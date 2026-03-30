# WordPress 埋め込みガイド

Timebaibai（占いサロンチャンス）の予約カレンダーやシフト表示を WordPress サイトに埋め込む手順です。

---

## 前提条件

- Timebaibai の管理者アカウント
- WordPress の編集権限（functions.php またはプラグイン追加）

---

## Step 1: Timebaibai 側の設定

### 1.1 埋め込み機能を有効化

1. 管理画面 → **メインページ設定** → 「外部埋め込みを有効化」を **ON**
2. 保存

### 1.2 API キーを生成

1. 管理画面 → **店舗管理** → 対象店舗を選択
2. **アクション** ドロップダウンから「埋め込みAPIキーを生成」を選択 → 実行
3. 生成されたAPIキー（64文字）をコピー

### 1.3 許可ドメインを設定（推奨）

1. 店舗編集画面の「**埋め込み許可ドメイン**」に WordPress サイトのドメインを入力
   - 例: `example.com, www.example.com`
   - カンマ区切りで複数指定可能
2. 設定すると、指定ドメイン以外からの iframe 表示がブロックされます

---

## Step 2: WordPress 側の設定

### 方法A: ショートコード（推奨）

`newfuhi-embed.php` の内容をテーマの `functions.php` 末尾に追加するか、
Code Snippets プラグイン等で追加してください。

追加後、以下のショートコードが使えるようになります:

```
[newfuhi_booking store_id="1" api_key="YOUR_API_KEY"]
[newfuhi_shift store_id="1" api_key="YOUR_API_KEY"]
```

#### パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `store_id` | `1` | 店舗ID |
| `api_key` | (必須) | Step 1.2 で生成した API キー |
| `height` | `600` (予約) / `400` (シフト) | iframe の高さ (px) |
| `width` | `100%` | iframe の幅 |

#### 使用例

固定ページや投稿のエディタ（ブロックエディタの場合は「ショートコード」ブロック）に以下を記述:

```
[newfuhi_booking store_id="1" api_key="abc123..." height="700"]
```

### 方法B: HTML 直接埋め込み

ショートコードを使わず、カスタム HTML ブロック等で直接 iframe を記述:

```html
<iframe
  src="https://timebaibai.com/embed/booking/1/?api_key=YOUR_API_KEY"
  width="100%"
  height="600"
  style="border: none; max-width: 100%;"
  loading="lazy"
  title="予約カレンダー"
></iframe>
```

---

## 埋め込みURL一覧

| URL | 表示内容 |
|-----|---------|
| `/embed/booking/<store_id>/?api_key=xxx` | 予約カレンダー（予約スロット一覧） |
| `/embed/shift/<store_id>/?api_key=xxx` | 本日のシフト（出勤キャスト一覧） |

---

## セキュリティ

- API キーなし/不一致: **403 Forbidden**
- 埋め込み無効（グローバル設定 OFF）: **404 Not Found**
- `embed_allowed_domains` 設定時: `Content-Security-Policy: frame-ancestors` ヘッダーが追加され、指定ドメイン以外での iframe 表示がブロックされます
- **timebaibai.com の他のページは iframe 表示不可**（`X-Frame-Options: DENY` を維持）

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| 403 エラー | API キーが間違い/未設定 | 店舗管理で API キーを再生成 |
| 404 エラー | 埋め込みが無効 | メインページ設定で「外部埋め込みを有効化」を ON |
| iframe が空白 | ブラウザがブロック | 許可ドメイン設定を確認、mixed content (HTTP/HTTPS) を確認 |
| レイアウト崩れ | iframe サイズ不適切 | `height` パラメータを調整 |

---

## ファイル一覧

| ファイル | 説明 |
|---------|------|
| `newfuhi-embed.php` | WordPress ショートコード定義（functions.php にコピペ） |
| `embed_example.html` | 動作確認用スタンドアロン HTML |
| `README_wordpress.md` | 本ドキュメント |
