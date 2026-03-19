#!/usr/bin/env python3
"""
NewFUHI システム仕様書 HTML → PDF 生成スクリプト

Usage:
    pip install weasyprint
    python docs/generate_system_spec.py

出力:
    docs/system_specification.html  — HTML仕様書
    docs/system_specification.pdf   — WeasyPrint PDF
"""
import os
import subprocess
import sys
import datetime

# macOS Homebrew: WeasyPrint が libgobject を見つけるために DYLD_LIBRARY_PATH を設定
_brew_prefix = subprocess.run(
    ['brew', '--prefix'], capture_output=True, text=True,
).stdout.strip() if sys.platform == 'darwin' else ''
if _brew_prefix:
    lib_path = os.path.join(_brew_prefix, 'lib')
    os.environ['DYLD_LIBRARY_PATH'] = lib_path + ':' + os.environ.get('DYLD_LIBRARY_PATH', '')

# Django セットアップ
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings.local')

import django
django.setup()

from django.apps import apps
from django.urls import get_resolver


def collect_models():
    """booking アプリの全モデル情報を収集"""
    models_info = []
    app_models = apps.get_app_config('booking').get_models()
    for model in app_models:
        fields = []
        for field in model._meta.get_fields():
            if hasattr(field, 'column'):
                field_info = {
                    'name': field.name,
                    'type': field.get_internal_type(),
                    'null': getattr(field, 'null', False),
                    'blank': getattr(field, 'blank', False),
                    'unique': getattr(field, 'unique', False),
                    'db_index': getattr(field, 'db_index', False),
                    'default': repr(field.default) if field.default is not None and str(field.default) != 'django.db.models.fields.NOT_PROVIDED' else '',
                    'help_text': str(getattr(field, 'help_text', '')),
                    'verbose_name': str(getattr(field, 'verbose_name', field.name)),
                }
                if hasattr(field, 'related_model') and field.related_model:
                    field_info['fk_to'] = field.related_model.__name__
                fields.append(field_info)

        indexes = []
        for idx in model._meta.indexes:
            indexes.append(', '.join(idx.fields))

        unique_together = []
        for ut in model._meta.unique_together:
            unique_together.append(', '.join(ut))

        models_info.append({
            'name': model.__name__,
            'verbose_name': str(model._meta.verbose_name),
            'db_table': model._meta.db_table,
            'fields': fields,
            'indexes': indexes,
            'unique_together': unique_together,
        })
    return models_info


def collect_url_patterns(resolver=None, prefix=''):
    """全 URL パターンを収集"""
    if resolver is None:
        resolver = get_resolver()
    patterns = []
    for pattern in resolver.url_patterns:
        if hasattr(pattern, 'url_patterns'):
            pat = prefix + str(getattr(pattern.pattern, '_route', str(pattern.pattern)))
            patterns.extend(collect_url_patterns(pattern, pat))
        else:
            pat = prefix + str(getattr(pattern.pattern, '_route', str(pattern.pattern)))
            name = getattr(pattern, 'name', '') or ''
            view_name = ''
            if hasattr(pattern, 'callback'):
                cb = pattern.callback
                if hasattr(cb, 'view_class'):
                    view_name = cb.view_class.__name__
                elif hasattr(cb, '__name__'):
                    view_name = cb.__name__
            patterns.append({
                'url': '/' + pat,
                'name': name,
                'view': view_name,
            })
    return patterns


def _field_badge(field_type):
    """フィールド型に応じたバッジHTML"""
    badge_map = {
        'AutoField': 'badge-pk',
        'BigAutoField': 'badge-pk',
        'ForeignKey': 'badge-fk',
        'OneToOneField': 'badge-fk',
        'BooleanField': 'badge-bool',
        'NullBooleanField': 'badge-bool',
        'CharField': 'badge-char',
        'TextField': 'badge-char',
        'EmailField': 'badge-char',
        'URLField': 'badge-char',
        'SlugField': 'badge-char',
        'UUIDField': 'badge-char',
        'IntegerField': 'badge-int',
        'FloatField': 'badge-int',
        'DecimalField': 'badge-int',
        'DateTimeField': 'badge-dt',
        'DateField': 'badge-dt',
        'TimeField': 'badge-dt',
    }
    css = badge_map.get(field_type, 'badge-char')
    return f'<span class="badge {css}">{field_type}</span>'


