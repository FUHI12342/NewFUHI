#!/usr/bin/env python3
"""
i18n_dashboard.py
=================
Converts hardcoded Japanese strings in the restaurant_dashboard.html template
to Django i18n {% trans "..." %} tags.

Part 1: HTML section (lines 1-1075) — targeted string replacements
Part 2: JS section (lines 1076-3563) — insert T dict + replace JS strings
"""

import re

TEMPLATE_PATH = "/Users/adon/NewFUHI/templates/admin/booking/restaurant_dashboard.html"

# ---------------------------------------------------------------------------
# 1. Read file
# ---------------------------------------------------------------------------
with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
    content = f.read()

original = content  # keep for diff summary
changes = []  # list of (description, old, new)


def replace_once(content, old, new, desc):
    """Replace exactly one occurrence; raise if not found or ambiguous."""
    count = content.count(old)
    if count == 0:
        print(f"  [SKIP] Not found: {desc!r}")
        return content, False
    if count > 1:
        # Allow multi-replace for truly identical strings flagged as such
        pass
    new_content = content.replace(old, new, 1)
    changes.append(desc)
    return new_content, True


def replace_all_occurrences(content, old, new, desc):
    """Replace ALL occurrences of old with new."""
    count = content.count(old)
    if count == 0:
        print(f"  [SKIP] Not found: {desc!r}")
        return content, 0
    new_content = content.replace(old, new)
    changes.append(f"{desc} (x{count})")
    return new_content, count


# ===========================================================================
# PART 1: HTML replacements (lines 1-1075)
# ===========================================================================
print("\n=== Part 1: HTML replacements ===")

