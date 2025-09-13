#!/usr/bin/env python3
"""
Discord VC Auto-Kick Bot
寝落ち検知・自動キックBot
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
import os
from pathlib import Path

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/opt/discord-vc-bot/logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('VCBot')

class VoiceState:
    """ユーザーの音声状態を管理"""
    def __init__(self, user_id: int, guild_id: int):
        self.user_id = user_id
        self.guild_id = guild_id
        self.last_voice_activity = datetime.now()
        self.join_time = datetime.now()
        self.is_working = False
        self.warning_sent = False
        self.sound_played = False
        
    def update_activity(self):
        """音声アクティビティを更新"""
        self.last_voice_activity = datetime.now()
        self.warning_sent = False
        self.sound_played = False
        
    def get_silence_duration(self) -> float:
        """無音継続時間を取得（秒）"""
        return (datetime.now() - self.last_voice_activity).total_seconds()

class GuildSettings:
    """サーバーごとの設定"""
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.normal_timeout = 1800  # 30分
        self.work_timeout = 3600    # 60分
        self.work_warning_timeout = 5400  # 90分
        self.work_final_timeout = 7200    # 120分
        self.min_users = 2
        self.grace_period = 900     # 15分
        self.enabled = True
        self.monitored_channels: Set[int] = set()
        self.log_channel_id: Optional[int] = None
        self.work_role_name = "作業中"
        
    def to_dict(self) -> dict:
        return {
            'guild_id': self.guild_id,
            'normal_timeout': self.normal_timeout,
            'work_timeout': self.work_timeout,
            'work_warning_timeout': self.work_warning_timeout,
            'work_final_timeout': self.work_final_timeout,
            'min_users': self.min_users,
            'grace_period': self.grace_period,
            'enabled': self.enabled,
            'monitored_channels': list(self.monitored_channels),
            'log_channel_id': self.log_channel_id,
            'work_role_name': self.work_role_name
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GuildSettings':
        settings = cls(data['guild_id'])
        settings.normal_timeout = data.get('normal_timeout', 1800)
        settings.work_timeout = data.get('work_timeout', 3600)
        settings.work_warning_timeout = data.get('work_warning_timeout', 5400)
        settings.work_final_timeout = data.get('work_final_timeout', 7200)
        settings.min_users = data.get('min_users', 2)
        settings.grace_period = data.get('grace_period', 900)
        settings.enabled = data.get('enabled', True)
        settings.monitored_channels = set(data.get('monitored_channels', []))
        settings.log_channel_id = data.get('log_channel_id')
        settings.work_role_name = data.get('work_role_name', '作業中')
        return settings

class VCAutoKickBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.guilds = True
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.voice_states: Dict[int, Dict[int, VoiceState]] = {}  # {guild_id: {user_id: VoiceState}}
        self.guild_settings: Dict[int, GuildSettings] = {}
        self.settings_file = Path('/opt/discord-vc-bot/guild_settings.json')
        self.load_settings()
        
    def load_settings(self):
        """設定をファイルから読み込み"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    for guild_data in data:
                        settings = GuildSettings.from_dict(guild_data)
                        self.guild_settings[settings.guild_id] = settings
                logger.info(f"Loaded settings for {len(self.guild_settings)} guilds")
            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
    
    def save_settings(self):
        """設定をファイルに保存"""
        try:
            data = [settings.to_dict() for settings in self.guild_settings.values()]
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("Settings saved successfully")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    def get_guild_settings(self, guild_id: int) -> GuildSettings:
        """ギルドの設定を取得（なければ作成）"""
        if guild_id not in self.guild_settings:
            self.guild_settings[guild_id] = GuildSettings(guild_id)
            self.save_settings()
        return self.guild_settings[guild_id]
    
    async def setup_hook(self):
        """Bot起動時の初期設定"""
        await self.tree.sync()
        self.monitor_voice_channels.start()
        logger.info("Bot setup completed")
    
    async def on_ready(self):
        """Bot準備完了時"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Connected to {len(self.guilds)} guilds')
        
        # 既存のVCユーザーを登録
        for guild in self.guilds:
            if guild.id not in self.voice_states:
                self.voice_states[guild.id] = {}
            
            for vc in guild.voice_channels:
                for member in vc.members:
                    if not member.bot:
                        state = VoiceState(member.id, guild.id)
                        self.voice_states[guild.id][member.id] = state
    
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """音声状態更新時の処理"""
        if member.bot:
            return
        
        guild_id = member.guild.id
        if guild_id not in self.voice_states:
            self.voice_states[guild_id] = {}
        
        # VCに参加
        if before.channel is None and after.channel is not None:
            state = VoiceState(member.id, guild_id)
            # 作業中ロールチェック
            settings = self.get_guild_settings(guild_id)
            work_role = discord.utils.get(member.guild.roles, name=settings.work_role_name)
            if work_role and work_role in member.roles:
                state.is_working = True
            self.voice_states[guild_id][member.id] = state
            logger.info(f"{member.name} joined VC in {member.guild.name}")
        
        # VCから退出
        elif before.channel is not None and after.channel is None:
            if member.id in self.voice_states[guild_id]:
                del self.voice_states[guild_id][member.id]
                logger.info(f"{member.name} left VC in {member.guild.name}")
        
        # ミュート状態の変更を検知
        elif after.channel is not None:
            if not after.self_mute and not after.mute:
                # アンミュート = 活動とみなす
                if member.id in self.voice_states[guild_id]:
                    self.voice_states[guild_id][member.id].update_activity()
    
    async def ensure_work_role(self, guild: discord.Guild) -> discord.Role:
        """作業中ロールを確保（なければ作成）"""
        settings = self.get_guild_settings(guild.id)
        role = discord.utils.get(guild.roles, name=settings.work_role_name)
        
        if role is None:
            try:
                role = await guild.create_role(
                    name=settings.work_role_name,
                    color=discord.Color.blue(),
                    reason="VC Auto-Kick Bot: 作業中ロール作成"
                )
                logger.info(f"Created work role in {guild.name}")
            except discord.Forbidden:
                logger.error(f"Permission denied to create role in {guild.name}")
                return None
        
        return role
    
    async def send_warning_dm(self, member: discord.Member):
        """警告DMを送信"""
        try:
            embed = discord.Embed(
                title="⚠️ 長時間無音状態です",
                description="作業中のようですが、60分以上音声アクティビティがありません。\n"
                           "このまま無音が続くと、VCから自動的にキックされます。",
                color=discord.Color.yellow(),
                timestamp=datetime.now()
            )
            embed.add_field(name="残り時間", value="約60分", inline=False)
            embed.set_footer(text=f"サーバー: {member.guild.name}")
            
            await member.send(embed=embed)
            logger.info(f"Warning DM sent to {member.name}")
        except discord.Forbidden:
            logger.warning(f"Cannot send DM to {member.name}")
    
    async def play_warning_sound(self, channel: discord.VoiceChannel):
        """VCで警告音を再生（簡易実装）"""
        # Note: 実際の音声再生にはffmpegとdiscord.pyの音声機能が必要
        # ここでは実装の概要のみ示す
        try:
            if channel.guild.voice_client is None:
                await channel.connect()
            
            # 警告音を再生する処理
            # voice_client = channel.guild.voice_client
            # source = discord.FFmpegPCMAudio('/opt/discord-vc-bot/warning.mp3')
            # voice_client.play(source)
            
            logger.info(f"Warning sound played in {channel.name}")
        except Exception as e:
            logger.error(f"Failed to play warning sound: {e}")
    
    async def kick_from_vc(self, member: discord.Member, reason: str):
        """VCからキック"""
        try:
            await member.move_to(None)
            logger.info(f"Kicked {member.name} from VC: {reason}")
            
            # ログチャンネルに通知
            settings = self.get_guild_settings(member.guild.id)
            if settings.log_channel_id:
                log_channel = member.guild.get_channel(settings.log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="🔇 自動キック実行",
                        description=f"{member.mention} をVCからキックしました",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="理由", value=reason, inline=False)
                    await log_channel.send(embed=embed)
        except discord.Forbidden:
            logger.error(f"Permission denied to kick {member.name}")
        except Exception as e:
            logger.error(f"Failed to kick {member.name}: {e}")
    
    @tasks.loop(seconds=30)
    async def monitor_voice_channels(self):
        """VCを定期的に監視"""
        for guild_id, states in self.voice_states.items():
            if not states:
                continue
            
            guild = self.get_guild(guild_id)
            if not guild:
                continue
            
            settings = self.get_guild_settings(guild_id)
            if not settings.enabled:
                continue
            
            # VCごとにチェック
            voice_channels = {}
            for user_id, state in states.items():
                member = guild.get_member(user_id)
                if member and member.voice and member.voice.channel:
                    channel_id = member.voice.channel.id
                    if channel_id not in voice_channels:
                        voice_channels[channel_id] = []
                    voice_channels[channel_id].append((member, state))
            
            for channel_id, members_states in voice_channels.items():
                # 監視対象チャンネルかチェック
                if settings.monitored_channels and channel_id not in settings.monitored_channels:
                    continue
                
                # Bot以外の人数チェック
                if len(members_states) < settings.min_users:
                    continue
                
                # 各メンバーの無音時間をチェック
                all_silent = True
                for member, state in members_states:
                    silence_duration = state.get_silence_duration()
                    
                    # 初回参加の猶予期間
                    if (datetime.now() - state.join_time).total_seconds() < settings.grace_period:
                        all_silent = False
                        continue
                    
                    if state.is_working:
                        # 作業中ユーザーの段階的チェック
                        if silence_duration < settings.work_timeout:
                            all_silent = False
                        elif silence_duration >= settings.work_final_timeout:
                            await self.kick_from_vc(member, "作業中: 120分以上無音")
                        elif silence_duration >= settings.work_warning_timeout and not state.sound_played:
                            channel = guild.get_channel(channel_id)
                            if channel:
                                await self.play_warning_sound(channel)
                            state.sound_played = True
                        elif silence_duration >= settings.work_timeout and not state.warning_sent:
                            await self.send_warning_dm(member)
                            state.warning_sent = True
                    else:
                        # 通常ユーザー
                        if silence_duration < settings.normal_timeout:
                            all_silent = False
                        elif silence_duration >= settings.normal_timeout:
                            await self.kick_from_vc(member, "30分以上無音")
                
                # 全員が無音の場合
                if all_silent and len(members_states) >= settings.min_users:
                    for member, state in members_states:
                        if not state.is_working:
                            await self.kick_from_vc(member, "全員が無音状態")

# スラッシュコマンド
class VCCommands(app_commands.Group):
    def __init__(self, bot: VCAutoKickBot):
        super().__init__(name="vc", description="VC自動キックBotの設定")
        self.bot = bot
    
    @app_commands.command(name="work", description="作業モードの切り替え")
    async def work(self, interaction: discord.Interaction):
        """作業中ロールの付与/解除"""
        member = interaction.user
        guild = interaction.guild
        role = await self.bot.ensure_work_role(guild)
        
        if role is None:
            await interaction.response.send_message("❌ 作業中ロールの作成に失敗しました", ephemeral=True)
            return
        
        if role in member.roles:
            await member.remove_roles(role)
            # 状態を更新
            if guild.id in self.bot.voice_states and member.id in self.bot.voice_states[guild.id]:
                self.bot.voice_states[guild.id][member.id].is_working = False
            await interaction.response.send_message("✅ 作業モードを解除しました", ephemeral=True)
        else:
            await member.add_roles(role)
            # 状態を更新
            if guild.id in self.bot.voice_states and member.id in self.bot.voice_states[guild.id]:
                self.bot.voice_states[guild.id][member.id].is_working = True
            await interaction.response.send_message("✅ 作業モードを有効にしました（無音許容時間: 120分）", ephemeral=True)
    
    @app_commands.command(name="status", description="現在のVC監視状態を確認")
    async def status(self, interaction: discord.Interaction):
        """監視状態の確認"""
        guild = interaction.guild
        settings = self.bot.get_guild_settings(guild.id)
        
        embed = discord.Embed(
            title="VC監視状態",
            color=discord.Color.green() if settings.enabled else discord.Color.red()
        )
        
        embed.add_field(name="監視", value="✅ 有効" if settings.enabled else "❌ 無効", inline=True)
        embed.add_field(name="通常タイムアウト", value=f"{settings.normal_timeout//60}分", inline=True)
        embed.add_field(name="作業中タイムアウト", value=f"{settings.work_final_timeout//60}分", inline=True)
        
        # 現在のVC状態
        if guild.id in self.bot.voice_states:
            active_users = len(self.bot.voice_states[guild.id])
            embed.add_field(name="監視中のユーザー", value=f"{active_users}人", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="enable", description="VC監視を有効化")
    @app_commands.checks.has_permissions(administrator=True)
    async def enable(self, interaction: discord.Interaction):
        """監視を有効化"""
        settings = self.bot.get_guild_settings(interaction.guild.id)
        settings.enabled = True
        self.bot.save_settings()
        await interaction.response.send_message("✅ VC監視を有効化しました", ephemeral=True)
    
    @app_commands.command(name="disable", description="VC監視を無効化")
    @app_commands.checks.has_permissions(administrator=True)
    async def disable(self, interaction: discord.Interaction):
        """監視を無効化"""
        settings = self.bot.get_guild_settings(interaction.guild.id)
        settings.enabled = False
        self.bot.save_settings()
        await interaction.response.send_message("✅ VC監視を無効化しました", ephemeral=True)
    
    @app_commands.command(name="timeout", description="タイムアウト時間を設定")
    @app_commands.checks.has_permissions(administrator=True)
    async def timeout(
        self, 
        interaction: discord.Interaction,
        normal: int = None,
        work: int = None
    ):
        """タイムアウト時間の設定（分単位）"""
        settings = self.bot.get_guild_settings(interaction.guild.id)
        
        if normal:
            settings.normal_timeout = normal * 60
        if work:
            settings.work_final_timeout = work * 60
            settings.work_warning_timeout = int(work * 60 * 0.75)
            settings.work_timeout = int(work * 60 * 0.5)
        
        self.bot.save_settings()
        
        embed = discord.Embed(
            title="タイムアウト設定を更新",
            color=discord.Color.blue()
        )
        embed.add_field(name="通常", value=f"{settings.normal_timeout//60}分", inline=True)
        embed.add_field(name="作業中", value=f"{settings.work_final_timeout//60}分", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="setlog", description="ログチャンネルを設定")
    @app_commands.checks.has_permissions(administrator=True)
    async def setlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """ログチャンネルの設定"""
        settings = self.bot.get_guild_settings(interaction.guild.id)
        settings.log_channel_id = channel.id
        self.bot.save_settings()
        await interaction.response.send_message(f"✅ ログチャンネルを {channel.mention} に設定しました", ephemeral=True)

# メイン処理
async def main():
    bot = VCAutoKickBot()
    
    @bot.event
    async def on_ready():
        # コマンドグループを追加
        bot.tree.add_command(VCCommands(bot))
        await bot.tree.sync()
    
    # Botトークンは環境変数から取得
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables")
        return
    
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())