def generate_html():
    """HTML 仕様書を生成"""
    models = collect_models()
    urls = collect_url_patterns()
    today = datetime.date.today().strftime('%Y年%m月%d日')

    # サービスモジュール一覧
    services = [
        ('payroll_calculator.py', '給与計算エンジン', '源泉徴収税テーブル参照、社会保険料計算、基本給・割増・手当計算、PayrollEntry/Deduction生成'),
        ('attendance_service.py', '勤怠導出サービス', 'ShiftAssignment→WorkAttendance変換、法定休憩計算、労働時間分類(通常/残業/深夜/休日)'),
        ('shift_scheduler.py', '自動スケジューリング', 'カバレッジベースShiftRequest→ShiftAssignment変換(定員/preferred優先)、最低勤務時間チェック、不足枠自動生成、Schedule同期'),
        ('shift_coverage.py', 'カバレッジ計算ヘルパー', 'カバレッジマップ構築、定員充足判定、不足時間カウント、不足枠(ShiftVacancy)生成'),
        ('shift_notifications.py', 'シフト通知サービス', 'LINE/メール通知: 募集開始、承認完了、欠勤申請、カバー募集、交代依頼'),
        ('zengin_export.py', '全銀フォーマットCSV生成', 'PayrollPeriod→全銀CSV(ヘッダー/データ/トレーラー/エンド)'),
        ('ai_chat.py', 'AIチャットサービス', 'Gemini API + RAGナレッジベース(管理画面ガイド/予約ガイド)'),
        ('qr_service.py', 'QRコード生成', '予約チェックインQR、テーブル注文QR'),
    ]

    # Celeryタスク一覧
    tasks = [
        ('delete_temporary_schedules', '毎分', '10分超の仮予約を削除'),
        ('trigger_gas_alert', 'イベント駆動', 'MQ-9閾値超過時にメール送信'),
        ('check_low_stock_and_notify', '1時間ごと', '在庫閾値割れ商品のLINE通知(24h重複スキップ)'),
        ('check_property_alerts', '5分ごと', '物件アラート検知(ガス漏れ/長期不在/デバイスオフライン)'),
        ('run_security_audit', '毎日03:00', 'セキュリティ自己診断(12項目)'),
        ('cleanup_security_logs', '毎週日曜04:00', '90日超セキュリティログ削除'),
        ('check_aws_costs', '毎日06:00', 'AWSコスト最適化チェック(6項目)'),
    ]

    # 管理コマンド一覧
    commands = [
        ('bootstrap_admin_staff', '--username, --store_id, --manager, --developer', '管理者スタッフの初期作成/更新'),
        ('cancel_expired_temp_bookings', '(引数なし)', '15分超の仮予約を自動キャンセル'),
        ('security_audit', '--json, --verbose, --category', 'セキュリティ自己診断実行(12チェック)'),
        ('cleanup_security_logs', '--days (default: 90)', '古いセキュリティログを削除'),
        ('check_aws_costs', '--threshold, --json, --region', 'AWSコスト監視(EC2/S3/EBS/EIP/RDS)'),
    ]

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NewFUHI システム仕様書</title>
<style>
@page {{
  size: A4;
  margin: 20mm 15mm 25mm 15mm;
  @top-center {{ content: "NewFUHI システム仕様書"; font-size: 9pt; color: #666; }}
  @bottom-center {{ content: "— " counter(page) " —"; font-size: 9pt; color: #666; }}
}}
* {{ box-sizing: border-box; }}
body {{ font-family: "Hiragino Kaku Gothic ProN","Noto Sans JP","Noto Sans CJK JP",sans-serif; font-size: 10pt; line-height: 1.7; color: #222; max-width: 100%; margin: 0; padding: 0; }}
h1 {{ font-size: 22pt; color: #1a3a5c; border-bottom: 3px solid #1a3a5c; padding-bottom: 8px; page-break-before: always; margin-top: 0; }}
h1:first-of-type {{ page-break-before: avoid; }}
h2 {{ font-size: 14pt; color: #2c5282; border-bottom: 1.5px solid #bee3f8; padding-bottom: 4px; margin-top: 24px; }}
h3 {{ font-size: 11pt; color: #2b6cb0; margin-top: 18px; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0 16px 0; font-size: 9pt; }}
th, td {{ border: 1px solid #cbd5e0; padding: 5px 8px; text-align: left; word-break: break-all; }}
th {{ background: #ebf4ff; font-weight: bold; color: #2c5282; }}
tr:nth-child(even) {{ background: #f7fafc; }}
code {{ background: #edf2f7; padding: 1px 4px; border-radius: 3px; font-size: 8.5pt; font-family: "SF Mono","Menlo",monospace; }}
pre {{ background: #1a202c; color: #e2e8f0; padding: 12px; border-radius: 6px; font-size: 8pt; line-height: 1.5; overflow-x: auto; white-space: pre-wrap; word-break: break-all; }}
pre code {{ background: none; color: inherit; padding: 0; }}
.cover {{ text-align: center; padding: 120px 0 60px 0; page-break-after: always; }}
.cover h1 {{ font-size: 32pt; border: none; page-break-before: avoid; }}
.cover .subtitle {{ font-size: 14pt; color: #4a5568; margin-top: 16px; }}
.cover .date {{ font-size: 11pt; color: #718096; margin-top: 40px; }}
.toc {{ page-break-after: always; }}
.toc h1 {{ page-break-before: avoid; }}
.toc ol {{ font-size: 11pt; line-height: 2.2; }}
.note {{ background: #fffbeb; border-left: 4px solid #f6ad55; padding: 10px 14px; margin: 10px 0; font-size: 9pt; }}
.info {{ background: #ebf8ff; border-left: 4px solid #63b3ed; padding: 10px 14px; margin: 10px 0; font-size: 9pt; }}
ul, ol {{ margin: 6px 0; padding-left: 24px; }}
li {{ margin: 2px 0; }}
.badge {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 8pt; font-weight: bold; color: #fff; }}
.badge-pk {{ background: #e53e3e; }}
.badge-fk {{ background: #3182ce; }}
.badge-bool {{ background: #38a169; }}
.badge-char {{ background: #805ad5; }}
.badge-int {{ background: #d69e2e; }}
.badge-dt {{ background: #dd6b20; }}
.arch-diagram {{ background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 16px 0; font-family: monospace; font-size: 8pt; white-space: pre; line-height: 1.4; }}
@media print {{
  h1, h2, h3 {{ page-break-after: avoid; }}
  table, pre {{ page-break-inside: avoid; }}
}}
</style>
</head>
<body>

<!-- 表紙 -->
<div class="cover">
<h1>NewFUHI<br>システム仕様書</h1>
<p class="subtitle">占いサロン管理プラットフォーム — Django + IoT + AWS</p>
<p class="date">Version 1.1 — {today}</p>
<p style="margin-top:60px;color:#a0aec0;font-size:10pt;">Confidential — 社内技術資料</p>
</div>

<!-- 目次 -->
<div class="toc">
<h1>目次</h1>
<ol>
<li>ドキュメント管理</li>
<li>エグゼクティブサマリ</li>
<li>システムアーキテクチャ</li>
<li>データベーススキーマ</li>
<li>API リファレンス</li>
<li>画面マップ（URLパターン一覧）</li>
<li>サービスレイヤ仕様</li>
<li>バックグラウンドタスク仕様</li>
<li>セキュリティアーキテクチャ</li>
<li>外部連携仕様</li>
<li>デプロイアーキテクチャ</li>
<li>付録</li>
</ol>
</div>

<!-- 1. ドキュメント管理 -->
<h1>1. ドキュメント管理</h1>
<table>
<tr><th>項目</th><th>内容</th></tr>
<tr><td>文書名</td><td>NewFUHI システム仕様書</td></tr>
<tr><td>バージョン</td><td>1.1</td></tr>
<tr><td>最終更新日</td><td>{today}</td></tr>
<tr><td>作成者</td><td>開発チーム</td></tr>
<tr><td>機密区分</td><td>社内限定</td></tr>
</table>

<h2>改訂履歴</h2>
<table>
<tr><th>バージョン</th><th>日付</th><th>変更内容</th></tr>
<tr><td>1.0</td><td>2026-03-18</td><td>初版作成</td></tr>
<tr><td>1.1</td><td>{today}</td><td>シフト改善: カバレッジベース自動配置、不足枠(ShiftVacancy)、交代・欠勤申請(ShiftSwapRequest)、最低勤務時間追加</td></tr>
</table>

<!-- 2. エグゼクティブサマリ -->
<h1>2. エグゼクティブサマリ</h1>
<p>NewFUHI は占いサロン・飲食店を対象とした統合管理プラットフォームです。以下の主要機能を提供します:</p>
<ul>
<li><strong>予約管理</strong>: LINE OAuth / Email OTP による予約フロー、Coiney決済連携</li>
<li><strong>テーブル注文</strong>: QRコードスキャンによるモバイルオーダー</li>
<li><strong>ECショップ</strong>: オンライン商品販売（在庫連動）</li>
<li><strong>IoTデバイス管理</strong>: Raspberry Pi Pico + センサーデータ収集、ガスアラート</li>
<li><strong>物件監視</strong>: IoTセンサーによる物件異常検知（ガス漏れ/長期不在/オフライン）</li>
<li><strong>シフト・勤怠管理</strong>: シフト希望→自動スケジューリング→勤怠記録→給与計算</li>
<li><strong>在庫管理</strong>: 入庫QR / 出庫（注文連動） / 閾値アラート</li>
<li><strong>セキュリティ監査</strong>: 12項目自己診断、ログ監視、AWSコスト監視</li>
<li><strong>多言語対応</strong>: 7言語（日本語/英語/繁体字/簡体字/韓国語/スペイン語/ポルトガル語）</li>
<li><strong>CMS</strong>: ヒーローバナー、カスタムブロック、バナー広告</li>
</ul>

<h2>技術スタック</h2>
<table>
<tr><th>レイヤー</th><th>技術</th></tr>
<tr><td>バックエンド</td><td>Django 4.x / Django REST Framework / Python 3</td></tr>
<tr><td>タスクキュー</td><td>Celery + Redis</td></tr>
<tr><td>データベース</td><td>SQLite(開発) / PostgreSQL(本番)</td></tr>
<tr><td>認証</td><td>Django Auth + LINE OAuth2 + Email OTP</td></tr>
<tr><td>暗号化</td><td>cryptography (Fernet)</td></tr>
<tr><td>IoT通信</td><td>HTTPS REST API (X-API-KEY認証)</td></tr>
<tr><td>決済</td><td>Coiney (クレジットカード)</td></tr>
<tr><td>AI</td><td>Google Gemini API (RAGチャット)</td></tr>
<tr><td>Webサーバー</td><td>Nginx + Gunicorn</td></tr>
<tr><td>CI/CD</td><td>GitHub Actions</td></tr>
</table>

<!-- 3. システムアーキテクチャ -->
<h1>3. システムアーキテクチャ</h1>

<h2>3.1 全体構成図</h2>
<div class="arch-diagram">
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  LINE App   │────▶│   Nginx      │────▶│  Gunicorn   │
│  (OAuth)    │     │  (Reverse    │     │  (Django)   │
└─────────────┘     │   Proxy)     │     └──────┬──────┘
                    └──────────────┘            │
┌─────────────┐            │              ┌────▼─────┐
│  Browser    │────────────┘              │ Celery   │
│  (Customer/ │                           │ Worker   │
│   Admin)    │                           └────┬─────┘
└─────────────┘                                │
                                          ┌────▼─────┐
┌─────────────┐     ┌──────────────┐     │  Redis   │
│  Pico W     │────▶│  /api/iot/   │     │  (Broker)│
│  (IoT)      │     │  event/      │     └──────────┘
└─────────────┘     └──────────────┘
                                          ┌──────────┐
                    ┌──────────────┐     │PostgreSQL│
                    │  Coiney API  │     │  (DB)    │
                    │  (決済)      │     └──────────┘
                    └──────────────┘
                                          ┌──────────┐
                    ┌──────────────┐     │  AWS S3  │
                    │  Gemini API  │     │ (Media)  │
                    │  (AIチャット)│     └──────────┘
                    └──────────────┘
</div>

<h2>3.2 コンポーネント図</h2>
<div class="arch-diagram">
booking/
├── models.py          ← 68モデル（データ層）
├── views.py           ← ビュー/API（プレゼンテーション層）
├── views_property.py  ← 物件管理ビュー
├── views_debug.py     ← デバッグパネル
├── views_restaurant_dashboard.py ← レストランダッシュボード
├── middleware.py       ← セキュリティ監視ミドルウェア
├── tasks.py           ← Celeryタスク（7タスク）
├── services/
│   ├── payroll_calculator.py  ← 給与計算エンジン
│   ├── attendance_service.py  ← 勤怠導出サービス
│   ├── shift_scheduler.py     ← 自動スケジューリング
│   ├── shift_notifications.py ← シフト通知
│   ├── zengin_export.py       ← 全銀CSV生成
│   ├── ai_chat.py             ← AIチャット(Gemini RAG)
│   └── qr_service.py          ← QRコード生成
├── management/commands/
│   ├── bootstrap_admin_staff.py
│   ├── cancel_expired_temp_bookings.py
│   ├── security_audit.py
│   ├── cleanup_security_logs.py
│   └── check_aws_costs.py
└── admin_site.py      ← カスタム管理サイト
</div>

<h2>3.3 データフロー図</h2>

<h3>予約フロー</h3>
<div class="arch-diagram">
Customer ──▶ BookingTopPage ──▶ StaffCalendar ──▶ PreBooking
    │                                                    │
    ├── LINE OAuth ──▶ LineEnterView ──▶ LineCallbackView ──▶ Schedule(is_temporary=True)
    │                                                              │
    │                                                    ┌────────▼────────┐
    │                                                    │ price >= 100?   │
    │                                                    └──┬───────────┬──┘
    │                                                  Yes  │           │ No
    │                                                       ▼           ▼
    │                                                Coiney決済URL    直接確定
    │                                                       │     (is_temporary=False)
    │                                                       ▼
    │                                                coiney_webhook
    │                                                       │
    │                                                       ▼
    └── Email OTP ──▶ EmailBookingView ──▶ EmailVerifyView ──▶ Schedule確定 + QR生成
</div>

<!-- 4. データベーススキーマ -->
<h1>4. データベーススキーマ</h1>
<p>booking アプリには <strong>{len(models)} モデル</strong>が定義されています。</p>
'''

    for i, model in enumerate(models, start=1):
        html += f'\n<h2>4.{i} {model["name"]}</h2>\n'
        html += f'<p><strong>テーブル名</strong>: <code>{model["db_table"]}</code> | <strong>表示名</strong>: {model["verbose_name"]}</p>\n'

        if model['fields']:
            html += '<table>\n<tr><th>フィールド名</th><th>型</th><th>NULL</th><th>索引</th><th>説明</th></tr>\n'
            for f in model['fields']:
                null_str = 'Yes' if f['null'] else ''
                idx_str = []
                if f.get('unique'):
                    idx_str.append('UNIQUE')
                if f.get('db_index'):
                    idx_str.append('INDEX')
                fk_info = f' → {f["fk_to"]}' if f.get('fk_to') else ''
                html += f'<tr><td><code>{f["name"]}</code></td><td>{_field_badge(f["type"])}{fk_info}</td><td>{null_str}</td><td>{" ".join(idx_str)}</td><td>{f["verbose_name"]}</td></tr>\n'
            html += '</table>\n'

        if model['indexes']:
            html += '<p><strong>複合インデックス</strong>: ' + ' | '.join(f'({idx})' for idx in model['indexes']) + '</p>\n'
        if model['unique_together']:
            html += '<p><strong>ユニーク制約</strong>: ' + ' | '.join(f'({ut})' for ut in model['unique_together']) + '</p>\n'

    # 5. API リファレンス
    api_urls = [u for u in urls if '/api/' in u['url']]
    html += '''
<!-- 5. API リファレンス -->
<h1>5. API リファレンス</h1>
<p>REST API エンドポイント一覧:</p>
<table>
<tr><th>URL</th><th>名前</th><th>ビュー</th></tr>
'''
    for u in api_urls:
        html += f'<tr><td><code>{u["url"]}</code></td><td>{u["name"]}</td><td>{u["view"]}</td></tr>\n'
    html += '</table>\n'

    # 6. 画面マップ
    html += '''
<!-- 6. 画面マップ -->
<h1>6. 画面マップ（URLパターン一覧）</h1>
<table>
<tr><th>URL</th><th>名前</th><th>ビュー</th></tr>
'''
    for u in urls:
        html += f'<tr><td><code>{u["url"]}</code></td><td>{u["name"]}</td><td>{u["view"]}</td></tr>\n'
    html += '</table>\n'

    # 7. サービスレイヤ仕様
    html += '''
<!-- 7. サービスレイヤ仕様 -->
<h1>7. サービスレイヤ仕様</h1>
<table>
<tr><th>モジュール</th><th>名称</th><th>機能概要</th></tr>
'''
    for svc in services:
        html += f'<tr><td><code>{svc[0]}</code></td><td>{svc[1]}</td><td>{svc[2]}</td></tr>\n'
    html += '</table>\n'

    html += '''
<h2>7.1 給与計算エンジン (payroll_calculator.py)</h2>
<h3>処理フロー</h3>
<ol>
<li>期間内の WorkAttendance 集計（通常/残業/深夜/休日の各分数）</li>
<li>総支給額計算: 基本給 + 残業手当(×1.25) + 深夜手当(×1.35) + 休日手当(×1.50) + 各種手当</li>
<li>社会保険料計算: 標準報酬月額 × 各料率（厚生年金/健康保険/雇用保険/介護保険/労災）</li>
<li>源泉徴収税: 課税対象額（総支給 - 社保 - 非課税通勤手当）から月額表参照</li>
<li>住民税: 固定月額加算</li>
<li>PayrollEntry + PayrollDeduction レコード生成（update_or_create で冪等）</li>
</ol>

<h2>7.2 勤怠導出サービス (attendance_service.py)</h2>
<ul>
<li>法定休憩: 6h以上→60分、4.5h以上→45分、それ以下→0分</li>
<li>深夜帯: 22:00〜05:00</li>
<li>法定労働: 1日8時間超は残業</li>
<li>休日: 日曜日（weekday==6）</li>
</ul>

<h2>7.3 自動スケジューリング (shift_scheduler.py) — v1.1 カバレッジベース</h2>
<ul>
<li>ShiftStaffRequirement（定員）を時間帯ごとに適用</li>
<li>ShiftRequest(preferred) → 最優先割り当て（定員超過でも緩和判定）</li>
<li>ShiftRequest(available) → カバレッジ不足時のみ割り当て</li>
<li>ShiftRequest(unavailable) → 除外</li>
<li>営業時間外リクエストのクリッピング（営業時間内に自動調整）</li>
<li>最低連続勤務時間チェック（StoreScheduleConfig.min_shift_hours）</li>
<li>不足枠(ShiftVacancy)自動生成: 定員未達の連続時間帯をマージ</li>
<li>Schedule同期: slot_durationに応じてShiftAssignment→Schedule分割</li>
</ul>

<h2>7.4 カバレッジ計算ヘルパー (shift_coverage.py) — v1.1 新規</h2>
<ul>
<li><code>build_coverage_map()</code>: {date → {staff_type → {hour → [staff_ids]}}} マップ構築</li>
<li><code>record_assignment()</code>: アサインをマップに記録</li>
<li><code>check_coverage_need()</code>: リクエスト時間帯に定員未達の時間があるか判定</li>
<li><code>count_coverage_hours()</code>: 不足時間数のカウント</li>
<li><code>generate_vacancies()</code>: 不足枠レコード生成（連続時間マージ）</li>
</ul>
'''

    # 8. バックグラウンドタスク仕様
    html += '''
<!-- 8. バックグラウンドタスク仕様 -->
<h1>8. バックグラウンドタスク仕様</h1>
<table>
<tr><th>タスク名</th><th>スケジュール</th><th>機能</th></tr>
'''
    for t in tasks:
        html += f'<tr><td><code>{t[0]}</code></td><td>{t[1]}</td><td>{t[2]}</td></tr>\n'
    html += '</table>\n'

    # 9. セキュリティアーキテクチャ
    html += '''
<!-- 9. セキュリティアーキテクチャ -->
<h1>9. セキュリティアーキテクチャ</h1>

<h2>9.1 認証方式</h2>
<table>
<tr><th>認証方式</th><th>対象</th><th>実装</th></tr>
<tr><td>Django Auth (セッション)</td><td>管理画面、マイページ</td><td>LoginView + SessionMiddleware</td></tr>
<tr><td>LINE OAuth2</td><td>顧客予約</td><td>LineEnterView → LineCallbackView (PKCE)</td></tr>
<tr><td>Email OTP</td><td>メール予約</td><td>6桁OTP、SHA-256ハッシュ保存、10分有効</td></tr>
<tr><td>API Key (SHA-256)</td><td>IoTデバイス</td><td>X-API-KEY ヘッダー、ハッシュ照合</td></tr>
<tr><td>DRF IsAuthenticated</td><td>管理API</td><td>Token/Session認証</td></tr>
</table>

<h2>9.2 暗号化</h2>
<table>
<tr><th>対象</th><th>方式</th><th>設定キー</th></tr>
<tr><td>LINE user_id</td><td>Fernet (AES-128-CBC)</td><td>LINE_USER_ID_ENCRYPTION_KEY</td></tr>
<tr><td>LINE user_id 検索</td><td>SHA-256 + pepper</td><td>LINE_USER_ID_HASH_PEPPER</td></tr>
<tr><td>IoT Wi-Fiパスワード</td><td>Fernet</td><td>IOT_ENCRYPTION_KEY</td></tr>
<tr><td>IoT APIキー</td><td>SHA-256 (不可逆)</td><td>—</td></tr>
</table>

<h2>9.3 セキュリティ監視</h2>
<ul>
<li><strong>SecurityAuditMiddleware</strong>: 全リクエスト監視
  <ul>
  <li>ログイン成功/失敗検知</li>
  <li>API認証失敗検知 (/api/ パスで 401/403)</li>
  <li>権限拒否検知 (非API 403)</li>
  <li>レートリミット: 同一IPから60秒以内に100リクエスト超</li>
  </ul>
</li>
<li><strong>security_audit コマンド</strong>: 12項目自己診断
  <ul>
  <li>DEBUG設定、SECRET_KEY強度、ALLOWED_HOSTS</li>
  <li>HSTS/SSL、Cookie Security、X-Frame-Options</li>
  <li>決済API鍵暗号化、ミドルウェア構成</li>
  <li>Django バージョン、.env権限、バックアップ鮮度</li>
  </ul>
</li>
</ul>
'''

    # 10. 外部連携仕様
    html += '''
<!-- 10. 外部連携仕様 -->
<h1>10. 外部連携仕様</h1>

<h2>10.1 LINE Messaging API</h2>
<table>
<tr><th>機能</th><th>API</th><th>用途</th></tr>
<tr><td>OAuth2認証</td><td>access.line.me/oauth2/v2.1/authorize</td><td>顧客ログイン</td></tr>
<tr><td>トークン取得</td><td>api.line.me/oauth2/v2.1/token</td><td>IDトークン取得</td></tr>
<tr><td>プッシュ通知</td><td>LineBotApi.push_message()</td><td>予約確定通知、決済URL送信、ガスアラート</td></tr>
<tr><td>プロフィール取得</td><td>LineBotApi.get_profile()</td><td>顧客名取得</td></tr>
</table>

<h2>10.2 Google Gemini API</h2>
<table>
<tr><th>項目</th><th>値</th></tr>
<tr><td>モデル</td><td>gemini-2.0-flash</td></tr>
<tr><td>エンドポイント</td><td>generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent</td></tr>
<tr><td>最大出力トークン</td><td>1024</td></tr>
<tr><td>Temperature</td><td>0.7</td></tr>
<tr><td>リトライ</td><td>429エラー時に最大2回（指数バックオフ）</td></tr>
</table>

<h2>10.3 Coiney 決済API</h2>
<table>
<tr><th>項目</th><th>値</th></tr>
<tr><td>API バージョン</td><td>2016-10-25</td></tr>
<tr><td>決済方法</td><td>creditcard</td></tr>
<tr><td>通貨</td><td>JPY</td></tr>
<tr><td>Webhook</td><td>POST /coiney_webhook/&lt;orderId&gt;/ (HMAC-SHA256署名検証)</td></tr>
</table>

<h2>10.4 AWS IoT / S3</h2>
<table>
<tr><th>サービス</th><th>用途</th></tr>
<tr><td>EC2</td><td>アプリケーションサーバー</td></tr>
<tr><td>S3</td><td>メディアファイル、バックアップ</td></tr>
<tr><td>DB</td><td>SQLite3 (将来RDS PostgreSQL移行予定)</td></tr>
<tr><td>CloudWatch</td><td>CPU監視（コスト最適化チェック）</td></tr>
</table>
'''

    # 11. デプロイアーキテクチャ
    html += '''
<!-- 11. デプロイアーキテクチャ -->
<h1>11. デプロイアーキテクチャ</h1>

<h2>11.1 AWS構成（現行）</h2>
<table>
<tr><th>リソース</th><th>詳細</th></tr>
<tr><td>EC2 インスタンス</td><td>t3.micro / Ubuntu 24.04 / ap-northeast-1 (Tokyo)</td></tr>
<tr><td>Public IP</td><td>52.198.72.13</td></tr>
<tr><td>ドメイン</td><td>timebaibai.com (Route 53)</td></tr>
<tr><td>IAM Role</td><td>EC2-S3-Backup-Tokyo</td></tr>
<tr><td>S3 バケット</td><td>mee-newfuhi-backups (DB + Media)</td></tr>
<tr><td>DB</td><td>SQLite3 (ローカルファイル)</td></tr>
</table>

<div class="arch-diagram">
          Internet
             │
      ┌──────▼──────┐
      │  Route 53   │  timebaibai.com
      └──────┬──────┘
             │
      ┌──────▼──────┐
      │   Nginx     │  SSL/TLS (Let's Encrypt)
      │  :80 → :443 │  Security Headers
      │  Rate Limit │  IoT API: 10r/s burst=20
      └──────┬──────┘
             │ proxy_pass
      ┌──────▼──────┐
      │  Gunicorn   │  127.0.0.1:8000
      │  (systemd)  │  workers=2, timeout=30
      └──────┬──────┘
             │
      ┌──────▼──────┐     ┌───────────┐
      │  Django     │────▶│  Redis    │
      │  + Celery   │     │ :6379     │
      └──────┬──────┘     └───────────┘
             │
      ┌──────▼──────┐
      │  SQLite3    │
      │  + S3 Sync  │───▶ mee-newfuhi-backups
      └─────────────┘
</div>

<h2>11.2 プロセス管理 (systemd)</h2>
<table>
<tr><th>サービス名</th><th>プロセス</th><th>設定</th></tr>
<tr><td><code>newfuhi.service</code></td><td>Gunicorn (Django WSGI)</td><td>workers=2, bind=127.0.0.1:8000, Restart=always</td></tr>
<tr><td><code>newfuhi-celery.service</code></td><td>Celery Worker</td><td>-A celery_config worker --loglevel=info</td></tr>
<tr><td><code>newfuhi-celerybeat.service</code></td><td>Celery Beat (スケジューラ)</td><td>-A celery_config beat --loglevel=info</td></tr>
<tr><td><code>nginx</code></td><td>リバースプロキシ</td><td>SSL終端 + 静的ファイル配信</td></tr>
<tr><td><code>redis-server</code></td><td>Celeryブローカー</td><td>redis://localhost:6379/0</td></tr>
</table>

<h2>11.3 セキュリティ設定</h2>
<table>
<tr><th>項目</th><th>設定内容</th></tr>
<tr><td>SSL/TLS</td><td>Let's Encrypt (certbot自動更新)</td></tr>
<tr><td>ファイアウォール (UFW)</td><td>Inbound: 22/tcp, 80/tcp, 443/tcp のみ許可</td></tr>
<tr><td>Fail2ban</td><td>SSH brute-force 防止 (sshd jail)</td></tr>
<tr><td>HTTP→HTTPS リダイレクト</td><td>Nginx 301 + Django SECURE_SSL_REDIRECT</td></tr>
<tr><td>HSTS</td><td>max-age=31536000, includeSubDomains, preload</td></tr>
<tr><td>Security Headers</td><td>X-Frame-Options: DENY, X-Content-Type-Options: nosniff, CSP</td></tr>
<tr><td>IoT API レート制限</td><td>limit_req_zone 10r/s burst=20 (Nginx)</td></tr>
<tr><td>Django Cookie Security</td><td>SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE</td></tr>
</table>

<h2>11.4 バックアップ戦略</h2>
<table>
<tr><th>対象</th><th>方法</th><th>スケジュール</th><th>保持期間</th></tr>
<tr><td>SQLite DB</td><td>sqlite3 .backup → S3 upload</td><td>毎日 AM 2:00 (cron)</td><td>ローカル30日 / S3 90日</td></tr>
<tr><td>Media ファイル</td><td>aws s3 sync</td><td>毎日 AM 2:00 (cron)</td><td>S3に常時同期</td></tr>
<tr><td>通知</td><td>LINE Notify (成功/失敗)</td><td>バックアップ完了時</td><td>-</td></tr>
</table>
<div class="info">
バックアップスクリプト: <code>scripts/backup_to_s3.sh</code><br>
S3バケット: <code>s3://mee-newfuhi-backups/</code> (db/, media/)<br>
環境検出: EC2 (/home/ubuntu/NewFUHI) と Mac (/Users/adon/NewFUHI) を自動判別
</div>

<h2>11.5 デプロイフロー</h2>
<div class="info">
<pre><code># ローカルからEC2へのデプロイ
./scripts/deploy_to_ec2.sh

# 実行ステップ:
# 1. git push origin main
# 2. EC2: git fetch && git reset --hard origin/main
# 3. EC2: pip install -r requirements.txt
# 4. EC2: python manage.py migrate --noinput
# 5. EC2: python manage.py collectstatic --noinput
# 6. EC2: systemctl restart newfuhi newfuhi-celery newfuhi-celerybeat
# 7. ヘルスチェック: curl https://timebaibai.com/healthz</code></pre>
</div>

<h2>11.6 環境変数</h2>
<table>
<tr><th>変数名</th><th>説明</th><th>必須</th></tr>
<tr><td>SECRET_KEY</td><td>Django シークレットキー</td><td>Yes</td></tr>
<tr><td>DATABASE_URL</td><td>DB接続文字列 (SQLite: sqlite:////path/to/db.sqlite3)</td><td>No (SQLiteフォールバック)</td></tr>
<tr><td>ALLOWED_HOSTS</td><td>許可ホスト (カンマ区切り)</td><td>Yes</td></tr>
<tr><td>CSRF_TRUSTED_ORIGINS</td><td>CSRF信頼オリジン</td><td>Yes</td></tr>
<tr><td>LINE_CHANNEL_ID</td><td>LINE Login チャネルID</td><td>LINE認証用</td></tr>
<tr><td>LINE_CHANNEL_SECRET</td><td>LINE Login チャネルシークレット</td><td>LINE認証用</td></tr>
<tr><td>LINE_REDIRECT_URL</td><td>LINE OAuth コールバックURL</td><td>LINE認証用</td></tr>
<tr><td>LINE_ACCESS_TOKEN</td><td>LINE Messaging API アクセストークン</td><td>LINE通知用</td></tr>
<tr><td>LINE_USER_ID_ENCRYPTION_KEY</td><td>LINE user_id 暗号化用Fernetキー</td><td>No (空でも起動可)</td></tr>
<tr><td>LINE_USER_ID_HASH_PEPPER</td><td>LINE user_id ハッシュ用ペッパー</td><td>No (空でも起動可)</td></tr>
<tr><td>GEMINI_API_KEY</td><td>Google Gemini API キー</td><td>AIチャット用</td></tr>
<tr><td>PAYMENT_API_URL</td><td>Coiney API エンドポイント</td><td>決済用</td></tr>
<tr><td>PAYMENT_API_KEY</td><td>Coiney API キー</td><td>決済用</td></tr>
<tr><td>CELERY_BROKER_URL</td><td>Redis URL (default: redis://localhost:6379/0)</td><td>No</td></tr>
<tr><td>DEFAULT_FROM_EMAIL</td><td>システムメール送信元</td><td>No</td></tr>
</table>

<h2>11.7 管理コマンド</h2>
<table>
<tr><th>コマンド</th><th>引数</th><th>説明</th></tr>
'''
    for cmd in commands:
        html += f'<tr><td><code>{cmd[0]}</code></td><td><code>{cmd[1]}</code></td><td>{cmd[2]}</td></tr>\n'
    html += '</table>\n'

    # 12. 付録
    html += '''
<!-- 12. 付録 -->
<h1>12. 付録</h1>

<h2>12.1 ソースファイル一覧</h2>
<table>
<tr><th>ファイル</th><th>行数</th><th>概要</th></tr>
<tr><td><code>booking/models.py</code></td><td>~1638</td><td>68モデル定義</td></tr>
<tr><td><code>booking/views.py</code></td><td>~2774</td><td>メインビュー/API</td></tr>
<tr><td><code>booking/tasks.py</code></td><td>~166</td><td>Celeryタスク(7)</td></tr>
<tr><td><code>booking/middleware.py</code></td><td>~146</td><td>セキュリティ監視</td></tr>
<tr><td><code>booking/services/payroll_calculator.py</code></td><td>~423</td><td>給与計算エンジン</td></tr>
<tr><td><code>booking/services/attendance_service.py</code></td><td>~160</td><td>勤怠導出</td></tr>
<tr><td><code>booking/services/shift_scheduler.py</code></td><td>~197</td><td>カバレッジベース自動スケジューリング</td></tr>
<tr><td><code>booking/services/shift_coverage.py</code></td><td>~54</td><td>カバレッジ計算ヘルパー</td></tr>
<tr><td><code>booking/services/shift_notifications.py</code></td><td>~105</td><td>シフト通知(欠勤/交代/カバー)</td></tr>
<tr><td><code>booking/services/zengin_export.py</code></td><td>~131</td><td>全銀CSV生成</td></tr>
<tr><td><code>booking/services/ai_chat.py</code></td><td>~131</td><td>AIチャット</td></tr>
<tr><td><code>booking/services/qr_service.py</code></td><td>~29</td><td>QRコード生成</td></tr>
</table>

<h2>12.2 テストカバレッジ</h2>
<div class="info">
テスト実行コマンド:
<pre><code>python -m pytest tests/ -v --tb=short
python -m pytest tests/ --cov=booking --cov-report=html</code></pre>
</div>

<h2>12.3 用語集</h2>
<table>
<tr><th>用語</th><th>説明</th></tr>
<tr><td>Schedule</td><td>予約スケジュール。is_temporary=True で仮予約、False で確定</td></tr>
<tr><td>Staff</td><td>占い師/スタッフ。store に紐づく</td></tr>
<tr><td>Store</td><td>店舗。複数のスタッフ、商品、デバイスを持つ</td></tr>
<tr><td>IoTDevice</td><td>Raspberry Pi Pico + センサーノード</td></tr>
<tr><td>IoTEvent</td><td>IoTデバイスから送信されたセンサーデータログ</td></tr>
<tr><td>Order / OrderItem</td><td>注文ヘッダー / 明細。在庫引当と連動</td></tr>
<tr><td>StockMovement</td><td>入出庫履歴（IN/OUT/ADJUST）</td></tr>
<tr><td>ShiftPeriod</td><td>シフト募集期間（月単位）</td></tr>
<tr><td>ShiftRequest</td><td>スタッフのシフト希望（preferred/available/unavailable）</td></tr>
<tr><td>ShiftAssignment</td><td>確定シフト（auto_schedule で生成）</td></tr>
<tr><td>ShiftVacancy</td><td>不足枠（定員未達の時間帯。auto_scheduleで自動生成、スタッフが応募可能）</td></tr>
<tr><td>ShiftSwapRequest</td><td>交代・欠勤申請（swap/cover/absence。マネージャー承認フロー）</td></tr>
<tr><td>StoreScheduleConfig.min_shift_hours</td><td>最低連続勤務時間（デフォルト2時間）</td></tr>
<tr><td>WorkAttendance</td><td>勤怠記録（シフトから自動生成 or 手動入力）</td></tr>
<tr><td>PayrollPeriod</td><td>給与計算期間（月単位）</td></tr>
<tr><td>PayrollEntry</td><td>個人別給与明細</td></tr>
<tr><td>PayrollDeduction</td><td>控除明細行（所得税/住民税/社保）</td></tr>
<tr><td>EmploymentContract</td><td>雇用契約（時給/月給、手当、社保基準額）</td></tr>
<tr><td>SalaryStructure</td><td>給与体系（社保料率、割増率）</td></tr>
<tr><td>Property</td><td>監視対象物件</td></tr>
<tr><td>PropertyDevice</td><td>物件に設置されたIoTデバイス</td></tr>
<tr><td>PropertyAlert</td><td>物件アラート（ガス漏れ/長期不在/オフライン）</td></tr>
<tr><td>SiteSettings</td><td>サイト全体設定（シングルトン、pk=1）</td></tr>
<tr><td>Fernet</td><td>対称暗号方式（AES-128-CBC + HMAC-SHA256）</td></tr>
<tr><td>全銀フォーマット</td><td>銀行振込データの標準規格（ヘッダー/データ/トレーラー/エンド）</td></tr>
</table>

</body>
</html>
'''
    return html


def main():
    html_path = os.path.join(BASE_DIR, 'docs', 'system_specification.html')
    pdf_path = os.path.join(BASE_DIR, 'docs', 'system_specification.pdf')

    print('Generating system specification HTML...')
    html_content = generate_html()

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f'HTML written to: {html_path}')

    # PDF生成
    try:
        from weasyprint import HTML
        print('Generating PDF with WeasyPrint...')
        HTML(filename=html_path).write_pdf(pdf_path)
        print(f'PDF written to: {pdf_path}')
    except ImportError:
        print('WeasyPrint not installed. Skipping PDF generation.')
        print('Install with: pip install weasyprint')
    except Exception as e:
        print(f'PDF generation failed: {e}')
        print('HTML file is still available for manual conversion.')


if __name__ == '__main__':
    main()
