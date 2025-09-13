# Developer Guide

> ⚠️ **開発中プロジェクト**
> このプロジェクトは現在開発中です. APIの変更, 機能の追加,削除が頻繁に行われる可能性があります.

Discord VC Auto-Kick Botの開発者向け技術ドキュメントです.

## プロジェクト構成

```
discord-vc-watcher/
├── bot.py                    # メインBotファイル
├── requirements.txt          # Python依存関係
├── .env.template            # 環境変数テンプレート
├── .env                     # 環境変数(gitignore対象)
├── .gitignore               # Git除外設定
├── discord-vc-bot.service   # systemdサービス設定(gitignore対象)
├── venv/                    # Python仮想環境(gitignore対象)
├── logs/                    # ログファイル(gitignore対象)
├── guild_settings.json      # サーバー設定(gitignore対象)
├── README.md                # ユーザー向けドキュメント
├── SETUP_GUIDE.md           # セットアップガイド
└── DEVELOPER.md             # 開発者向けドキュメント
```

## 開発環境セットアップ

### 1. リポジトリクローン

```bash
git clone https://github.com/yourusername/discord-vc-bot.git
cd discord-vc-bot
```

### 2. 仮想環境作成

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 環境変数設定

```bash
cp .env.template .env
# .envファイルを編集してBotトークンを設定
```

### 4. 開発用実行

```bash
source venv/bin/activate
python bot.py
```

## アーキテクチャ

### 技術スタック
- **Python**: 3.10+
- **discord.py**: 2.3.0+ (非同期Discord APIライブラリ)
- **aiofiles**: 非同期ファイルIO
- **python-dotenv**: 環境変数管理
- **systemd**: プロセス管理 (Linux)

### 非同期アーキテクチャ
```python
# イベントループベースの設計
async def main():
    async with bot:
        await bot.start(token)

# タスクベースの並行処理
@tasks.loop(minutes=2)
async def check_voice_activity():
    # 全ギルドの音声状態を並行チェック
    await asyncio.gather(*[check_guild(guild) for guild in bot.guilds])
```

## コード構造

### クラス設計

#### `VoiceState`
```python
class VoiceState:
    def __init__(self, user_id: int):
        self.user_id: int = user_id
        self.last_activity: datetime = datetime.now()
        self.work_mode: bool = False
        self.dm_warning_sent: bool = False
        self.sound_warning_sent: bool = False
        self.join_time: datetime = datetime.now()
        self.mute_changes: int = 0
```

#### `VCBot(commands.Bot)`
```python
class VCBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.guilds = True
        super().__init__(command_prefix='!', intents=intents)

        self.voice_states: Dict[int, Dict[int, VoiceState]] = {}
        self.guild_settings: Dict[int, Dict] = {}
```

#### `VCCommands(app_commands.Group)`
Slash Commandsの階層構造実装
```python
class VCCommands(app_commands.Group):
    def __init__(self, bot: VCBot):
        super().__init__(name="vc", description="VC監視関連コマンド")
        self.bot = bot
```

### 主要アルゴリズム

#### 音声アクティビティ検出
```python
@bot.event
async def on_voice_state_update(member, before, after):
    # WebSocket接続によるリアルタイム状態変更検出
    if before.channel != after.channel:
        await handle_channel_change(member, before, after)

    # ミュート状態変更の検出
    if before.self_mute != after.self_mute:
        await update_activity(member)
```

#### タイムアウト判定アルゴリズム
```python
def should_kick_user(voice_state: VoiceState, settings: dict) -> tuple[bool, str]:
    now = datetime.now()
    inactive_time = (now - voice_state.last_activity).total_seconds()

    # 猶予期間チェック
    if (now - voice_state.join_time).total_seconds() < settings['grace_period']:
        return False, "grace_period"

    # 作業モード判定
    if voice_state.work_mode:
        return inactive_time >= settings['work_final_timeout'], "work_timeout"
    else:
        return inactive_time >= settings['normal_timeout'], "normal_timeout"
```