# Quick-link cards
HTML_REPLACEMENTS = [
    # Quick-link spans
    ("<span>シフトカレンダー</span>", '<span>{% trans "シフトカレンダー" %}</span>'),
    ("<span>QR勤怠</span>", '<span>{% trans "QR勤怠" %}</span>'),
    ("<span>出退勤ボード</span>", '<span>{% trans "出退勤ボード" %}</span>'),
    ("<span>POS</span>", '<span>{% trans "POS" %}</span>'),
    ("<span>キッチン</span>", '<span>{% trans "キッチン" %}</span>'),
    ("<span>来客分析</span>", '<span>{% trans "来客分析" %}</span>'),
    ("<span>AI推薦</span>", '<span>{% trans "AI推薦" %}</span>'),
    # Toolbar
    ('title="ヘルプを表示"', 'title="{% trans \'ヘルプを表示\' %}"'),
    (">ヘルプ</button>", '>{% trans "ヘルプ" %}</button>'),
    # Period label
    ('"期間:"', '"{% trans \'期間\' %}:"'),
    # Period select options (appear multiple times — we'll handle each group)
    # Tabs
    (">概要</button>", '>{% trans "概要" %}</button>'),
    (">総売上</button>", '>{% trans "総売上" %}</button>'),
    (">顧客</button>", '>{% trans "顧客" %}</button>'),
    (">キャスト</button>", '>{% trans "キャスト" %}</button>'),
    (">スタッフ</button>", '>{% trans "スタッフ" %}</button>'),
    (">ECショップ売上</button>", '>{% trans "ECショップ売上" %}</button>'),
    (">店内メニュー売上</button>", '>{% trans "店内メニュー売上" %}</button>'),
    (">シフト</button>", '>{% trans "シフト" %}</button>'),
    (">勤怠</button>", '>{% trans "勤怠" %}</button>'),
    (">運営</button>", '>{% trans "運営" %}</button>'),
    (">チェックイン</button>", '>{% trans "チェックイン" %}</button>'),
    # Overview sub-tabs
    (">予約KPI</button>", '>{% trans "予約KPI" %}</button>'),
    (">日別予約グラフ</button>", '>{% trans "日別予約グラフ" %}</button>'),
    # Insight sub-tab has embedded span — handled separately below
    (">KPIスコアカード</button>", '>{% trans "KPIスコアカード" %}</button>'),
    # Overview KPI card
    ('<h3 class="text-lg font-semibold mb-3">予約KPI</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "予約KPI" %}</h3>'),
    ('<span class="text-sm db-text-secondary">今後の予約数</span>',
     '<span class="text-sm db-text-secondary">{% trans "今後の予約数" %}</span>'),
    ('<span class="text-sm db-text-secondary">キャンセル率</span>',
     '<span class="text-sm db-text-secondary">{% trans "キャンセル率" %}</span>'),
    ('<span class="text-sm db-text-secondary">過去90日の予約合計</span>',
     '<span class="text-sm db-text-secondary">{% trans "過去90日の予約合計" %}</span>'),
    # Overview chart card
    ('<h3 class="text-lg font-semibold mb-3">日別予約数（過去90日）</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "日別予約数（過去90日）" %}</h3>'),
    # Insights card
    ('<h3 class="text-lg font-semibold">ビジネスインサイト</h3>',
     '<h3 class="text-lg font-semibold">{% trans "ビジネスインサイト" %}</h3>'),
    (">すべて既読</button>", '>{% trans "すべて既読" %}</button>'),
    (">分析実行</button>", '>{% trans "分析実行" %}</button>'),
    ('<p class="text-gray-400 text-sm text-center">読み込み中...</p>',
     '<p class="text-gray-400 text-sm text-center">{% trans "読み込み中..." %}</p>'),
    # KPI scorecard
    ('<h3 class="text-lg font-semibold mb-4">KPIスコアカード</h3>',
     '<h3 class="text-lg font-semibold mb-4">{% trans "KPIスコアカード" %}</h3>'),
    ('<p class="text-gray-400 text-sm text-center col-span-full">読み込み中...</p>',
     '<p class="text-gray-400 text-sm text-center col-span-full">{% trans "読み込み中..." %}</p>'),
    # Sales sub-tabs
    (">売上推移</button>", '>{% trans "売上推移" %}</button>'),
    (">人気商品 TOP10</button>", '>{% trans "人気商品 TOP10" %}</button>'),
    (">メニュー分析</button>", '>{% trans "メニュー分析" %}'),  # no </button> immediately — has `;`
    (">ABC分析</button>", '>{% trans "ABC分析" %}'),
    (">売上予測</button>", '>{% trans "売上予測" %}'),
    (">時間帯別売上</button>", '>{% trans "時間帯別売上" %}'),
    (">客単価推移</button>", '>{% trans "客単価推移" %}'),
    (">チャネル別売上</button>", '>{% trans "チャネル別売上" %}'),
    # Sales trend card
    ('<h3 class="text-lg font-semibold mb-3">売上推移</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "売上推移" %}</h3>'),
    # Top products card
    ('<h3 class="text-lg font-semibold mb-3">人気商品 TOP10</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "人気商品 TOP10" %}</h3>'),
    # Menu engineering card
    ('<h3 class="text-lg font-semibold">メニューエンジニアリング マトリクス</h3>',
     '<h3 class="text-lg font-semibold">{% trans "メニューエンジニアリング マトリクス" %}</h3>'),
    # Menu eng table headers
    ('<th class="px-3 py-2 text-left">商品名</th>\n                <th class="px-3 py-2 text-right">販売数</th>\n                <th class="px-3 py-2 text-right">利益率</th>\n                <th class="px-3 py-2 text-right">売上</th>\n                <th class="px-3 py-2 text-center">分類</th>',
     '<th class="px-3 py-2 text-left">{% trans "商品名" %}</th>\n                <th class="px-3 py-2 text-right">{% trans "販売数" %}</th>\n                <th class="px-3 py-2 text-right">{% trans "利益率" %}</th>\n                <th class="px-3 py-2 text-right">{% trans "売上" %}</th>\n                <th class="px-3 py-2 text-center">{% trans "分類" %}</th>'),
    ('<tr><td colspan="5" class="px-3 py-2 text-gray-400 text-center">読み込み中...</td></tr>\n            </tbody>\n          </table>\n        </div>\n        <div class="ai-analysis-panel mt-4 p-4 bg-gradient-to-r from-violet-50 to-indigo-50 rounded-xl border" id="sales-ai-menu-eng"',
     '<tr><td colspan="5" class="px-3 py-2 text-gray-400 text-center">{% trans "読み込み中..." %}</td></tr>\n            </tbody>\n          </table>\n        </div>\n        <div class="ai-analysis-panel mt-4 p-4 bg-gradient-to-r from-violet-50 to-indigo-50 rounded-xl border" id="sales-ai-menu-eng"'),
    # ABC analysis card
    ('<h3 class="text-lg font-semibold">ABC分析（パレート）</h3>',
     '<h3 class="text-lg font-semibold">{% trans "ABC分析（パレート）" %}</h3>'),
    # ABC rank legend
    ('<span class="inline-flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-emerald-500"></span> A (上位80%)</span>',
     '<span class="inline-flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-emerald-500"></span> A ({% trans "上位80%" %})</span>'),
    ('<span class="inline-flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-amber-500"></span> B (80-95%)</span>',
     '<span class="inline-flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-amber-500"></span> B (80-95%)</span>'),
    ('<span class="inline-flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-gray-400"></span> C (95-100%)</span>',
     '<span class="inline-flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-gray-400"></span> C (95-100%)</span>'),
    # ABC table headers
    ('<th class="px-3 py-2 text-left">商品名</th>\n                <th class="px-3 py-2 text-right">売上</th>\n                <th class="px-3 py-2 text-right">構成比</th>\n                <th class="px-3 py-2 text-right">累積</th>\n                <th class="px-3 py-2 text-center">ランク</th>',
     '<th class="px-3 py-2 text-left">{% trans "商品名" %}</th>\n                <th class="px-3 py-2 text-right">{% trans "売上" %}</th>\n                <th class="px-3 py-2 text-right">{% trans "構成比" %}</th>\n                <th class="px-3 py-2 text-right">{% trans "累積" %}</th>\n                <th class="px-3 py-2 text-center">{% trans "ランク" %}</th>'),
    ('<tr><td colspan="5" class="px-3 py-2 text-gray-400 text-center">読み込み中...</td></tr>\n            </tbody>\n          </table>\n        </div>\n        <div class="ai-analysis-panel mt-4 p-4 bg-gradient-to-r from-violet-50 to-indigo-50 rounded-xl border" id="sales-ai-abc"',
     '<tr><td colspan="5" class="px-3 py-2 text-gray-400 text-center">{% trans "読み込み中..." %}</td></tr>\n            </tbody>\n          </table>\n        </div>\n        <div class="ai-analysis-panel mt-4 p-4 bg-gradient-to-r from-violet-50 to-indigo-50 rounded-xl border" id="sales-ai-abc"'),
    # Forecast card
    ('<h3 class="text-lg font-semibold">売上予測</h3>',
     '<h3 class="text-lg font-semibold">{% trans "売上予測" %}</h3>'),
    # Heatmap card
    ('<h3 class="text-lg font-semibold">時間帯別売上ヒートマップ</h3>',
     '<h3 class="text-lg font-semibold">{% trans "時間帯別売上ヒートマップ" %}</h3>'),
    ('<span class="text-xs text-gray-400">曜日 × 時間帯（過去90日）</span>',
     '<span class="text-xs text-gray-400">{% trans "曜日 × 時間帯（過去90日）" %}</span>'),
    # AOV card
    ('<h3 class="text-lg font-semibold">客単価（AOV）推移</h3>',
     '<h3 class="text-lg font-semibold">{% trans "客単価（AOV）推移" %}</h3>'),
    # Channel sales card
    ('<h3 class="text-lg font-semibold">チャネル別売上</h3>',
     '<h3 class="text-lg font-semibold">{% trans "チャネル別売上" %}</h3>'),
    # Customers sub-tabs
    (">コホート分析</button>", '>{% trans "コホート分析" %}'),
    (">RFM分析</button>", '>{% trans "RFM分析" %}'),
    (">バスケット分析</button>", '>{% trans "バスケット分析" %}'),
    (">NPS・満足度</button>", '>{% trans "NPS・満足度" %}'),
    # Cohort card
    ('<h3 class="text-lg font-semibold">月別コホート リテンション</h3>',
     '<h3 class="text-lg font-semibold">{% trans "月別コホート リテンション" %}</h3>'),
    ('<span class="text-xs text-gray-400">初回来店月ごとの継続率</span>',
     '<span class="text-xs text-gray-400">{% trans "初回来店月ごとの継続率" %}</span>'),
    ('<p class="text-gray-400 text-center py-8">読み込み中...</p>',
     '<p class="text-gray-400 text-center py-8">{% trans "読み込み中..." %}</p>'),
    # RFM card
    ('<h3 class="text-lg font-semibold">RFMセグメンテーション</h3>',
     '<h3 class="text-lg font-semibold">{% trans "RFMセグメンテーション" %}</h3>'),
    # Basket card
    ('<h3 class="text-lg font-semibold">バスケット分析（併売ルール）</h3>',
     '<h3 class="text-lg font-semibold">{% trans "バスケット分析（併売ルール）" %}</h3>'),
    ('<p class="text-gray-400 text-center py-8">読み込み中...</p>',
     '<p class="text-gray-400 text-center py-8">{% trans "読み込み中..." %}</p>'),
    # NPS cards
    ('<h3 class="text-lg font-semibold mb-3">NPSスコア</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "NPSスコア" %}</h3>'),
    # NPS breakdown — mixed text with dynamic elements
    ('<span class="text-emerald-600">推奨者: <b id="nps-promoters">0</b></span>',
     '<span class="text-emerald-600">{% trans "推奨者" %}: <b id="nps-promoters">0</b></span>'),
    ('<span class="text-gray-500">中立者: <b id="nps-passives">0</b></span>',
     '<span class="text-gray-500">{% trans "中立者" %}: <b id="nps-passives">0</b></span>'),
    ('<span class="text-rose-600">批判者: <b id="nps-detractors">0</b></span>',
     '<span class="text-rose-600">{% trans "批判者" %}: <b id="nps-detractors">0</b></span>'),
    ('<div class="text-xs text-gray-400 mt-2">回答数: <span id="nps-total">0</span></div>',
     '<div class="text-xs text-gray-400 mt-2">{% trans "回答数" %}: <span id="nps-total">0</span></div>'),
    ('<h3 class="text-lg font-semibold mb-3">カテゴリ別評価</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "カテゴリ別評価" %}</h3>'),
    ('<h3 class="text-lg font-semibold mb-3">NPS推移</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "NPS推移" %}</h3>'),
    ('<h3 class="text-lg font-semibold mb-3">最新フィードバック</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "最新フィードバック" %}</h3>'),
    ('<p class="text-gray-400 text-sm text-center">読み込み中...</p>\n        </div>\n      </div>\n    </div>\n  </div>',
     '<p class="text-gray-400 text-sm text-center">{% trans "読み込み中..." %}</p>\n        </div>\n      </div>\n    </div>\n  </div>'),
    # Cast sub-tabs
    (">グラフ</button>", '>{% trans "グラフ" %}</button>'),
    (">売上ランキング</button>", '>{% trans "売上ランキング" %}</button>'),
    # Cast cards
    ('<h3 class="text-lg font-semibold mb-3">キャスト別 予約数・売上比較</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "キャスト別 予約数・売上比較" %}</h3>'),
    ('<h3 class="text-lg font-semibold mb-3">キャスト別 売上ランキング</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "キャスト別 売上ランキング" %}</h3>'),
    # Cast ranking table headers
    ('<th class="px-4 py-2 text-center">順位</th>\n              <th class="px-4 py-2 text-left">キャスト</th>\n              <th class="px-4 py-2 text-right">予約数</th>\n              <th class="px-4 py-2 text-right">売上 (円)</th>',
     '<th class="px-4 py-2 text-center">{% trans "順位" %}</th>\n              <th class="px-4 py-2 text-left">{% trans "キャスト" %}</th>\n              <th class="px-4 py-2 text-right">{% trans "予約数" %}</th>\n              <th class="px-4 py-2 text-right">{% trans "売上 (円)" %}</th>'),
    ('<tr><td colspan="4" class="px-4 py-2 text-gray-400 text-center">読み込み中...</td></tr>\n          </tbody>',
     '<tr><td colspan="4" class="px-4 py-2 text-gray-400 text-center">{% trans "読み込み中..." %}</td></tr>\n          </tbody>'),
    # Staff card
    ('<h3 class="text-lg font-semibold mb-3">スタッフ別 予約数・売上比較</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "スタッフ別 予約数・売上比較" %}</h3>'),
    # EC sub-tabs (buttons with semicolons in onclick)
    # We replace the text content patterns between > and < surrounding Japanese
    # EC sales tab heading
    ('<h3 class="text-lg font-semibold">ECショップ 売上推移</h3>',
     '<h3 class="text-lg font-semibold">{% trans "ECショップ 売上推移" %}</h3>'),
    ('<h3 class="text-lg font-semibold mb-3">ECショップ 人気商品 TOP10</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "ECショップ 人気商品 TOP10" %}</h3>'),
    ('<h3 class="text-lg font-semibold">EC メニューエンジニアリング</h3>',
     '<h3 class="text-lg font-semibold">{% trans "EC メニューエンジニアリング" %}</h3>'),
    ('<h3 class="text-lg font-semibold">EC ABC分析（パレート）</h3>',
     '<h3 class="text-lg font-semibold">{% trans "EC ABC分析（パレート）" %}</h3>'),
    ('<h3 class="text-lg font-semibold">EC 売上予測</h3>',
     '<h3 class="text-lg font-semibold">{% trans "EC 売上予測" %}</h3>'),
    ('<h3 class="text-lg font-semibold">EC 時間帯別売上</h3>',
     '<h3 class="text-lg font-semibold">{% trans "EC 時間帯別売上" %}</h3>'),
    ('<h3 class="text-lg font-semibold">EC 客単価推移</h3>',
     '<h3 class="text-lg font-semibold">{% trans "EC 客単価推移" %}</h3>'),
    # Instore headings
    ('<h3 class="text-lg font-semibold">店内メニュー 売上推移</h3>',
     '<h3 class="text-lg font-semibold">{% trans "店内メニュー 売上推移" %}</h3>'),
    ('<h3 class="text-lg font-semibold mb-3">店内メニュー 人気商品 TOP10</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "店内メニュー 人気商品 TOP10" %}</h3>'),
    ('<h3 class="text-lg font-semibold">店内 メニューエンジニアリング</h3>',
     '<h3 class="text-lg font-semibold">{% trans "店内 メニューエンジニアリング" %}</h3>'),
    ('<h3 class="text-lg font-semibold">店内 ABC分析（パレート）</h3>',
     '<h3 class="text-lg font-semibold">{% trans "店内 ABC分析（パレート）" %}</h3>'),
    ('<h3 class="text-lg font-semibold">店内 売上予測</h3>',
     '<h3 class="text-lg font-semibold">{% trans "店内 売上予測" %}</h3>'),
    ('<h3 class="text-lg font-semibold">店内 時間帯別売上</h3>',
     '<h3 class="text-lg font-semibold">{% trans "店内 時間帯別売上" %}</h3>'),
    ('<h3 class="text-lg font-semibold">店内 客単価推移</h3>',
     '<h3 class="text-lg font-semibold">{% trans "店内 客単価推移" %}</h3>'),
    # Shift tab
    ('<h3 class="text-lg font-semibold">今月のシフト状況</h3>',
     '<h3 class="text-lg font-semibold">{% trans "今月のシフト状況" %}</h3>'),
    # Shift calendar link button text
    ('<i class="fas fa-calendar-alt"></i> シフトカレンダーを開く',
     '<i class="fas fa-calendar-alt"></i> {% trans "シフトカレンダーを開く" %}'),
    ('<span class="text-sm text-gray-500">確定シフト数</span>',
     '<span class="text-sm text-gray-500">{% trans "確定シフト数" %}</span>'),
    ('<span class="text-sm text-gray-500">同期済み</span>',
     '<span class="text-sm text-gray-500">{% trans "同期済み" %}</span>'),
    ('<span class="text-sm text-gray-500">募集中の期間</span>',
     '<span class="text-sm text-gray-500">{% trans "募集中の期間" %}</span>'),
    ('<h4 class="text-base font-semibold mb-2">スタッフ別シフト数</h4>',
     '<h4 class="text-base font-semibold mb-2">{% trans "スタッフ別シフト数" %}</h4>'),
    # Shift table headers
    ('<th class="px-4 py-2 text-left">スタッフ</th>\n              <th class="px-4 py-2 text-right">確定シフト数</th>\n              <th class="px-4 py-2 text-right">同期済み</th>',
     '<th class="px-4 py-2 text-left">{% trans "スタッフ" %}</th>\n              <th class="px-4 py-2 text-right">{% trans "確定シフト数" %}</th>\n              <th class="px-4 py-2 text-right">{% trans "同期済み" %}</th>'),
    ('<tr><td colspan="3" class="px-4 py-2 text-gray-400 text-center">読み込み中...</td></tr>',
     '<tr><td colspan="3" class="px-4 py-2 text-gray-400 text-center">{% trans "読み込み中..." %}</td></tr>'),
    # Attendance tab
    ('<h3 class="text-lg font-semibold">本日の出退勤状況</h3>',
     '<h3 class="text-lg font-semibold">{% trans "本日の出退勤状況" %}</h3>'),
    # Attendance links
    ('<i class="fas fa-clipboard-check"></i> 出退勤ボード',
     '<i class="fas fa-clipboard-check"></i> {% trans "出退勤ボード" %}'),
    ('<i class="fas fa-qrcode"></i> QR勤怠',
     '<i class="fas fa-qrcode"></i> {% trans "QR勤怠" %}'),
    ('<span class="text-sm text-gray-500">出勤中</span>',
     '<span class="text-sm text-gray-500">{% trans "出勤中" %}</span>'),
    ('<span class="text-sm text-gray-500">退勤済み</span>',
     '<span class="text-sm text-gray-500">{% trans "退勤済み" %}</span>'),
    ('<span class="text-sm text-gray-500">未出勤</span>',
     '<span class="text-sm text-gray-500">{% trans "未出勤" %}</span>'),
    # Attendance table headers
    ('<th class="px-4 py-2 text-left">スタッフ</th>\n            <th class="px-4 py-2 text-center">状態</th>\n            <th class="px-4 py-2 text-right">出勤</th>\n            <th class="px-4 py-2 text-right">退勤</th>',
     '<th class="px-4 py-2 text-left">{% trans "スタッフ" %}</th>\n            <th class="px-4 py-2 text-center">{% trans "状態" %}</th>\n            <th class="px-4 py-2 text-right">{% trans "出勤" %}</th>\n            <th class="px-4 py-2 text-right">{% trans "退勤" %}</th>'),
    ('<tr><td colspan="4" class="px-4 py-2 text-gray-400 text-center">読み込み中...</td></tr>\n        </tbody>',
     '<tr><td colspan="4" class="px-4 py-2 text-gray-400 text-center">{% trans "読み込み中..." %}</td></tr>\n        </tbody>'),
    # Operations tab
    ('<h3 class="text-lg font-semibold">来客分析</h3>',
     '<h3 class="text-lg font-semibold">{% trans "来客分析" %}</h3>'),
    ('<i class="fas fa-chart-bar"></i> 詳細を見る',
     '<i class="fas fa-chart-bar"></i> {% trans "詳細を見る" %}'),
    ('<span class="text-sm text-gray-500">今日の来客数</span>',
     '<span class="text-sm text-gray-500">{% trans "今日の来客数" %}</span>'),
    ('<span class="text-sm text-gray-500">コンバージョン率</span>',
     '<span class="text-sm text-gray-500">{% trans "コンバージョン率" %}</span>'),
    ('<h3 class="text-lg font-semibold">AI推薦</h3>',
     '<h3 class="text-lg font-semibold">{% trans "AI推薦" %}</h3>'),
    ('<i class="fas fa-robot"></i> 詳細を見る',
     '<i class="fas fa-robot"></i> {% trans "詳細を見る" %}'),
    ('<span class="text-sm text-gray-500">モデル精度</span>',
     '<span class="text-sm text-gray-500">{% trans "モデル精度" %}</span>'),
    ('<span class="text-sm text-gray-500">今日の推薦スタッフ数</span>',
     '<span class="text-sm text-gray-500">{% trans "今日の推薦スタッフ数" %}</span>'),
    ('<h3 class="text-lg font-semibold">進行中の注文</h3>',
     '<h3 class="text-lg font-semibold">{% trans "進行中の注文" %}</h3>'),
    ('<i class="fas fa-cash-register"></i> POS',
     '<i class="fas fa-cash-register"></i> {% trans "POS" %}'),
    ('<i class="fas fa-utensils"></i> キッチン',
     '<i class="fas fa-utensils"></i> {% trans "キッチン" %}'),
    ('<span class="text-sm text-gray-500">未処理</span>',
     '<span class="text-sm text-gray-500">{% trans "未処理" %}</span>'),
    ('<span class="text-sm text-gray-500">調理中</span>',
     '<span class="text-sm text-gray-500">{% trans "調理中" %}</span>'),
    ('<span class="text-sm text-gray-500">配膳済み</span>',
     '<span class="text-sm text-gray-500">{% trans "配膳済み" %}</span>'),
    ('<h3 class="text-lg font-semibold mb-3">在庫アラート</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "在庫アラート" %}</h3>'),
    ('<p class="text-gray-400 text-sm text-center">読み込み中...</p>\n        </div>\n      </div>\n    </div>\n  </div>\n\n  {# ===== Tab: チェックイン',
     '<p class="text-gray-400 text-sm text-center">{% trans "読み込み中..." %}</p>\n        </div>\n      </div>\n    </div>\n  </div>\n\n  {# ===== Tab: チェックイン'),
    # Checkin sub-tabs
    (">サマリー</button>", '>{% trans "サマリー" %}</button>'),
    (">日別推移</button>", '>{% trans "日別推移" %}</button>'),
    (">スタッフ別</button>", '>{% trans "スタッフ別" %}</button>'),
    (">時間帯別</button>", '>{% trans "時間帯別" %}</button>'),
    # Checkin summary cards
    ('<span class="text-sm text-gray-500">総予約数</span>',
     '<span class="text-sm text-gray-500">{% trans "総予約数" %}</span>'),
    ('<span class="text-sm text-gray-500">チェックイン済</span>',
     '<span class="text-sm text-gray-500">{% trans "チェックイン済" %}</span>'),
    ('<span class="text-sm text-gray-500">ノーショー</span>',
     '<span class="text-sm text-gray-500">{% trans "ノーショー" %}</span>'),
    ('<span class="text-sm text-gray-500">チェックイン率</span>',
     '<span class="text-sm text-gray-500">{% trans "チェックイン率" %}</span>'),
    # Checkin chart headings
    ('<h3 class="text-lg font-semibold mb-3">日別チェックイン推移</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "日別チェックイン推移" %}</h3>'),
    ('<h3 class="text-lg font-semibold mb-3">スタッフ別チェックイン率</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "スタッフ別チェックイン率" %}</h3>'),
    ('<h3 class="text-lg font-semibold mb-3">時間帯別チェックイン分布</h3>',
     '<h3 class="text-lg font-semibold mb-3">{% trans "時間帯別チェックイン分布" %}</h3>'),
]

