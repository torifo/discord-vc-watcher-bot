#!/bin/bash

# Discord VC Auto-Kick Bot セットアップスクリプト

set -e

echo "Discord VC Auto-Kick Bot セットアップを開始します..."

# 1. 必要なパッケージのインストール
echo "必要なパッケージをインストール中..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv

# 2. ユーザーとディレクトリの作成
echo "ユーザーとディレクトリを作成中..."
sudo useradd -r -s /bin/false discord-bot || echo "ユーザーは既に存在します"
sudo mkdir -p /opt/discord-vc-bot/logs
sudo chown -R discord-bot:discord-bot /opt/discord-vc-bot

# 3. Pythonファイルのコピー
echo "Botファイルをコピー中..."
sudo cp bot.py /opt/discord-vc-bot/
sudo cp requirements.txt /opt/discord-vc-bot/

# 4. Python仮想環境の作成
echo "Python仮想環境を作成中..."
sudo -u discord-bot python3 -m venv /opt/discord-vc-bot/venv

# 5. 依存関係のインストール
echo "Python依存関係をインストール中..."
sudo -u discord-bot /opt/discord-vc-bot/venv/bin/pip install --upgrade pip
sudo -u discord-bot /opt/discord-vc-bot/venv/bin/pip install -r /opt/discord-vc-bot/requirements.txt

# 6. systemdサービスファイルのコピー
echo "systemdサービスファイルを設定中..."
sudo cp discord-vc-bot.service /etc/systemd/system/

# 7. Botトークンの設定
echo ""
echo "=========================================="
echo "Botトークンを設定してください："
echo "1. /etc/systemd/system/discord-vc-bot.service を編集"
echo "2. YOUR_BOT_TOKEN_HERE を実際のトークンに置き換え"
echo ""
echo "または環境変数ファイルを使用："
echo "sudo nano /opt/discord-vc-bot/.env"
echo "DISCORD_BOT_TOKEN=your_actual_token_here"
echo "=========================================="
echo ""

# 8. 権限の設定
echo "権限を設定中..."
sudo chown -R discord-bot:discord-bot /opt/discord-vc-bot
sudo chmod 755 /opt/discord-vc-bot
sudo chmod 644 /opt/discord-vc-bot/*.py
sudo chmod 755 /opt/discord-vc-bot/logs

# 9. systemdの再読み込み
echo "systemdを再読み込み中..."
sudo systemctl daemon-reload

echo ""
echo "=========================================="
echo "セットアップが完了しました！"
echo ""
echo "使用方法："
echo "  サービス開始: sudo systemctl start discord-vc-bot"
echo "  サービス停止: sudo systemctl stop discord-vc-bot"
echo "  サービス再起動: sudo systemctl restart discord-vc-bot"
echo "  自動起動有効化: sudo systemctl enable discord-vc-bot"
echo "  ログ確認: sudo journalctl -u discord-vc-bot -f"
echo ""
echo "Botトークンの設定を忘れずに行ってください！"
echo "=========================================="