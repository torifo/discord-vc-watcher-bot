# Discord VC Auto-Kick Bot

寝落ち検知・自動キック機能を持つDiscord VCボットです。

## 機能

- **自動キック機能**: 一定時間無音のユーザーを自動的にVCからキック
- **作業モード**: 長時間の作業用に警告付きの延長タイマー
- **柔軟な設定**: サーバーごとにタイムアウト時間やチャンネルを個別設定
- **ログ機能**: キック履歴やBot動作のログを記録

## 動作仕様

### 通常モード（デフォルト）
- 参加後30分無音でキック

### 作業モード（`/vc work`実行後）
- 60分無音 → DM警告
- 90分無音 → 警告音再生
- 120分無音 → 自動キック

### キックされない条件
- VCに1人だけの場合
- 参加から15分以内（猶予期間）
- 定期的に音声アクティビティがある
- ミュート解除などの操作を行った

## Botの招待

以下のリンクからBotをサーバーに招待できます：

[Botを招待](https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8396800&scope=bot%20applications.commands)

### 必要な権限

- View Channels（チャンネルを見る）
- Send Messages（メッセージを送信）
- Embed Links（埋め込みリンク）
- Connect（接続）
- Move Members（メンバーを移動）
- Use Voice Activity（音声検出を使用）

## 使用方法

### 基本コマンド

| コマンド | 説明 |
|---------|------|
| `/vc status` | 現在の設定状況を表示 |
| `/vc work` | 作業モードに切り替え |
| `/vc normal` | 通常モードに戻す |
| `/vc stop` | 監視を停止 |
| `/vc start` | 監視を開始 |

### 管理者コマンド

| コマンド | 説明 |
|---------|------|
| `/vc config timeout <秒>` | 通常タイムアウト時間を設定 |
| `/vc config work-timeout <秒>` | 作業タイムアウト時間を設定 |
| `/vc config grace-period <秒>` | 猶予期間を設定 |
| `/vc config min-users <人数>` | 最小ユーザー数を設定 |
| `/vc setchannel <チャンネル>` | 監視チャンネルを設定 |
| `/vc unsetchannel <チャンネル>` | 監視チャンネルを解除 |
| `/vc setlog <チャンネル>` | ログチャンネルを設定 |

## 設定例

```bash
# 通常モードを45分に設定
/vc config timeout 2700

# 作業モードを3時間に設定
/vc config work-timeout 10800

# 猶予期間を10分に設定
/vc config grace-period 600

# 最小ユーザー数を1人に設定（一人でもキックされる）
/vc config min-users 1
```

## サポート

問題や要望がある場合は、以下にお問い合わせください：

- [GitHub Issues](https://github.com/yourusername/discord-vc-bot/issues)
- Discord: `@your_discord_username`

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 更新履歴

### v1.0.0
- 基本的な自動キック機能
- 作業モード実装
- スラッシュコマンド対応
- サーバー別設定機能