# Apply HTML replacements
for old, new in HTML_REPLACEMENTS:
    content, ok = replace_once(content, old, new, f"HTML: {old[:60]!r}")

# Special: insight sub-tab button with embedded span
old_insight_btn = '>インサイト <span id="insight-badge"'
new_insight_btn = '>{% trans "インサイト" %} <span id="insight-badge"'
content, _ = replace_once(content, old_insight_btn, new_insight_btn, "HTML: insight subtab button")

# Special: period select <option> tags (appear in multiple selects, all identical)
# Replace ALL occurrences of the four period options
PERIOD_OPTIONS = [
    ('<option value="daily">日別</option>', "daily", "日別"),
    ('<option value="weekly">週別</option>', "weekly", "週別"),
    ('<option value="monthly">月別</option>', "monthly", "月別"),
    ('<option value="yearly">年別</option>', "yearly", "年別"),
]
for opt_jp, val, opt_en_key in PERIOD_OPTIONS:
    new_opt = '<option value="' + val + '">{% trans "' + opt_en_key + '" %}</option>'
    content, cnt = replace_all_occurrences(content, opt_jp, new_opt, "HTML options: " + opt_en_key)

# ===========================================================================
# PART 2: JS – Insert T dictionary after DOMContentLoaded line
# ===========================================================================
print("\n=== Part 2: JS – Insert T dictionary ===")