#### 並行処理によるスケーラビリティ
```python
@tasks.loop(minutes=2)
async def check_voice_activity():
    tasks = []
    for guild in bot.guilds:
        if guild.id in bot.guild_settings:
            tasks.append(check_guild_voice_activity(guild))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
```

## データ管理

### 設定ファイルスキーマ

#### guild_settings.json
```typescript
interface GuildSettings {
  guild_id: number;           // Discord Guild ID (Snowflake)
  normal_timeout: number;     // 通常モードタイムアウト (秒)
  work_timeout: number;       // 作業モード警告タイムアウト (秒)
  work_warning_timeout: number; // 作業モードDM警告 (秒)
  work_final_timeout: number; // 作業モード最終タイムアウト (秒)
  min_users: number;          // キック対象最小ユーザー数
  grace_period: number;       // 参加後猶予期間 (秒)
  enabled: boolean;           // Bot有効/無効
  monitored_channels: number[]; // 監視対象チャンネルID配列
  log_channel_id: number | null; // ログ出力チャンネルID
  work_role_name: string;     // 作業モード時のロール名
}
```

### 環境変数設計
```bash
# Required
DISCORD_BOT_TOKEN=bot_token_here

# Optional
LOG_LEVEL=INFO                    # ログレベル
DEFAULT_NORMAL_TIMEOUT=1800      # デフォルト通常タイムアウト
DEFAULT_WORK_TIMEOUT=7200        # デフォルト作業タイムアウト
DEFAULT_GRACE_PERIOD=900         # デフォルト猶予期間
DATABASE_URL=sqlite:///bot.db    # 将来のDB接続用
```

### メモリ管理
```python
# WeakValueDictionary使用によるメモリリーク防止
from weakref import WeakValueDictionary

class VCBot(commands.Bot):
    def __init__(self):
        self.voice_states: Dict[int, WeakValueDictionary[int, VoiceState]] = {}

    async def cleanup_inactive_states(self):
        """非アクティブな状態オブジェクトのクリーンアップ"""
        for guild_id, states in self.voice_states.items():
            inactive_users = [
                user_id for user_id, state in states.items()
                if (datetime.now() - state.last_activity).days > 1
            ]
            for user_id in inactive_users:
                del states[user_id]
```

## 本番環境デプロイ

### systemdサービス設定

```bash
# サービスファイルをコピー
sudo cp discord-vc-bot.service /etc/systemd/system/
sudo systemctl daemon-reload

# サービス開始,自動起動設定
sudo systemctl start discord-vc-bot
sudo systemctl enable discord-vc-bot
```

### ログローテーション設定

```bash
# /etc/logrotate.d/discord-vc-bot
/path/to/your/project/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 ubuntu ubuntu
}
```

## 開発ガイドライン

### コーディング規約

- Python PEP 8に準拠
- 型ヒントを積極的に使用
- docstringでクラス,関数の説明を記述

### コミット規約

- 明確で簡潔なコミットメッセージ
- 機能追加: `feat: 新機能の説明`
- バグ修正: `fix: 修正内容の説明`
- ドキュメント: `docs: ドキュメント更新内容`

### テスト

```bash
# 構文チェック
python -m py_compile bot.py

# 依存関係チェック
pip check
```

## エラーハンドリング & パフォーマンス

### Discord API例外処理
```python
import discord
from discord.errors import HTTPException, Forbidden, NotFound

async def safe_move_user(user: discord.Member) -> bool:
    """安全なユーザー移動処理"""
    try:
        await user.move_to(None)  # キック
        return True
    except Forbidden:
        logger.error(f"権限不足: {user.display_name}をキックできません")
    except NotFound:
        logger.warning(f"ユーザーが見つかりません: {user.id}")
    except HTTPException as e:
        if e.status == 429:  # Rate Limited
            retry_after = e.response.headers.get('Retry-After', 1)
            logger.warning(f"Rate Limited: {retry_after}秒待機")
            await asyncio.sleep(float(retry_after))
            return await safe_move_user(user)  # リトライ
        else:
            logger.error(f"HTTP Error {e.status}: {e.text}")
    except Exception as e:
        logger.critical(f"予期しないエラー: {type(e).__name__}: {e}")
    return False
```

