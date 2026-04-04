# LINE リッチメニュー設定手順

## 概要

LINE Official Account Manager でリッチメニューを設定し、NewFUHI の Webhook と連携させる手順です。

## 前提条件

- LINE Official Account が作成済み
- Messaging API が有効化済み
- Webhook URL が設定済み: `https://timebaibai.com/line/webhook/`
- LINE Developers Console で Channel Secret / Access Token が発行済み

## リッチメニュー設定手順

### 1. LINE Official Account Manager にログイン

https://manager.line.biz/ にアクセスし、対象アカウントを選択。

### 2. リッチメニューを作成

1. サイドメニュー → **トークルーム管理** → **リッチメニュー**
2. **作成** をクリック
3. **テンプレートを選択**: 6分割（大）を推奨

### 3. ボタン配置（推奨レイアウト）

```
┌─────────┬─────────┬─────────┐
│         │         │         │
│  予約   │ 予約確認 │ お知らせ │
│  する   │         │         │
├─────────┼─────────┼─────────┤
│         │         │         │
│ ショップ │ お問い  │  Web    │
│         │ 合わせ  │  サイト  │
└─────────┴─────────┴─────────┘
```

### 4. 各ボタンのアクション設定

| ボタン | アクション種別 | 設定値 |
|--------|---------------|--------|
| 予約する | ポストバック | `action=start_booking` |
| 予約確認 | ポストバック | `action=check_booking` |
| お知らせ | URL | `https://timebaibai.com/` |
| ショップ | URL | `https://timebaibai.com/` |
| お問い合わせ | ポストバック | `action=contact` |
| Webサイト | URL | `https://timebaibai.com/` |

### 5. 表示設定

- **タイトル**: メインメニュー
- **トークルームメニューのテキスト**: メニュー
- **デフォルト表示**: ON（トーク画面を開いた時に自動表示）
- **表示期間**: 無期限

### 6. 保存・公開

**保存** をクリックして公開。

## Postback イベント対応表

| action パラメータ | 処理内容 | 実装場所 |
|-------------------|----------|----------|
| `start_booking` | チャットボット予約フロー開始 | `views_line_webhook.py` → `line_chatbot.py` |
| `check_booking` | 直近予約3件を返信 | `views_line_webhook.py` |
| `contact` | お問い合わせ案内テキスト | `views_line_webhook.py` |

## 注意事項

- リッチメニュー画像は LINE Official Account Manager 上で作成・アップロード
- API経由でのリッチメニュー設定も可能（`linebot.LineBotApi.create_rich_menu()`）だが、管理画面からの設定を推奨
- チャットボット予約を利用するには管理画面 → メインサイト設定 → LINE連携 → **LINEチャットボット** を ON にする
- リッチメニューの変更はLINE側の操作のみで完結（コード変更不要）
