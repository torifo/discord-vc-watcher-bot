# Discord VC Auto-Kick Bot セットアップガイド

## 概要
このBotは、Discord VCで長時間無音状態のユーザーを自動的にキックする汎用Public Botです。

## 主な機能

### 🎯 コア機能
- **自動キック**: 30分以上無音のユーザーを自動キック
- **作業モード**: `/vc work`で作業モード切り替え（120分まで延長）
- **段階的警告**: 作業中ユーザーには段階的に警告
  - 60分: DM警告
  - 90分: VC内で警告音
  - 120分: キック実行
- **マルチサーバー対応**: 複数のDiscordサーバーで同時動作

## Discord Developer Portalでの設定

### 1. Botの作成
1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. 「New Application」をクリック
3. アプリケーション名を入力（例: VC Auto-Kick Bot）

### 2. Bot設定
1. 左メニューから「Bot」を選択
2. 「Reset Token」でトークンを生成・コピー
3. 以下の設定を有効化:
   - **Public Bot**: ✅（誰でも追加可能）
   - **Presence Intent**: ✅
   - **Server Members Intent**: ✅
   - **Message Content Intent**: ✅

### 3. 必要な権限（Permissions）
OAuth2 > URL Generatorで以下を選択:

**Scopes**: `bot`, `applications.commands`

**Bot Permissions**:
- View Channels
- Send Messages
- Embed Links
- Connect
- Move Members
- Manage Roles
- Use Slash Commands

### 4. 招待URLの生成
生成されたURLを使用してBotをサーバーに追加

## サーバーへのインストール

### 前提条件
- Ubuntu 20.04以降 または Debian 11以降
- Python 3.8以上
- sudo権限

### インストール手順

```bash
# 1. ファイルをダウンロード
git clone https://github.com/yourusername/discord-vc-bot.git
cd discord-vc-bot

# 2. 仮想環境を作成して依存関係をインストール
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Botトークンを設定
nano .env
# DISCORD_BOT_TOKEN=your_actual_token_here

# 4. systemdサービスファイルをコピー
sudo cp discord-vc-bot.service /etc/systemd/system/
sudo systemctl daemon-reload

# 5. サービスを開始
sudo systemctl start discord-vc-bot
sudo systemctl enable discord-vc-bot

# 6. ログを確認
sudo journalctl -u discord-vc-bot -f
```

## 使用方法

### スラッシュコマンド

#### 一般ユーザー向け
- `/vc work` - 作業モードの切り替え
- `/vc status` - 現在の監視状態を確認

#### 管理者向け
- `/vc enable` - VC監視を有効化
- `/vc disable` - VC監視を無効化
- `/vc timeout [normal] [work]` - タイムアウト時間を設定（分単位）
- `/vc setlog #channel` - ログチャンネルを設定

## 動作仕様

### 通常モード（デフォルト）
参加 → 30分無音 → 自動キック

### 作業モード（`/vc work`実行後）
参加 → 60分無音 → DM警告 → 90分無音 → 警告音 → 120分無音 → 自動キック

### キックされない条件
- VCに1人だけの場合
- 参加から15分以内（猶予期間）
- 定期的に音声アクティビティがある
- ミュート解除などの操作を行った

## トラブルシューティング

### Botがオンラインにならない
```bash
# トークンの確認
sudo systemctl status discord-vc-bot

# ログの確認
sudo journalctl -u discord-vc-bot -n 50
```

### 権限エラー
- Botに必要な権限が付与されているか確認
- Botのロールが対象ユーザーより上位にあるか確認

### キックされない
- `/vc status`で監視が有効か確認
- 監視対象のVCチャンネルか確認
- 最小人数（2人）を満たしているか確認

## 設定ファイル

### guild_settings.json
各サーバーの設定は自動的に保存されます:

```json
{
  "guild_id": 123456789,
  "normal_timeout": 1800,
  "work_timeout": 3600,
  "work_warning_timeout": 5400,
  "work_final_timeout": 7200,
  "min_users": 2,
  "grace_period": 900,
  "enabled": true,
  "monitored_channels": [],
  "log_channel_id": null,
  "work_role_name": "作業中"
}
```

## セキュリティ

### 推奨事項
- Botトークンは環境変数で管理
- 最小権限の原則を適用
- ログファイルの定期的な確認
- systemdのセキュリティ設定を活用

### ログローテーション
```bash
# /etc/logrotate.d/discord-vc-bot
/home/ubuntu/Bot/discord/vc-watcher/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 ubuntu ubuntu
}
```

## メンテナンス

### アップデート
```bash
# Botを停止
sudo systemctl stop discord-vc-bot

# ファイルを更新
cp new_bot.py /home/ubuntu/Bot/discord/vc-watcher/bot.py

# 依存関係を更新
source /home/ubuntu/Bot/discord/vc-watcher/venv/bin/activate
pip install -r /home/ubuntu/Bot/discord/vc-watcher/requirements.txt

# Botを再起動
sudo systemctl start discord-vc-bot
```

### バックアップ
```bash
# 設定ファイルのバックアップ
cp /home/ubuntu/Bot/discord/vc-watcher/guild_settings.json /home/ubuntu/Bot/discord/vc-watcher/guild_settings.json.bak
```

## 今後の拡張予定
- [ ] Web管理画面
- [ ] 統計機能（キック回数、無音時間など）
- [ ] カスタム警告音のアップロード
- [ ] 時間帯別の設定
- [ ] 特定ユーザーのホワイトリスト
- [ ] AIによる会話検出（より精密な寝落ち判定）

## サポート
問題が発生した場合は、以下の情報と共に報告してください:

- Botのバージョン
- エラーログ（`sudo journalctl -u discord-vc-bot -n 100`）
- 発生状況の詳細