### 権限チェッカー
```python
class PermissionChecker:
    @staticmethod
    def check_required_permissions(guild: discord.Guild) -> tuple[bool, list[str]]:
        """必要権限の一括チェック"""
        required_perms = {
            'view_channel': 'チャンネル表示',
            'send_messages': 'メッセージ送信',
            'embed_links': '埋め込みリンク',
            'connect': 'VC接続',
            'move_members': 'メンバー移動'
        }

        missing_perms = []
        bot_perms = guild.me.guild_permissions

        for perm, name in required_perms.items():
            if not getattr(bot_perms, perm):
                missing_perms.append(name)

        return len(missing_perms) == 0, missing_perms
```

### レート制限管理
```python
from asyncio import Semaphore
from collections import defaultdict

class RateLimiter:
    def __init__(self):
        self.semaphores = defaultdict(lambda: Semaphore(5))  # ギルド毎に5並行

    async def acquire(self, guild_id: int):
        return await self.semaphores[guild_id].acquire()

    def release(self, guild_id: int):
        self.semaphores[guild_id].release()

# 使用例
rate_limiter = RateLimiter()

async def process_guild_kicks(guild: discord.Guild, users: list[discord.Member]):
    await rate_limiter.acquire(guild.id)
    try:
        for user in users:
            await safe_move_user(user)
            await asyncio.sleep(0.5)  # 追加の安全マージン
    finally:
        rate_limiter.release(guild.id)
```

### 構造化ログ
```python
import structlog
from pythonjsonlogger import jsonlogger

# 本番環境用JSON構造化ログ
def setup_logging():
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    handler.setFormatter(formatter)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# 使用例
logger = structlog.get_logger()
logger.info("user_kicked", user_id=12345, guild_id=67890, reason="timeout")
```

## パフォーマンス最適化

### メモリ使用量監視
```python
import psutil
from discord.ext import tasks

@tasks.loop(hours=1)
async def monitor_resources():
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    cpu_percent = process.cpu_percent()

    logger.info(
        "resource_usage",
        memory_mb=memory_mb,
        cpu_percent=cpu_percent,
        voice_states_count=sum(len(states) for states in bot.voice_states.values())
    )

    # メモリ使用量が500MBを超えた場合の警告
    if memory_mb > 500:
        logger.warning("high_memory_usage", memory_mb=memory_mb)
```

### データベース移行準備
```python
# 将来のPostgreSQL対応
from typing import Protocol

class GuildSettingsRepository(Protocol):
    async def get(self, guild_id: int) -> dict | None: ...
    async def save(self, guild_id: int, settings: dict) -> None: ...
    async def delete(self, guild_id: int) -> None: ...

class JsonGuildSettingsRepository:
    """現在のJSON実装"""
    async def get(self, guild_id: int) -> dict | None:
        # 既存のJSON読み込みロジック
        pass

class PostgreSQLGuildSettingsRepository:
    """将来のPostgreSQL実装"""
    async def get(self, guild_id: int) -> dict | None:
        # PostgreSQL実装
        pass
```

## 高度な機能実装

### Webhook統合
```python
from discord import Webhook
import aiohttp

class WebhookNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send_kick_notification(self, user: discord.Member, reason: str):
        async with aiohttp.ClientSession() as session:
            webhook = Webhook.from_url(self.webhook_url, session=session)
            embed = discord.Embed(
                title="ユーザーキック通知",
                description=f"{user.mention} がキックされました",
                color=0xff0000
            )
            embed.add_field(name="理由", value=reason)
            await webhook.send(embed=embed)
```