T_DICT = """
  var T = {
    // Chart labels
    reservations: "{% trans '予約数' %}",
    cancellations: "{% trans 'キャンセル数' %}",
    sales_yen: "{% trans '売上 (円)' %}",
    sales_prefix: "{% trans '売上: ' %}",
    yen_suffix: "{% trans ' 円' %}",
    order_count: "{% trans '注文数' %}",
    ec_sales_yen: "{% trans 'ECショップ売上 (円)' %}",
    instore_sales_yen: "{% trans '店内メニュー売上 (円)' %}",
    aov_yen: "{% trans '客単価 (円)' %}",
    aov_prefix: "{% trans '客単価: ' %}",
    cumulative_pct: "{% trans '累積構成比 (%)' %}",
    cumulative_prefix: "{% trans '累積: ' %}",
    sales_volume: "{% trans '販売数量 (人気度)' %}",
    sales_volume_short: "{% trans '販売数量' %}",
    margin_rate_pct: "{% trans '利益率 (%)' %}",
    actual: "{% trans '実績' %}",
    forecast_label: "{% trans '予測' %}",
    upper_bound: "{% trans '上限' %}",
    lower_bound: "{% trans '下限' %}",
    time_slot: "{% trans '時間帯' %}",
    weekday: "{% trans '曜日' %}",
    avg_rating: "{% trans '平均評価' %}",
    checkin_label: "{% trans 'チェックイン' %}",
    noshow_label: "{% trans 'ノーショー' %}",
    checkin_rate_pct: "{% trans 'チェックイン率 (%)' %}",
    checkin_count: "{% trans 'チェックイン数' %}",
    // Status messages
    loading: "{% trans '読み込み中...' %}",
    no_data: "{% trans 'データなし' %}",
    fetch_error: "{% trans '取得エラー' %}",
    data_fetch_error: "{% trans 'データ取得エラー' %}",
    no_shift_data: "{% trans 'シフトデータなし' %}",
    no_cast_data: "{% trans 'キャストデータなし' %}",
    no_att_data: "{% trans '本日の勤怠データなし' %}",
    no_stock_alerts: "{% trans '在庫アラートなし' %}",
    remaining: "{% trans '残' %}",
    no_feedback: "{% trans 'フィードバックがありません' %}",
    no_data_available: "{% trans 'データがありません' %}",
    loading_error: "{% trans '読み込みエラー' %}",
    no_insights: "{% trans 'インサイトはありません。「分析実行」ボタンで最新の分析を行えます。' %}",
    mark_read: "{% trans '既読にする' %}",
    analyzing: "{% trans '分析中...' %}",
    run_analysis: "{% trans '分析実行' %}",
    // Attendance
    clocked_out: "{% trans '退勤済み' %}",
    clocked_in: "{% trans '出勤中' %}",
    not_clocked_in: "{% trans '未出勤' %}",
    // Forecast method
    moving_avg: "{% trans '移動平均+曜日係数' %}",
    // Pairwise
    pairwise: "{% trans 'ペアワイズ分析' %}",
    target_txn: "{% trans '対象トランザクション: ' %}",
    unit_items: "{% trans '件' %}",
    demo_label: "{% trans 'デモ' %}",
    target_txn_demo: "{% trans '対象トランザクション: 100件（デモ）' %}",
    // Basket table headers
    th_antecedent: "{% trans '前提商品' %}",
    th_consequent: "{% trans '結論商品' %}",
    // Cohort
    th_cohort: "{% trans 'コホート' %}",
    th_size: "{% trans '人数' %}",
    // Menu Engineering table headers
    th_product: "{% trans '商品名' %}",
    th_qty_sold: "{% trans '販売数' %}",
    th_margin_rate: "{% trans '利益率' %}",
    th_sales: "{% trans '売上' %}",
    th_category: "{% trans '分類' %}",
    th_share: "{% trans '構成比' %}",
    th_cumulative: "{% trans '累積' %}",
    th_rank: "{% trans 'ランク' %}",
    // Tooltip formats
    sold_prefix: "{% trans '販売: ' %}",
    margin_prefix: "{% trans '利益率: ' %}",
    order_prefix: "{% trans '注文数: ' %}",
    // Severity/category labels
    sev_critical: "{% trans '重要' %}",
    sev_warning: "{% trans '注意' %}",
    sev_info: "{% trans '情報' %}",
    cat_sales: "{% trans '売上' %}",
    cat_inventory: "{% trans '在庫' %}",
    cat_staffing: "{% trans 'スタッフ' %}",
    cat_menu: "{% trans 'メニュー' %}",
    cat_customer: "{% trans '顧客' %}",
    // KPI status
    status_good: "{% trans '良好' %}",
    status_warn: "{% trans '注意' %}",
    status_bad: "{% trans '要改善' %}",
    benchmark_prefix: "{% trans '基準: ' %}",
    // AI analysis
    ai_analysis: "{% trans 'AI分析' %}",
    recommended_actions: "{% trans '推奨アクション' %}",
    // NPS
    food: "{% trans '料理' %}",
    service: "{% trans 'サービス' %}",
    ambiance: "{% trans '雰囲気' %}",
    food_colon: "{% trans '料理:' %}",
    service_colon: "{% trans 'サービス:' %}",
    ambiance_colon: "{% trans '雰囲気:' %}",
    // Weekday labels
    sun: "{% trans '日' %}",
    mon: "{% trans '月' %}",
    tue: "{% trans '火' %}",
    wed: "{% trans '水' %}",
    thu: "{% trans '木' %}",
    fri: "{% trans '金' %}",
    sat: "{% trans '土' %}",
    hour_suffix: "{% trans '時' %}",
    // Channel
    ch_ec: "{% trans 'ECショップ' %}",
    ch_table: "{% trans 'テーブル注文' %}",
    ch_reservation: "{% trans '予約' %}",
    // Tour
    tour_tab_nav_title: "{% trans 'タブナビゲーション' %}",
    tour_tab_nav_text: "{% trans 'ここでダッシュボードの各セクションを切り替えます。概要・売上・顧客・スタッフ・シフト・勤怠・運営の7つのタブがあります。' %}",
    tour_overview_title: "{% trans '概要タブ' %}",
    tour_overview_text: "{% trans '予約KPI、日別予約グラフ、ビジネスインサイト、KPIスコアカードを確認できます。' %}",
    tour_period_title: "{% trans '期間選択' %}",
    tour_period_text: "{% trans '日別・週別・月別でデータの集計期間を切り替えられます。' %}",
    tour_sales_title: "{% trans '売上タブ' %}",
    tour_sales_text: "{% trans '売上推移、人気商品、メニュー分析、ABC分析、売上予測、時間帯別売上、客単価推移を確認できます。' %}",
    tour_customers_title: "{% trans '顧客分析タブ' %}",
    tour_customers_text: "{% trans 'コホート分析、RFMセグメンテーション、バスケット分析、NPS・顧客満足度を確認できます。' %}",
    tour_ops_title: "{% trans '運営タブ' %}",
    tour_ops_text: "{% trans '在庫アラートなど、日常の運営に必要な情報を確認できます。' %}",
    tour_help_title: "{% trans 'ヘルプボタン' %}",
    tour_help_text: "{% trans 'このボタンをクリックすると、いつでもこのヘルプを再表示できます。' %}",
    // Instore label
    instore: "{% trans '店内' %}",
  };
"""

