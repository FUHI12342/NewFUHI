#!/usr/bin/env python3
"""
SNS自動投稿 + WordPress埋め込み 機能ガイド PDF生成スクリプト
WeasyPrint を使用して HTML → PDF 変換
"""
import datetime

HTML_CONTENT = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<style>
  @page { size: A4; margin: 20mm 15mm; }
  body { font-family: "Hiragino Sans", "Yu Gothic", sans-serif; font-size: 11pt; line-height: 1.7; color: #1a1a1a; }
  h1 { font-size: 22pt; color: #1e40af; border-bottom: 3px solid #1e40af; padding-bottom: 8px; margin-top: 40px; }
  h2 { font-size: 16pt; color: #1e3a5f; margin-top: 30px; border-left: 4px solid #3b82f6; padding-left: 12px; }
  h3 { font-size: 13pt; color: #374151; margin-top: 20px; }
  .cover { text-align: center; padding-top: 120px; page-break-after: always; }
  .cover h1 { font-size: 28pt; border: none; color: #1e40af; }
  .cover .subtitle { font-size: 14pt; color: #6b7280; margin-top: 10px; }
  .cover .date { font-size: 12pt; color: #9ca3af; margin-top: 40px; }
  .cover .logo { font-size: 40pt; margin-bottom: 20px; }
  table { border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 10pt; }
  th, td { border: 1px solid #d1d5db; padding: 8px 12px; text-align: left; }
  th { background: #eff6ff; font-weight: bold; color: #1e3a5f; }
  tr:nth-child(even) { background: #f9fafb; }
  .note { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px 16px; margin: 15px 0; font-size: 10pt; }
  .info { background: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px 16px; margin: 15px 0; font-size: 10pt; }
  .success { background: #ecfdf5; border-left: 4px solid #10b981; padding: 12px 16px; margin: 15px 0; font-size: 10pt; }
  .danger { background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 16px; margin: 15px 0; font-size: 10pt; }
  code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 9pt; font-family: monospace; }
  pre { background: #1f2937; color: #e5e7eb; padding: 16px; border-radius: 8px; font-size: 9pt; overflow-x: auto; font-family: monospace; line-height: 1.5; }
  .ui-mock { background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 12px; padding: 20px; margin: 15px 0; }
  .ui-mock .header { background: #1e40af; color: white; padding: 10px 16px; border-radius: 8px 8px 0 0; margin: -20px -20px 16px -20px; font-weight: bold; }
  .ui-mock .card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 10px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 9pt; font-weight: bold; }
  .badge-blue { background: #dbeafe; color: #1e40af; }
  .badge-green { background: #dcfce7; color: #166534; }
  .badge-orange { background: #ffedd5; color: #9a3412; }
  .badge-gray { background: #f3f4f6; color: #4b5563; }
  .score { font-size: 18pt; font-weight: bold; }
  .score-high { color: #16a34a; }
  .score-mid { color: #f59e0b; }
  .score-low { color: #ef4444; }
  .flow-step { display: flex; align-items: flex-start; margin: 10px 0; }
  .flow-num { background: #3b82f6; color: white; width: 28px; height: 28px; border-radius: 50%; text-align: center; line-height: 28px; font-weight: bold; font-size: 10pt; flex-shrink: 0; margin-right: 12px; }
  .flow-text { flex: 1; }
  .page-break { page-break-before: always; }
  .toc { margin: 30px 0; }
  .toc a { color: #1e40af; text-decoration: none; }
  .toc li { margin: 8px 0; font-size: 12pt; }
  .arrow { text-align: center; font-size: 20pt; color: #3b82f6; margin: 5px 0; }
  .embed-demo { background: #f0f9ff; border: 2px dashed #3b82f6; border-radius: 8px; padding: 40px; text-align: center; color: #1e40af; margin: 15px 0; }
</style>
</head>
<body>

<!-- 表紙 -->
<div class="cover">
  <div class="logo">🔮</div>
  <h1>Timebaibai 新機能ガイド</h1>
  <div class="subtitle">SNS自動投稿 + AI生成 + WordPress埋め込み</div>
  <div class="subtitle" style="margin-top:5px;">占いサロンチャンス 管理者向け</div>
  <div class="date">""" + datetime.date.today().strftime('%Y年%m月%d日') + """</div>
  <div style="margin-top:60px; font-size:10pt; color:#9ca3af;">
    Timebaibai Platform v3.0<br>
    https://timebaibai.com
  </div>
</div>

<!-- 目次 -->
<h1>目次</h1>
<ol class="toc">
  <li><a href="#overview">機能概要</a></li>
  <li><a href="#rag">RAGナレッジ管理</a></li>
  <li><a href="#draft">AI下書き生成 + LLM Judge評価</a></li>
  <li><a href="#posting">投稿フロー（即時・予約）</a></li>
  <li><a href="#cost">コスト試算</a></li>
  <li><a href="#wordpress">WordPress iframe埋め込み</a></li>
  <li><a href="#setup">セットアップ手順</a></li>
</ol>

<!-- 1. 機能概要 -->
<h1 id="overview" class="page-break">1. 機能概要</h1>

<h2>システム全体図</h2>
<div class="ui-mock">
<pre style="background:white; color:#1a1a1a; text-align:center; font-size:10pt;">
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│  RAG Knowledge  │────▶│  Gemini API  │────▶│  DraftPost   │
│  (ナレッジDB)    │     │  (AI生成)     │     │  (下書き)     │
└─────────────────┘     └──────────────┘     └──────┬───────┘
                                                     │
                                            ┌────────▼────────┐
                                            │  LLM Judge      │
                                            │  (品質評価)      │
                                            └────────┬────────┘
                                                     │
                                          ┌──────────▼──────────┐
                                          │  下書き管理UI        │
                                          │  (編集・承認・投稿)   │
                                          └───┬──────┬──────┬───┘
                                              │      │      │
                                         ┌────▼─┐┌───▼──┐┌──▼───┐
                                         │X API ││Insta ││ GBP  │
                                         │      ││gram  ││      │
                                         └──────┘└──────┘└──────┘
</pre>
</div>

<h2>3つの主要機能</h2>
<table>
  <tr>
    <th>機能</th>
    <th>概要</th>
    <th>技術</th>
  </tr>
  <tr>
    <td><strong>RAGナレッジ</strong></td>
    <td>キャスト情報・店舗情報をDBに蓄積し、AI投稿文の正確性を担保</td>
    <td>KnowledgeEntry モデル</td>
  </tr>
  <tr>
    <td><strong>AI下書き+LLM Judge</strong></td>
    <td>Gemini APIで投稿文を自動生成、品質を自動評価（0〜1.0）</td>
    <td>Gemini 2.0 Flash</td>
  </tr>
  <tr>
    <td><strong>WordPress埋め込み</strong></td>
    <td>予約カレンダー・シフト表示をiframeで外部サイトに埋め込み</td>
    <td>APIキー認証 + CSP</td>
  </tr>
</table>

<!-- 2. RAGナレッジ管理 -->
<h1 id="rag" class="page-break">2. RAGナレッジ管理</h1>

<h2>目的</h2>
<p>AIが正確な投稿文を生成するための「事実データベース」です。キャスト名、得意占術、店舗情報などを登録しておくと、AI生成時に自動参照されます。</p>

<h2>管理画面 UI</h2>
<div class="ui-mock">
  <div class="header">管理画面 → SNS自動投稿 → SNSナレッジ</div>
  <table>
    <tr><th>カテゴリ</th><th>タイトル</th><th>内容（抜粋）</th><th>有効</th></tr>
    <tr><td><span class="badge badge-blue">キャスト</span></td><td>星野 ルナのプロフィール</td><td>タロット・西洋占星術が得意。優しい語りかけで...</td><td>✅</td></tr>
    <tr><td><span class="badge badge-blue">キャスト</span></td><td>月見 アカリのプロフィール</td><td>手相・四柱推命の実力派。的確な鑑定が好評...</td><td>✅</td></tr>
    <tr><td><span class="badge badge-green">店舗情報</span></td><td>店舗基本情報</td><td>占いサロンチャンス高円寺店 / JR高円寺駅徒歩3分...</td><td>✅</td></tr>
    <tr><td><span class="badge badge-orange">サービス</span></td><td>占いメニュー</td><td>タロット、手相、西洋占星術、四柱推命、霊視...</td><td>✅</td></tr>
  </table>
</div>

<h2>カテゴリ一覧</h2>
<table>
  <tr><th>カテゴリ</th><th>用途</th><th>例</th></tr>
  <tr><td>キャストプロフィール</td><td>占い師の情報</td><td>名前、得意占術、紹介文</td></tr>
  <tr><td>店舗情報</td><td>基本情報</td><td>住所、営業時間、最寄駅</td></tr>
  <tr><td>サービス情報</td><td>メニュー詳細</td><td>占術一覧、料金、所要時間</td></tr>
  <tr><td>キャンペーン</td><td>期間限定情報</td><td>初回割引、季節イベント</td></tr>
  <tr><td>カスタム</td><td>自由記入</td><td>注意事項、特記事項</td></tr>
</table>

<h2>RAGコンテキスト構築例</h2>
<p>AI生成時に自動構築される参照テキスト:</p>
<pre>
【店舗情報】
店舗名: 占いサロンチャンス高円寺店
住所: 高円寺南三丁目
営業時間: 11:00-23:00
最寄り駅: JR高円寺駅

【ナレッジベース】
[キャストプロフィール] 星野ルナ: タロット・西洋占星術が得意
[キャストプロフィール] 月見アカリ: 手相・四柱推命の実力派
[サービス情報] タロット、手相、霊視 各30分〜60分

【本日の出勤キャスト】
- 星野 ルナ (9:00-17:00)
- 月見 アカリ (13:00-21:00)
</pre>

<!-- 3. AI下書き生成 + LLM Judge -->
<h1 id="draft" class="page-break">3. AI下書き生成 + LLM Judge評価</h1>

<h2>下書き管理UI</h2>
<div class="ui-mock">
  <div class="header">管理画面 → SNS下書き管理</div>

  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <div>
        <span class="badge badge-blue">生成済み</span>
        <span style="margin-left:8px; font-size:9pt; color:#6b7280;">2026-03-30 | X, Instagram</span>
      </div>
      <div class="score score-mid">0.70</div>
    </div>
    <p style="margin:12px 0;">占いサロンチャンス高円寺店より。本日は星野ルナ先生（タロット・西洋占星術）と水瀬ソラ先生（手相・四柱推命）が出勤。春の新生活、進路や恋愛のお悩みに寄り添います。JR高円寺駅徒歩3分、完全予約制。#占い #高円寺</p>
    <div>
      <code style="background:#dbeafe; color:#1e40af;">📝 編集</code>
      <code style="background:#dcfce7; color:#166534;">▶ 投稿</code>
      <code style="background:#ffedd5; color:#9a3412;">🕐 予約投稿</code>
      <code style="background:#f3e8ff; color:#7c3aed;">🔄 再生成</code>
    </div>
  </div>

  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <div>
        <span class="badge badge-orange">予約済み</span>
        <span style="margin-left:8px; font-size:9pt; color:#6b7280;">2026-03-31 10:00 | X</span>
      </div>
      <div class="score score-mid">0.70</div>
    </div>
    <p style="margin:12px 0;">明日の占いサロンチャンス高円寺店は朝霧ヒカル先生が出勤！霊視とオーラリーディングで心の奥底を照らします。ご予約はお早めに。#占い #高円寺 #霊視</p>
  </div>

  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <div>
        <span class="badge badge-gray">投稿済み</span>
        <span style="margin-left:8px; font-size:9pt; color:#6b7280;">2026-03-29 | X</span>
      </div>
      <div class="score score-high">0.85</div>
    </div>
    <p style="margin:12px 0; color:#6b7280;">占いサロンチャンス高円寺店、本日も元気に営業中！月見アカリ先生のタロット占いが大人気。あなたの2026年の運命は？ #占い #タロット #高円寺</p>
  </div>
</div>

<h2>AI生成フロー</h2>
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>「新規生成」ボタン</strong>をクリック → 店舗・対象日・プラットフォーム（X / Instagram / GBP）を選択</div></div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>RAGコンテキスト自動構築</strong>: ナレッジDB + 当日出勤キャスト情報を統合</div></div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>Gemini 2.0 Flash</strong> が投稿文を生成（280加重文字以内、絵文字付き、CTA含む）</div></div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>LLM Judge</strong> が自動評価（ルールベース + AI評価の複合スコア）</div></div>
<div class="flow-step"><div class="flow-num">5</div><div class="flow-text">下書き一覧に<span class="badge badge-blue">生成済み</span>ステータスで表示</div></div>

<h2>LLM Judge 評価基準</h2>
<table>
  <tr><th>チェック項目</th><th>方式</th><th>配点</th><th>内容</th></tr>
  <tr><td>店舗名チェック</td><td>ルールベース（即時）</td><td>-</td><td>店舗名が含まれているか</td></tr>
  <tr><td>禁止ワード</td><td>ルールベース（即時）</td><td>-</td><td>不適切な表現がないか</td></tr>
  <tr><td>文字数</td><td>ルールベース（即時）</td><td>-</td><td>加重文字数 280以内（X用）</td></tr>
  <tr><td>事実正確性</td><td>LLM Judge（AI）</td><td>30%</td><td>キャスト名・占術が正確か</td></tr>
  <tr><td>文章品質</td><td>LLM Judge（AI）</td><td>30%</td><td>自然で読みやすいか</td></tr>
  <tr><td>集客効果</td><td>LLM Judge（AI）</td><td>20%</td><td>来店意欲を喚起できるか</td></tr>
  <tr><td>プラットフォーム適合</td><td>LLM Judge（AI）</td><td>20%</td><td>X/Instagram/GBPの特性に合っているか</td></tr>
</table>

<h2>品質スコアの目安</h2>
<table>
  <tr><th>スコア</th><th>評価</th><th>推奨アクション</th></tr>
  <tr><td><span class="score-high" style="font-weight:bold;">0.80〜1.00</span></td><td>高品質</td><td>そのまま投稿OK</td></tr>
  <tr><td><span class="score-mid" style="font-weight:bold;">0.60〜0.79</span></td><td>標準</td><td>確認後投稿、必要に応じ微修正</td></tr>
  <tr><td><span class="score-low" style="font-weight:bold;">0.00〜0.59</span></td><td>要改善</td><td>手動編集 or 再生成を推奨</td></tr>
</table>

<!-- 4. 投稿フロー -->
<h1 id="posting" class="page-break">4. 投稿フロー</h1>

<h2>即時投稿</h2>
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text">下書き一覧で「<strong>▶ 投稿</strong>」ボタンをクリック</div></div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text">プラットフォーム確認画面 → 「投稿する」で実行</div></div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text">X: API経由で即座に投稿 / Instagram・GBP: ブラウザ自動投稿</div></div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text">ステータスが<span class="badge badge-gray">投稿済み</span>に変更</div></div>

<h2>予約投稿</h2>
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text">下書き一覧で「<strong>🕐 予約投稿</strong>」ボタンをクリック</div></div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text">投稿日時をカレンダーピッカーで指定</div></div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text">ステータスが<span class="badge badge-orange">予約済み</span>に変更</div></div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text">Celery Beat が5分ごとにチェック → 時刻到達で自動投稿</div></div>

<h2>自動生成スケジュール</h2>
<div class="info">
  <strong>毎日 08:00</strong> に Celery Beat が全店舗の下書きを自動AI生成します。<br>
  管理者は出勤後にチェック → 承認 → 投稿/予約投稿 の流れです。
</div>

<h2>プラットフォーム別投稿方式</h2>
<table>
  <tr><th>Platform</th><th>方式</th><th>認証</th><th>制限</th></tr>
  <tr><td><strong>X (Twitter)</strong></td><td>API v2 (OAuth 2.0 PKCE)</td><td>管理画面でOAuth連携</td><td>月500件 (Free)</td></tr>
  <tr><td><strong>Instagram</strong></td><td>ブラウザ自動投稿 (Playwright)</td><td>初回手動ログイン</td><td>1日1〜2件推奨</td></tr>
  <tr><td><strong>Google Business Profile</strong></td><td>ブラウザ自動投稿 (Playwright)</td><td>初回手動ログイン</td><td>1日1件推奨</td></tr>
</table>

<!-- 5. コスト試算 -->
<h1 id="cost" class="page-break">5. コスト試算</h1>

<h2>月間コスト概算（1店舗・1日1投稿の場合）</h2>
<table>
  <tr><th>項目</th><th>単価</th><th>月間使用量</th><th>月額</th></tr>
  <tr><td>Gemini 2.0 Flash（AI生成）</td><td>無料枠: 100万トークン/日</td><td>~30回 × 1,000トークン</td><td><strong>¥0</strong></td></tr>
  <tr><td>Gemini 2.0 Flash（LLM Judge）</td><td>同上</td><td>~30回 × 500トークン</td><td><strong>¥0</strong></td></tr>
  <tr><td>X API Free Tier</td><td>無料（月500件）</td><td>~30件</td><td><strong>¥0</strong></td></tr>
  <tr><td>Playwright (OSS)</td><td>無料</td><td>-</td><td><strong>¥0</strong></td></tr>
  <tr><td>EC2 (t3.micro) ※既存</td><td>~$8.5/月</td><td>常時稼働</td><td><strong>~¥1,300</strong> (既存費用)</td></tr>
  <tr style="background:#ecfdf5; font-weight:bold;">
    <td colspan="3">追加コスト合計</td><td>¥0</td>
  </tr>
</table>

<div class="success">
  <strong>結論:</strong> 現在の利用規模（1店舗・1日1投稿）では<strong>追加コストゼロ</strong>で運用できます。<br>
  Gemini API の無料枠（15 RPM / 100万トークン/日）、X API Free（月500件）の範囲内です。
</div>

<h2>スケールアップ時のコスト</h2>
<table>
  <tr><th>規模</th><th>Gemini API</th><th>X API</th><th>月額追加</th></tr>
  <tr><td>1店舗 × 1日1投稿</td><td>無料枠内</td><td>Free (500/月)</td><td>¥0</td></tr>
  <tr><td>5店舗 × 1日1投稿</td><td>無料枠内</td><td>Free (500/月)</td><td>¥0</td></tr>
  <tr><td>10店舗 × 1日2投稿</td><td>Pay-as-you-go (~$0.01)</td><td>Basic ($100/月)</td><td>~¥15,000</td></tr>
</table>

<!-- 6. WordPress iframe埋め込み -->
<h1 id="wordpress" class="page-break">6. WordPress iframe埋め込み</h1>

<h2>概要</h2>
<p>Timebaibai の予約カレンダーやシフト表示を、WordPressサイトに iframe で埋め込めます。<br>
<strong>timebaibai.com 本体には一切影響ありません。</strong></p>

<div class="ui-mock">
  <div class="header">WordPress ページでの表示イメージ</div>
  <div style="padding: 20px; text-align:center;">
    <p style="text-align:left; font-size:14pt; font-weight:bold;">占いサロンチャンス 予約ページ</p>
    <p style="text-align:left; color:#6b7280;">お好きな占い師と日時をお選びください。</p>
    <div class="embed-demo">
      <div style="font-size:14pt; font-weight:bold;">📅 予約カレンダー</div>
      <div style="margin-top:10px; color:#6b7280;">← iframe で Timebaibai の予約画面が表示されます →</div>
      <div style="margin-top:10px; font-size:9pt;">https://timebaibai.com/embed/booking/1/?api_key=xxxxx</div>
    </div>
  </div>
</div>

<h2>セットアップ手順</h2>

<h3>Step 1: Timebaibai 管理画面で有効化</h3>
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text">管理画面 → <strong>メインサイト設定</strong> → 「外部埋め込みを有効化」を <strong>ON</strong></div></div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text">管理画面 → <strong>店舗一覧</strong> → 対象店舗を選択</div></div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text">アクション「<strong>埋め込みAPIキーを生成</strong>」を実行 → 64文字のキーが発行されます</div></div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text">（推奨）「埋め込み許可ドメイン」に WordPress のドメインを入力（例: <code>example.com</code>）</div></div>

<h3>Step 2: WordPress にショートコードを追加</h3>
<p>テーマの <code>functions.php</code> に以下を追加:</p>
<pre>
// 予約カレンダー埋め込み
function newfuhi_booking_shortcode($atts) {
    $atts = shortcode_atts(array(
        'store_id' => '1',
        'api_key'  => '',
        'height'   => '600',
        'width'    => '100%',
    ), $atts, 'newfuhi_booking');

    $src = esc_url(
      "https://timebaibai.com/embed/booking/"
      . intval($atts['store_id'])
      . "/?api_key=" . sanitize_text_field($atts['api_key'])
    );

    return '&lt;iframe src="' . $src . '" width="'
      . esc_attr($atts['width']) . '" height="'
      . esc_attr($atts['height'])
      . '" style="border:none; max-width:100%;"
      loading="lazy"&gt;&lt;/iframe&gt;';
}
add_shortcode('newfuhi_booking', 'newfuhi_booking_shortcode');
</pre>

<h3>Step 3: ページにショートコードを記述</h3>
<pre>
[newfuhi_booking store_id="1" api_key="ここにAPIキーを貼り付け"]
[newfuhi_shift store_id="1" api_key="ここにAPIキーを貼り付け"]
</pre>

<h3>Step 3（代替）: HTML直接埋め込み</h3>
<p>WordPress のカスタム HTML ブロック等で:</p>
<pre>
&lt;iframe
  src="https://timebaibai.com/embed/booking/1/?api_key=YOUR_API_KEY"
  width="100%"
  height="600"
  style="border: none; max-width: 100%;"
  loading="lazy"
  title="予約カレンダー"
&gt;&lt;/iframe&gt;
</pre>

<h2>利用可能な埋め込みURL</h2>
<table>
  <tr><th>URL</th><th>表示内容</th><th>用途</th></tr>
  <tr><td><code>/embed/booking/&lt;store_id&gt;/</code></td><td>予約カレンダー</td><td>顧客が予約スロットを選択・予約</td></tr>
  <tr><td><code>/embed/shift/&lt;store_id&gt;/</code></td><td>本日のシフト</td><td>出勤キャスト一覧を公開表示</td></tr>
</table>

<h2>セキュリティ</h2>
<table>
  <tr><th>脅威</th><th>対策</th></tr>
  <tr><td>APIキーなし/不正</td><td>403 Forbidden を返却</td></tr>
  <tr><td>埋め込み無効時</td><td>404 Not Found を返却</td></tr>
  <tr><td>不正ドメインからの埋め込み</td><td>CSP <code>frame-ancestors</code> ヘッダーで制限</td></tr>
  <tr><td>他ページのiframe表示</td><td><code>X-Frame-Options: DENY</code> を維持（embed以外）</td></tr>
</table>

<!-- 7. セットアップ手順 -->
<h1 id="setup" class="page-break">7. 初期セットアップ手順</h1>

<h2>SNS自動投稿の初期設定</h2>
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Gemini API キー設定</strong>: <a href="https://aistudio.google.com">aistudio.google.com</a> でAPIキー取得 → EC2の<code>.env</code>に<code>GEMINI_API_KEY=xxx</code>を追加</div></div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>ナレッジ登録</strong>: 管理画面 → SNSナレッジ → キャスト情報・店舗情報・サービス情報を登録</div></div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>下書き生成テスト</strong>: SNS下書き管理 → 新規生成 → AI生成を確認</div></div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>X OAuth連携</strong>（任意）: SNSアカウント → X連携 → OAuth認証フロー実行</div></div>
<div class="flow-step"><div class="flow-num">5</div><div class="flow-text"><strong>投稿テスト</strong>: 下書き → 投稿ボタン → X に投稿されることを確認</div></div>

<h2>日常運用フロー</h2>
<div class="info">
  <strong>毎朝の流れ（5分で完了）</strong><br>
  08:00 Celery が自動で下書き生成 → 管理者がチェック → 承認して投稿/予約投稿
</div>

<div class="note">
  <strong>注意事項</strong><br>
  • Gemini API 無料枠: 15リクエスト/分、100万トークン/日<br>
  • X API Free: 月500件まで（超過時は翌月リセット）<br>
  • Instagram/GBP ブラウザ投稿: 1日1〜2件推奨（BAN防止）<br>
  • ブラウザ投稿を使う場合、EC2にPlaywrightのインストールが必要
</div>

</body>
</html>"""

def main():
    from weasyprint import HTML
    import os

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, 'timebaibai_feature_guide.pdf')

    print('Generating PDF...')
    HTML(string=HTML_CONTENT).write_pdf(output_path)
    print(f'Done: {output_path}')

if __name__ == '__main__':
    main()