### 統計収集システム
```python
from collections import Counter, defaultdict
from datetime import datetime, timedelta

class StatisticsCollector:
    def __init__(self):
        self.kick_stats = defaultdict(Counter)
        self.daily_stats = defaultdict(lambda: defaultdict(int))

    def record_kick(self, guild_id: int, user_id: int, reason: str):
        today = datetime.now().date().isoformat()
        self.kick_stats[guild_id][reason] += 1
        self.daily_stats[guild_id][today] += 1

    def get_guild_statistics(self, guild_id: int, days: int = 30) -> dict:
        cutoff = datetime.now() - timedelta(days=days)
        recent_stats = {
            date: count for date, count in self.daily_stats[guild_id].items()
            if datetime.fromisoformat(date) >= cutoff.date()
        }

        return {
            'total_kicks': sum(self.kick_stats[guild_id].values()),
            'kicks_by_reason': dict(self.kick_stats[guild_id]),
            'daily_kicks': recent_stats,
            'avg_daily_kicks': sum(recent_stats.values()) / max(len(recent_stats), 1)
        }
```

## 拡張機能ロードマップ

### Phase 1: 安定性向上 (v1.1)
- [ ] PostgreSQL対応
- [ ] Redis caching
- [ ] Prometheus metrics
- [ ] Circuit breaker pattern
- [ ] Health check endpoint

### Phase 2: 機能拡張 (v1.2)
- [ ] Web管理画面 (FastAPI + React)
- [ ] ユーザー別除外設定
- [ ] カスタム警告音設定
- [ ] スケジュール機能 (特定時間帯のみ有効)
- [ ] 多言語対応 (i18n)

### Phase 3: 高度な機能 (v2.0)
- [ ] 機械学習による異常検知
- [ ] REST API提供
- [ ] 外部サービス連携 (Slack, Teams)
- [ ] クラスター構成対応
- [ ] GraphQL API

## コントリビューションガイドライン

### 開発フロー
1. **Issue作成**: 機能要望やバグ報告
2. **Fork & Branch**: `feature/xxx`, `fix/xxx`, `docs/xxx`
3. **開発**: TDD推奨, 型ヒント必須
4. **テスト**: 単体テスト, 統合テスト
5. **PR作成**: テンプレートに従って記述
6. **コードレビュー**: 2人以上の承認必要
7. **マージ**: Squash and Merge推奨

### コーディング規約
```python
# Type hints必須
def process_user(user: discord.Member, timeout: int) -> tuple[bool, str]:
    """ユーザー処理関数

    Args:
        user: 処理対象ユーザー
        timeout: タイムアウト時間(秒)

    Returns:
        (成功フラグ, 結果メッセージ)

    Raises:
        discord.HTTPException: API呼び出し失敗
    """
    pass

# Constants
CLASS_CONSTANTS = {
    'NORMAL_TIMEOUT': 1800,
    'WORK_TIMEOUT': 7200
}

# Enum使用推奨
from enum import Enum

class KickReason(Enum):
    NORMAL_TIMEOUT = "normal_timeout"
    WORK_TIMEOUT = "work_timeout"
    ADMIN_KICK = "admin_kick"
```

### テスト戦略
```python
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

@pytest_asyncio.async_test
async def test_user_kick_logic():
    # Arrange
    mock_user = MagicMock(spec=discord.Member)
    mock_user.move_to = AsyncMock()

    bot = VCBot()

    # Act
    result = await bot.kick_user(mock_user, "timeout")

    # Assert
    assert result is True
    mock_user.move_to.assert_called_once_with(None)

# 統合テスト例
@pytest.mark.integration
async def test_full_workflow():
    # Discord Bot Test Framework使用
    pass
```

## 技術仕様

### システム要件
- **Python**: 3.10+ (型ヒント, match文使用)
- **Memory**: 128MB+ (小規模), 512MB+ (大規模)
- **CPU**: 1コア+ (非同期処理最適化)
- **Storage**: 1GB+ (ログ, 設定ファイル)
- **Network**: Outbound HTTPS (Discord API)

### Docker対応
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
USER 1000

CMD ["python", "bot.py"]
```

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: discord-vc-bot
spec:
  replicas: 1
  selector:
    matchLabels:
      app: discord-vc-bot
  template:
    metadata:
      labels:
        app: discord-vc-bot
    spec:
      containers:
      - name: bot
        image: discord-vc-bot:latest
        env:
        - name: DISCORD_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: bot-secrets
              key: token
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

## ライセンス

MIT License - 詳細は[LICENSE](LICENSE)ファイルを参照