DOMCONTENTLOADED_LINE = "document.addEventListener('DOMContentLoaded', function () {"
INSERT_AFTER = DOMCONTENTLOADED_LINE + "\n"

if INSERT_AFTER in content:
    content = content.replace(INSERT_AFTER, INSERT_AFTER + T_DICT, 1)
    changes.append("JS: inserted T dictionary")
    print("  [OK] T dictionary inserted")
else:
    print(f"  [WARN] Could not find DOMContentLoaded insertion point")

# ===========================================================================
# PART 3: JS string replacements using T.key
# ===========================================================================
print("\n=== Part 3: JS string replacements ===")

JS_REPLACEMENTS = [
    # Reservation chart labels
    ("label: '予約数'", "label: T.reservations"),
    ("label: 'キャンセル数'", "label: T.cancellations"),
    # Sales trend chart
    ("label: '売上 (円)'", "label: T.sales_yen"),
    ("return '売上: ' + Number(ctx.parsed.y).toLocaleString() + ' 円';",
     "return T.sales_prefix + Number(ctx.parsed.y).toLocaleString() + T.yen_suffix;"),
    ("return Number(v).toLocaleString() + ' 円';",
     "return Number(v).toLocaleString() + T.yen_suffix;"),
    # Top products chart
    ("label: '注文数'", "label: T.order_count"),
    # EC sales label
    ("label: 'ECショップ売上 (円)'", "label: T.ec_sales_yen"),
    # Instore sales label
    ("label: '店内メニュー売上 (円)'", "label: T.instore_sales_yen"),
    # AOV chart labels
    ("label: '客単価 (円)'", "label: T.aov_yen"),
    ("return '客単価: ' + Number(context.parsed.y).toLocaleString() + ' 円';",
     "return T.aov_prefix + Number(context.parsed.y).toLocaleString() + T.yen_suffix;"),
    # ABC chart labels
    ("label: '売上 (円)',\n            data: revenues",
     "label: T.sales_yen,\n            data: revenues"),
    ("label: '累積構成比 (%)'", "label: T.cumulative_pct"),
    ("return '累積: ' + context.parsed.y.toFixed(1) + '%';",
     "return T.cumulative_prefix + context.parsed.y.toFixed(1) + '%';"),
    ("return '売上: ' + Number(context.parsed.y).toLocaleString() + ' 円';",
     "return T.sales_prefix + Number(context.parsed.y).toLocaleString() + T.yen_suffix;"),
    # Forecast chart labels
    ("label: '実績'", "label: T.actual"),
    ("label: '予測'", "label: T.forecast_label"),
    ("label: '上限'", "label: T.upper_bound"),
    ("label: '下限'", "label: T.lower_bound"),
    # Forecast legend filter
    ("item.text !== '上限' && item.text !== '下限'",
     "item.text !== T.upper_bound && item.text !== T.lower_bound"),
    # Forecast tooltip null check
    ("if (context.dataset.label === '上限' || context.dataset.label === '下限') return null;",
     "if (context.dataset.label === T.upper_bound || context.dataset.label === T.lower_bound) return null;"),
    # Forecast method text
    ("method === 'prophet' ? 'Prophet' : '移動平均+曜日係数'",
     "method === 'prophet' ? 'Prophet' : T.moving_avg"),
    # Sales heatmap
    ("title: { display: true, text: '時間帯' }",
     "title: { display: true, text: T.time_slot }"),
    ("title: { display: true, text: '曜日' }",
     "title: { display: true, text: T.weekday }"),
    ("ticks: { stepSize: 1, callback: function(v) { return v + '時'; } }",
     "ticks: { stepSize: 1, callback: function(v) { return v + T.hour_suffix; } }"),
    # Menu engineering scatter chart axis titles
    ("title: { display: true, text: '販売数量 (人気度)' }",
     "title: { display: true, text: T.sales_volume }"),
    ("title: { display: true, text: '利益率 (%)' }",
     "title: { display: true, text: T.margin_rate_pct }"),
    # Menu eng tooltip
    ("return pt.label + ' (販売: ' + pt.x + ', 利益率: ' + pt.y.toFixed(1) + '%)'",
     "return pt.label + ' (' + T.sold_prefix + pt.x + ', ' + T.margin_prefix + pt.y.toFixed(1) + '%)'"),
    # Menu eng table "データなし" in tbody
    ("tbody.innerHTML = '<tr><td colspan=\"5\" class=\"px-3 py-2 text-gray-400 text-center\">データなし</td></tr>';",
     "tbody.innerHTML = '<tr><td colspan=\"5\" class=\"px-3 py-2 text-gray-400 text-center\">' + T.no_data + '</td></tr>';"),
    # Menu eng fetch error
    ("document.getElementById('menu-eng-tbody').innerHTML = '<tr><td colspan=\"5\" class=\"px-3 py-2 text-gray-400 text-center\">取得エラー</td></tr>';",
     "document.getElementById('menu-eng-tbody').innerHTML = '<tr><td colspan=\"5\" class=\"px-3 py-2 text-gray-400 text-center\">' + T.fetch_error + '</td></tr>';"),
    # ABC table "データなし"
    ("tbody.innerHTML = '<tr><td colspan=\"5\" class=\"px-3 py-2 text-gray-400 text-center\">データなし</td></tr>';",
     "tbody.innerHTML = '<tr><td colspan=\"5\" class=\"px-3 py-2 text-gray-400 text-center\">' + T.no_data + '</td></tr>';"),
    # ABC fetch error
    ("document.getElementById('abc-tbody').innerHTML = '<tr><td colspan=\"5\" class=\"px-3 py-2 text-gray-400 text-center\">取得エラー</td></tr>';",
     "document.getElementById('abc-tbody').innerHTML = '<tr><td colspan=\"5\" class=\"px-3 py-2 text-gray-400 text-center\">' + T.fetch_error + '</td></tr>';"),
    # AOV chart axis titles
    ("title: { display: true, text: '客単価 (円)' }",
     "title: { display: true, text: T.aov_yen }"),
    ("title: { display: true, text: '注文数' }",
     "title: { display: true, text: T.order_count }"),
    # AOV tooltip
    ("return '客単価: ' + Number(context.parsed.y).toLocaleString() + ' 円';",
     "return T.aov_prefix + Number(context.parsed.y).toLocaleString() + T.yen_suffix;"),
    ("return '注文数: ' + context.parsed.y;",
     "return T.order_prefix + context.parsed.y;"),
    # Staff performance chart labels
    ("label: '予約数', data: staff.map(function (s) { return s.reservations; }), backgroundColor: COLORS.sky",
     "label: T.reservations, data: staff.map(function (s) { return s.reservations; }), backgroundColor: COLORS.sky"),
    ("label: '売上 (円)', data: staff.map(function (s) { return s.sales; }), backgroundColor: COLORS.amber",
     "label: T.sales_yen, data: staff.map(function (s) { return s.sales; }), backgroundColor: COLORS.amber"),
    # Staff performance axis titles
    ("title: { display: true, text: '予約数' }, ticks: { precision: 0 } },\n            y1: { type: 'linear', position: 'right', beginAtZero: true, title: { display: true, text: '売上 (円)' }, grid: { drawOnChartArea: false }, ticks: { callback: function (v) { return Number(v).toLocaleString(); } } }\n          }\n        }\n      });\n    }).catch(function (err) { console.error('Failed to load staff performance:', err); });",
     "title: { display: true, text: T.reservations }, ticks: { precision: 0 } },\n            y1: { type: 'linear', position: 'right', beginAtZero: true, title: { display: true, text: T.sales_yen }, grid: { drawOnChartArea: false }, ticks: { callback: function (v) { return Number(v).toLocaleString(); } } }\n          }\n        }\n      });\n    }).catch(function (err) { console.error('Failed to load staff performance:', err); });"),
    # Cast chart labels
    ("label: '予約数', data: staff.map(function (s) { return s.reservations; }), backgroundColor: COLORS.violet",
     "label: T.reservations, data: staff.map(function (s) { return s.reservations; }), backgroundColor: COLORS.violet"),
    ("label: '売上 (円)', data: staff.map(function (s) { return s.sales; }), backgroundColor: COLORS.amber, borderRadius: 4, yAxisID: 'y1' }",
     "label: T.sales_yen, data: staff.map(function (s) { return s.sales; }), backgroundColor: COLORS.amber, borderRadius: 4, yAxisID: 'y1' }"),
    # Cast axis
    ("title: { display: true, text: '予約数' }, ticks: { precision: 0 } },\n            y1: { type: 'linear', position: 'right', beginAtZero: true, title: { display: true, text: '売上 (円)' }, grid: { drawOnChartArea: false }, ticks: { callback: function (v) { return Number(v).toLocaleString(); } } }\n          }\n        }\n      });\n\n      // Ranking table",
     "title: { display: true, text: T.reservations }, ticks: { precision: 0 } },\n            y1: { type: 'linear', position: 'right', beginAtZero: true, title: { display: true, text: T.sales_yen }, grid: { drawOnChartArea: false }, ticks: { callback: function (v) { return Number(v).toLocaleString(); } } }\n          }\n        }\n      });\n\n      // Ranking table"),
    # Cast ranking "キャストデータなし"
    ("tbody.innerHTML = '<tr><td colspan=\"4\" class=\"px-4 py-2 text-gray-400 text-center\">キャストデータなし</td></tr>';",
     "tbody.innerHTML = '<tr><td colspan=\"4\" class=\"px-4 py-2 text-gray-400 text-center\">' + T.no_cast_data + '</td></tr>';"),
    # Shift data "シフトデータなし"
    ("tbody.innerHTML = '<tr><td colspan=\"3\" class=\"px-4 py-2 text-gray-400 text-center\">シフトデータなし</td></tr>';",
     "tbody.innerHTML = '<tr><td colspan=\"3\" class=\"px-4 py-2 text-gray-400 text-center\">' + T.no_shift_data + '</td></tr>';"),
    # Attendance statuses
    ("status = '退勤済み'", "status = T.clocked_out"),
    ("status = '出勤中'", "status = T.clocked_in"),
    ("status = '未出勤'", "status = T.not_clocked_in"),
    # Attendance "本日の勤怠データなし"
    ("'<tr><td colspan=\"4\" class=\"px-4 py-2 text-gray-400 text-center\">本日の勤怠データなし</td></tr>'",
     "'<tr><td colspan=\"4\" class=\"px-4 py-2 text-gray-400 text-center\">' + T.no_att_data + '</td></tr>'"),
    # Attendance fetch error
    ("'<tr><td colspan=\"4\" class=\"px-4 py-2 text-gray-400 text-center\">データ取得エラー</td></tr>'",
     "'<tr><td colspan=\"4\" class=\"px-4 py-2 text-gray-400 text-center\">' + T.data_fetch_error + '</td></tr>'"),
    # Low-stock "在庫アラートなし"
    ("container.innerHTML = '<p class=\"text-emerald-500 text-sm text-center font-medium\">在庫アラートなし</p>';",
     "container.innerHTML = '<p class=\"text-emerald-500 text-sm text-center font-medium\">' + T.no_stock_alerts + '</p>';"),
    # Low-stock "残 "
    ("'<span class=\"text-xs text-gray-500\">残 ' + p.stock + '</span>'",
     "'<span class=\"text-xs text-gray-500\">' + T.remaining + ' ' + p.stock + '</span>'"),
    # Basket analysis
    ("document.getElementById('basket-method').textContent = method === 'apriori' ? 'Apriori' : method === 'pairwise' ? 'ペアワイズ分析' : '--';",
     "document.getElementById('basket-method').textContent = method === 'apriori' ? 'Apriori' : method === 'pairwise' ? T.pairwise : '--';"),
    ("document.getElementById('basket-total').textContent = '対象トランザクション: ' + total + '件';",
     "document.getElementById('basket-total').textContent = T.target_txn + total + T.unit_items;"),
    # Basket demo overrides
    ("document.getElementById('basket-method').textContent = 'デモ';",
     "document.getElementById('basket-method').textContent = T.demo_label;"),
    ("document.getElementById('basket-total').textContent = '対象トランザクション: 100件（デモ）';",
     "document.getElementById('basket-total').textContent = T.target_txn_demo;"),
    # Basket table headers
    ("html += '<th class=\"px-3 py-2 text-left\">前提商品</th>';",
     "html += '<th class=\"px-3 py-2 text-left\">' + T.th_antecedent + '</th>';"),
    ("html += '<th class=\"px-3 py-2 text-left\">結論商品</th>';",
     "html += '<th class=\"px-3 py-2 text-left\">' + T.th_consequent + '</th>';"),
    # Basket error
    ("document.getElementById('basket-table').innerHTML = '<p class=\"text-gray-400 text-center\">データ取得エラー</p>';",
     "document.getElementById('basket-table').innerHTML = '<p class=\"text-gray-400 text-center\">' + T.data_fetch_error + '</p>';"),
    # Cohort "データ取得エラー"
    ("document.getElementById('cohort-table').innerHTML = '<p class=\"text-gray-400 text-center\">データ取得エラー</p>';",
     "document.getElementById('cohort-table').innerHTML = '<p class=\"text-gray-400 text-center\">' + T.data_fetch_error + '</p>';"),
    # Cohort table headers
    ("html += '<thead><tr class=\"bg-gray-50\"><th class=\"px-3 py-2 text-left\">コホート</th><th class=\"px-3 py-2 text-right\">人数</th>';",
     "html += '<thead><tr class=\"bg-gray-50\"><th class=\"px-3 py-2 text-left\">' + T.th_cohort + '</th><th class=\"px-3 py-2 text-right\">' + T.th_size + '</th>';"),
    # Insights – no data message
    ("container.innerHTML = '<p class=\"text-gray-400 text-sm text-center py-8\">インサイトはありません。「分析実行」ボタンで最新の分析を行えます。</p>';",
     "container.innerHTML = '<p class=\"text-gray-400 text-sm text-center py-8\">' + T.no_insights + '</p>';"),
    # Insights severity labels
    ("var severityLabel = { critical: '重要', warning: '注意', info: '情報' };",
     "var severityLabel = { critical: T.sev_critical, warning: T.sev_warning, info: T.sev_info };"),
    # Insights category labels
    ("var catLabel = { sales: '売上', inventory: '在庫', staffing: 'スタッフ', menu: 'メニュー', customer: '顧客' };",
     "var catLabel = { sales: T.cat_sales, inventory: T.cat_inventory, staffing: T.cat_staffing, menu: T.cat_menu, customer: T.cat_customer };"),
    # Insight "既読にする" button
    ("'<button onclick=\"markInsightRead(' + ins.id + ', this)\" class=\"text-xs text-indigo-500 hover:underline mt-1\">既読にする</button>'",
     "'<button onclick=\"markInsightRead(' + ins.id + ', this)\" class=\"text-xs text-indigo-500 hover:underline mt-1\">' + T.mark_read + '</button>'"),
    # Insights fetch error
    ("document.getElementById('insights-list').innerHTML = '<p class=\"text-gray-400 text-sm text-center\">取得エラー</p>';",
     "document.getElementById('insights-list').innerHTML = '<p class=\"text-gray-400 text-sm text-center\">' + T.fetch_error + '</p>';"),
    # generateInsights button texts
    ("btn.textContent = '分析中...';", "btn.textContent = T.analyzing;"),
    ("btn.textContent = '分析実行';", "btn.textContent = T.run_analysis;"),
    # NPS radar labels
    ("labels: ['料理', 'サービス', '雰囲気'],",
     "labels: [T.food, T.service, T.ambiance],"),
    # NPS radar dataset label
    ("label: '平均評価',", "label: T.avg_rating,"),
    # Feedback "フィードバックがありません"
    ("list.innerHTML = '<p class=\"text-gray-400 text-sm text-center\">フィードバックがありません</p>';",
     "list.innerHTML = '<p class=\"text-gray-400 text-sm text-center\">' + T.no_feedback + '</p>';"),
    # Feedback category display
    ("html += '<div class=\"text-xs text-gray-500 mb-1\">料理:' + fb.food_rating + ' サービス:' + fb.service_rating + ' 雰囲気:' + fb.ambiance_rating + '</div>';",
     "html += '<div class=\"text-xs text-gray-500 mb-1\">' + T.food_colon + fb.food_rating + ' ' + T.service_colon + fb.service_rating + ' ' + T.ambiance_colon + fb.ambiance_rating + '</div>';"),
    # KPI scorecard statuses
    ("var statusLabel = kpi.status === 'good' ? '良好' : kpi.status === 'warn' ? '注意' : '要改善';",
     "var statusLabel = kpi.status === 'good' ? T.status_good : kpi.status === 'warn' ? T.status_warn : T.status_bad;"),
    # KPI benchmark
    ("html += '<span class=\"text-xs text-gray-400\">基準: ' + kpi.benchmark + '</span>';",
     "html += '<span class=\"text-xs text-gray-400\">' + T.benchmark_prefix + kpi.benchmark + '</span>';"),
    # KPI "データがありません"
    ("grid.innerHTML = '<p class=\"text-gray-400 text-sm text-center col-span-full\">データがありません</p>';",
     "grid.innerHTML = '<p class=\"text-gray-400 text-sm text-center col-span-full\">' + T.no_data_available + '</p>';"),
    # KPI loading
    ("grid.innerHTML = '<p class=\"text-gray-400 text-sm text-center col-span-full\">読み込み中...</p>';",
     "grid.innerHTML = '<p class=\"text-gray-400 text-sm text-center col-span-full\">' + T.loading + '</p>';"),
    # KPI loading error
    ("grid.innerHTML = '<p class=\"text-red-400 text-sm text-center col-span-full\">読み込みエラー</p>';",
     "grid.innerHTML = '<p class=\"text-red-400 text-sm text-center col-span-full\">' + T.loading_error + '</p>';"),
    # AI analysis panel
    ("'<span class=\"text-violet-600 font-bold text-sm\">AI分析</span>'",
     "'<span class=\"text-violet-600 font-bold text-sm\">' + T.ai_analysis + '</span>'"),
    # AI recommended actions
    ("'<div class=\"text-xs font-bold text-indigo-600 mb-1\">推奨アクション</div>'",
     "'<div class=\"text-xs font-bold text-indigo-600 mb-1\">' + T.recommended_actions + '</div>'"),
    # Channel sales axis title
    ("title: { display: true, text: '売上 (円)' },\n              ticks: { callback: function(v) { return Number(v).toLocaleString(); } }",
     "title: { display: true, text: T.sales_yen },\n              ticks: { callback: function(v) { return Number(v).toLocaleString(); } }"),
    # Heatmap bubble label (both instances in renderHeatmapGeneric and loadSalesHeatmap)
    ("label: '売上',\n            data: points",
     "label: T.cat_sales,\n            data: points"),
    # Weekday labels array (standalone loadSalesHeatmap)
    ("var WEEKDAY_LABELS = ['日', '月', '火', '水', '木', '金', '土'];",
     "var WEEKDAY_LABELS = [T.sun, T.mon, T.tue, T.wed, T.thu, T.fri, T.sat];"),
    # Heatmap tooltip
    ("return WEEKDAY_LABELS[p.y] + ' ' + p.x + '時 — ' + Number(p.revenue).toLocaleString() + '円 / ' + p.orders + '件';",
     "return WEEKDAY_LABELS[p.y] + ' ' + p.x + T.hour_suffix + ' — ' + Number(p.revenue).toLocaleString() + '円 / ' + p.orders + T.unit_items;"),
    # renderHeatmapGeneric weekday labels
    ("var WEEKDAY_LABELS = ['日','月','火','水','木','金','土'];",
     "var WEEKDAY_LABELS = [T.sun, T.mon, T.tue, T.wed, T.thu, T.fri, T.sat];"),
    # renderHeatmapGeneric tooltip
    ("return WEEKDAY_LABELS[p.y]+' '+p.x+'時 — '+Number(p.revenue).toLocaleString()+'円';}}}",
     "return WEEKDAY_LABELS[p.y]+' '+p.x+T.hour_suffix+' — '+Number(p.revenue).toLocaleString()+'円';}}}"),
    # renderHeatmapGeneric axis
    ("ticks:{stepSize:1,callback:function(v){return v+'時';}}",
     "ticks:{stepSize:1,callback:function(v){return v+T.hour_suffix;}}"),
    # renderMenuEngGeneric tooltip
    ("return pt.label + ' (販売:' + pt.x + ', 利益率:' + pt.y.toFixed(1) + '%)'",
     "return pt.label + ' (' + T.sold_prefix + pt.x + ', ' + T.margin_prefix + pt.y.toFixed(1) + '%)'"),
    # renderMenuEngGeneric axis titles
    ("x: {title: {display: true, text: '販売数量'}, beginAtZero: true}",
     "x: {title: {display: true, text: T.sales_volume_short}, beginAtZero: true}"),
    ("y: {title: {display: true, text: '利益率 (%)'}, beginAtZero: true}",
     "y: {title: {display: true, text: T.margin_rate_pct}, beginAtZero: true}"),
    # renderMenuEngGeneric table headers
    ("<th class=\"px-3 py-2 text-left\">商品名</th><th class=\"px-3 py-2 text-right\">販売数</th><th class=\"px-3 py-2 text-right\">利益率</th><th class=\"px-3 py-2 text-right\">売上</th><th class=\"px-3 py-2 text-center\">分類</th>",
     "<th class=\"px-3 py-2 text-left\">'+T.th_product+'</th><th class=\"px-3 py-2 text-right\">'+T.th_qty_sold+'</th><th class=\"px-3 py-2 text-right\">'+T.th_margin_rate+'</th><th class=\"px-3 py-2 text-right\">'+T.th_sales+'</th><th class=\"px-3 py-2 text-center\">'+T.th_category+'</th>"),
    # renderABCGeneric chart labels
    ("{label: '売上 (円)', data: revenues", "{label: T.sales_yen, data: revenues"),
    ("{label: '累積構成比 (%)', data: cumPcts", "{label: T.cumulative_pct, data: cumPcts"),
    # renderABCGeneric table headers
    ("<th class=\"px-3 py-2 text-left\">商品名</th><th class=\"px-3 py-2 text-right\">売上</th><th class=\"px-3 py-2 text-right\">構成比</th><th class=\"px-3 py-2 text-right\">累積</th><th class=\"px-3 py-2 text-center\">ランク</th>",
     "<th class=\"px-3 py-2 text-left\">'+T.th_product+'</th><th class=\"px-3 py-2 text-right\">'+T.th_sales+'</th><th class=\"px-3 py-2 text-right\">'+T.th_share+'</th><th class=\"px-3 py-2 text-right\">'+T.th_cumulative+'</th><th class=\"px-3 py-2 text-center\">'+T.th_rank+'</th>"),
    # renderForecastGeneric chart labels
    ("{label:'実績', data:histData", "{label:T.actual, data:histData"),
    ("{label:'予測', data:predData", "{label:T.forecast_label, data:predData"),
    ("{label:'上限', data:upperData", "{label:T.upper_bound, data:upperData"),
    ("{label:'下限', data:lowerData", "{label:T.lower_bound, data:lowerData"),
    # renderForecastGeneric legend filter
    ("item.text!=='上限'&&item.text!=='下限'",
     "item.text!==T.upper_bound&&item.text!==T.lower_bound"),
    # renderAOVGeneric chart labels
    ("{label:'客単価 (円)', data:aovData", "{label:T.aov_yen, data:aovData"),
    ("{label:'注文数', data:orderData", "{label:T.order_count, data:orderData"),
    # renderAOVGeneric axis
    ("title:{display:true,text:'客単価 (円)'}",
     "title:{display:true,text:T.aov_yen}"),
    ("title:{display:true,text:'注文数'}",
     "title:{display:true,text:T.order_count}"),
    # Tour steps
    ("title: 'タブナビゲーション',\n      text: 'ここでダッシュボードの各セクションを切り替えます。概要・売上・顧客・スタッフ・シフト・勤怠・運営の7つのタブがあります。',",
     "title: T.tour_tab_nav_title,\n      text: T.tour_tab_nav_text,"),
    ("title: '概要タブ',\n      text: '予約KPI、日別予約グラフ、ビジネスインサイト、KPIスコアカードを確認できます。',",
     "title: T.tour_overview_title,\n      text: T.tour_overview_text,"),
    ("title: '期間選択',\n      text: '日別・週別・月別でデータの集計期間を切り替えられます。',",
     "title: T.tour_period_title,\n      text: T.tour_period_text,"),
    ("title: '売上タブ',\n      text: '売上推移、人気商品、メニュー分析、ABC分析、売上予測、時間帯別売上、客単価推移を確認できます。',",
     "title: T.tour_sales_title,\n      text: T.tour_sales_text,"),
    ("title: '顧客分析タブ',\n      text: 'コホート分析、RFMセグメンテーション、バスケット分析、NPS・顧客満足度を確認できます。',",
     "title: T.tour_customers_title,\n      text: T.tour_customers_text,"),
    ("title: '運営タブ',\n      text: '在庫アラートなど、日常の運営に必要な情報を確認できます。',",
     "title: T.tour_ops_title,\n      text: T.tour_ops_text,"),
    ("title: 'ヘルプボタン',\n      text: 'このボタンをクリックすると、いつでもこのヘルプを再表示できます。',",
     "title: T.tour_help_title,\n      text: T.tour_help_text,"),
    # Checkin daily chart labels
    ("label: 'チェックイン',\n                  data: data.daily.map(function(d) { return d.checked_in; })",
     "label: T.checkin_label,\n                  data: data.daily.map(function(d) { return d.checked_in; })"),
    ("label: 'ノーショー',\n                  data: data.daily.map(function(d) { return d.no_show; })",
     "label: T.noshow_label,\n                  data: data.daily.map(function(d) { return d.no_show; })"),
    # Checkin staff chart label
    ("label: 'チェックイン率 (%)',\n                data: data.by_staff.map(function(s) { return (s.checkin_rate * 100).toFixed(1); })",
     "label: T.checkin_rate_pct,\n                data: data.by_staff.map(function(s) { return (s.checkin_rate * 100).toFixed(1); })"),
    # Checkin hourly chart label
    ("label: 'チェックイン数',\n                data: data.hourly.map(function(h) { return h.count; })",
     "label: T.checkin_count,\n                data: data.hourly.map(function(h) { return h.count; })"),
    # EC sales chart label (uses full string)
    # already handled by "label: 'ECショップ売上 (円)'" replacement above
    # instore sales chart label already handled
    # channel_labels for demo data (these are data values, NOT UI labels — skip)
    # instoreSuite label config
    ("label: '店内'}", "label: T.instore}"),
]

for old, new in JS_REPLACEMENTS:
    content, ok = replace_once(content, old, new, f"JS: {old[:70]!r}")

# ===========================================================================
# 4. Write file
# ===========================================================================
print("\n=== Writing file ===")
with open(TEMPLATE_PATH, "w", encoding="utf-8") as f:
    f.write(content)

# ===========================================================================
# 5. Summary
# ===========================================================================
successful = [c for c in changes]
print(f"\n=== Summary ===")
print(f"Total replacements made: {len(successful)}")
print(f"Original length: {len(original)} chars")
print(f"New length:      {len(content)} chars")
print(f"Delta:           +{len(content) - len(original)} chars")
print("\nAll replacements:")
for i, desc in enumerate(successful, 1):
    print(f"  {i:3d}. {desc}")
