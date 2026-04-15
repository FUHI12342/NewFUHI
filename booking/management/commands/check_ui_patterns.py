"""
テンプレートUIパターンチェッカー

過去に修正指示された再発しやすいUI/UXの問題パターンを
テンプレートファイルから静的に検出する。

使用例:
    python manage.py check_ui_patterns              # 全テンプレートチェック
    python manage.py check_ui_patterns --fix        # 自動修正（可能な場合）
    python manage.py check_ui_patterns --json       # JSON出力（CI/CD用）
    python manage.py check_ui_patterns --record     # ERROR-CHECKLIST.mdに記録
"""

import json
import os
import re
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


# チェックルール定義
RULES = [
    {
        "id": "FOUC-001",
        "severity": "CRITICAL",
        "title": "Alpine.js x-cloak CSS未定義",
        "description": (
            "x-cloak属性を使用しているが [x-cloak] { display: none !important; } "
            "がstyleブロックに存在しない。ページ読み込み時にFOUC（Flash of Unstyled Content）が発生する。"
        ),
        "check": "_check_xclock_css_missing",
    },
    {
        "id": "FOUC-002",
        "severity": "HIGH",
        "title": "モーダル/オーバーレイにinline display:none未設定",
        "description": (
            "x-show + x-cloak のモーダル/オーバーレイ要素に style=\"display:none\" が"
            "未設定。CSSキャッシュの遅延時にモーダルが一瞬表示される。"
        ),
        "check": "_check_modal_inline_style",
    },
    {
        "id": "FOUC-003",
        "severity": "MEDIUM",
        "title": "ドロップダウンにinline display:none未設定",
        "description": (
            "x-show + x-cloak のドロップダウン/メニュー要素に style=\"display:none\" "
            "が未設定。"
        ),
        "check": "_check_dropdown_inline_style",
    },
    {
        "id": "FOUC-004",
        "severity": "HIGH",
        "title": "x-show切替spanにx-cloak未設定（保存/保存中パターン）",
        "description": (
            "x-show で切り替える「保存中」「送信中」「読み込み中」等のspanに"
            "x-cloakが未設定。Alpine初期化前に両方のテキストが同時表示される。"
        ),
        "check": "_check_loading_span_cloak",
    },
    {
        "id": "TOUR-001",
        "severity": "HIGH",
        "title": "ツアーガイドのTOUR_AUTO_START未設定",
        "description": (
            "admin_tour.jsを読み込んでいるがwindow.TOUR_AUTO_STARTが設定されていない。"
            "SiteSettingsの設定が反映されない。"
        ),
        "check": "_check_tour_auto_start",
    },
    {
        "id": "TOUR-002",
        "severity": "MEDIUM",
        "title": "ツアーステップのセレクタが存在しない可能性",
        "description": (
            "TOUR_STEPSで指定されたCSSセレクタがテンプレート内に見つからない。"
            "ツアーステップがスキップされる可能性がある。"
        ),
        "check": "_check_tour_selectors",
    },
    {
        "id": "A11Y-001",
        "severity": "MEDIUM",
        "title": "モーダルにaria属性未設定",
        "description": (
            "モーダル/ダイアログ要素に role=\"dialog\" や aria-modal=\"true\" が未設定。"
        ),
        "check": "_check_modal_aria",
    },
    {
        "id": "STYLE-001",
        "severity": "LOW",
        "title": "インラインstyle多用（10箇所以上）",
        "description": (
            "1ファイルにインラインstyleが10箇所以上。CSSクラスへの抽出を推奨。"
        ),
        "check": "_check_inline_style_count",
    },
]


class Command(BaseCommand):
    help = "テンプレートのUIパターンをチェックし、既知の問題を検出する"

    def add_arguments(self, parser):
        parser.add_argument(
            "--json", action="store_true",
            help="JSON形式で出力",
        )
        parser.add_argument(
            "--record", action="store_true",
            help="結果をINFO/ERROR-CHECKLIST.mdに記録",
        )
        parser.add_argument(
            "--severity", type=str, default="LOW",
            choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
            help="最低報告レベル（デフォルト: LOW）",
        )
        parser.add_argument(
            "paths", nargs="*", type=str,
            help="チェック対象パス（省略時: templates/admin/）",
        )

    def handle(self, *args, **options):
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        min_severity = severity_order.get(options["severity"], 3)

        # チェック対象ファイル収集
        target_paths = options["paths"] or [
            os.path.join(settings.BASE_DIR, "templates", "admin"),
        ]

        template_files = []
        for target in target_paths:
            target_path = Path(target)
            if target_path.is_file():
                template_files.append(target_path)
            elif target_path.is_dir():
                template_files.extend(target_path.rglob("*.html"))

        if not template_files:
            self.stderr.write(self.style.WARNING("チェック対象ファイルなし"))
            return

        # チェック実行
        all_findings = []
        for filepath in sorted(template_files):
            content = filepath.read_text(encoding="utf-8")
            rel_path = str(filepath.relative_to(settings.BASE_DIR))

            for rule in RULES:
                if severity_order[rule["severity"]] > min_severity:
                    continue

                checker = globals().get(rule["check"])
                if not checker:
                    continue

                findings = checker(content, rel_path)
                for finding in findings:
                    finding.update({
                        "rule_id": rule["id"],
                        "severity": rule["severity"],
                        "title": rule["title"],
                        "description": rule["description"],
                    })
                all_findings.append(findings)

        # フラット化
        findings = [f for group in all_findings for f in group]

        # ソート（severity順）
        findings.sort(key=lambda f: severity_order.get(f["severity"], 99))

        if options["json"]:
            self.stdout.write(json.dumps(findings, ensure_ascii=False, indent=2))
        else:
            self._print_report(findings, template_files)

        if options["record"] and findings:
            self._record_to_checklist(findings)

        # 終了コード
        critical_count = sum(
            1 for f in findings if f["severity"] == "CRITICAL"
        )
        if critical_count > 0:
            self.stderr.write(
                self.style.ERROR(
                    f"\n{critical_count}件のCRITICAL問題が検出されました"
                )
            )
            raise SystemExit(1)

    def _print_report(self, findings, template_files):
        """人間可読レポートを出力"""
        if not findings:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n{len(template_files)}ファイルをチェック — 問題なし"
                )
            )
            return

        severity_styles = {
            "CRITICAL": self.style.ERROR,
            "HIGH": self.style.WARNING,
            "MEDIUM": self.style.NOTICE,
            "LOW": lambda x: x,
        }

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f" UIパターンチェック結果: {len(findings)}件検出")
        self.stdout.write(f"{'='*60}\n")

        for f in findings:
            style = severity_styles.get(f["severity"], lambda x: x)
            self.stdout.write(style(
                f"[{f['severity']}] {f['rule_id']}: {f['title']}"
            ))
            self.stdout.write(f"  ファイル: {f['file']}")
            if f.get("line"):
                self.stdout.write(f"  行: {f['line']}")
            if f.get("detail"):
                self.stdout.write(f"  詳細: {f['detail']}")
            self.stdout.write("")

        # サマリー
        by_sev = {}
        for f in findings:
            by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
        summary_parts = [f"{sev}: {cnt}" for sev, cnt in by_sev.items()]
        self.stdout.write(f"合計: {', '.join(summary_parts)}")

    def _record_to_checklist(self, findings):
        """ERROR-CHECKLIST.mdに記録"""
        checklist_path = Path(settings.BASE_DIR) / "INFO" / "ERROR-CHECKLIST.md"
        checklist_path.parent.mkdir(exist_ok=True)

        today = date.today().isoformat()

        if checklist_path.exists():
            content = checklist_path.read_text(encoding="utf-8")
        else:
            content = (
                "# エラーチェックリスト（再発防止マニュアル）\n\n"
                f"> 最終更新: {today}\n\n"
                "## UI/テンプレート\n\n"
                "| # | 問題 | 対策 | 結果 | 日付 |\n"
                "|---|------|------|------|------|\n"
            )

        section = "## UI/テンプレート"
        if section not in content:
            content += (
                f"\n{section}\n\n"
                "| # | 問題 | 対策 | 結果 | 日付 |\n"
                "|---|------|------|------|------|\n"
            )

        # 既存行数カウント
        lines = content.split("\n")
        row_count = 0
        in_section = False
        insert_idx = -1
        for i, line in enumerate(lines):
            if line.strip() == section:
                in_section = True
                continue
            if in_section and line.startswith("## "):
                insert_idx = i
                break
            if (
                in_section
                and line.strip().startswith("|")
                and "---" not in line
                and "問題" not in line
            ):
                row_count += 1
                insert_idx = i + 1

        if insert_idx == -1:
            insert_idx = len(lines)

        new_rows = []
        for f in findings:
            row_count += 1
            problem = f"{f['rule_id']}: {f['title']} ({f['file']})"
            fix = f["description"][:60]
            new_rows.append(
                f"| {row_count} | {problem} | {fix} | 未解決 | {today} |"
            )

        for row in reversed(new_rows):
            lines.insert(insert_idx, row)

        # 最終更新日を更新
        updated = "\n".join(lines)
        updated = re.sub(
            r"最終更新: \d{4}-\d{2}-\d{2}",
            f"最終更新: {today}",
            updated,
        )

        checklist_path.write_text(updated, encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{len(new_rows)}件をERROR-CHECKLIST.mdに記録しました"
            )
        )


# ── チェック関数 ──────────────────────────────

def _check_xclock_css_missing(content, filepath):
    """x-cloak使用テンプレートに[x-cloak] CSSルールが存在するか"""
    findings = []
    if "x-cloak" not in content:
        return findings

    has_css_rule = bool(re.search(
        r"\[x-cloak\]\s*\{[^}]*display\s*:\s*none",
        content,
    ))

    if not has_css_rule:
        findings.append({
            "file": filepath,
            "line": None,
            "detail": (
                "x-cloakが使用されているが [x-cloak] { display: none !important; } "
                "がstyleブロックにない"
            ),
        })
    return findings


def _check_modal_inline_style(content, filepath):
    """モーダル/オーバーレイにdisplay:noneが設定されているか"""
    findings = []
    lines = content.split("\n")

    modal_patterns = [
        re.compile(r'class="[^"]*(?:modal|overlay|tpl-overlay|dialog)[^"]*"'),
        re.compile(r'class="[^"]*(?:Modal|Overlay|Dialog)[^"]*"'),
    ]

    for i, line in enumerate(lines, 1):
        if "x-show" not in line or "x-cloak" not in line:
            continue

        is_modal = any(p.search(line) for p in modal_patterns)
        if not is_modal:
            continue

        has_display_none = bool(re.search(
            r'style="[^"]*display\s*:\s*none',
            line,
        ))

        if not has_display_none:
            findings.append({
                "file": filepath,
                "line": i,
                "detail": "モーダル/オーバーレイにstyle=\"display:none\"が未設定",
            })

    return findings


def _check_dropdown_inline_style(content, filepath):
    """ドロップダウン/メニューにdisplay:noneが設定されているか"""
    findings = []
    lines = content.split("\n")

    dropdown_patterns = [
        re.compile(r'class="[^"]*(?:drop|menu|popup|popover)[^"]*"', re.I),
    ]

    for i, line in enumerate(lines, 1):
        if "x-show" not in line or "x-cloak" not in line:
            continue

        is_dropdown = any(p.search(line) for p in dropdown_patterns)
        if not is_dropdown:
            continue

        has_display_none = bool(re.search(
            r'style="[^"]*display\s*:\s*none',
            line,
        ))

        if not has_display_none:
            findings.append({
                "file": filepath,
                "line": i,
                "detail": "ドロップダウン/メニューにstyle=\"display:none\"が未設定",
            })

    return findings


def _check_tour_auto_start(content, filepath):
    """admin_tour.jsを読み込んでいるテンプレートにTOUR_AUTO_STARTがあるか"""
    findings = []

    has_tour_js = "admin_tour.js" in content or "admin_tour" in content
    has_tour_steps = "TOUR_STEPS" in content

    if not has_tour_js or not has_tour_steps:
        return findings

    has_auto_start = "TOUR_AUTO_START" in content
    if not has_auto_start:
        findings.append({
            "file": filepath,
            "line": None,
            "detail": (
                "admin_tour.jsとTOUR_STEPSが定義されているが"
                "TOUR_AUTO_STARTが設定されていない"
            ),
        })

    return findings


def _check_tour_selectors(content, filepath):
    """TOUR_STEPSのセレクタがテンプレート内に存在するか"""
    findings = []

    match = re.search(
        r"TOUR_STEPS\s*=\s*\[(.*?)\];",
        content,
        re.DOTALL,
    )
    if not match:
        return findings

    tour_block = match.group(1)
    selectors = re.findall(r"selector:\s*['\"]([^'\"]+)['\"]", tour_block)

    for selector in selectors:
        # CSSセレクタからクラス名/ID名を抽出
        if selector.startswith("."):
            class_name = selector[1:].split(" ")[0].split(":")[0]
            if class_name not in content:
                findings.append({
                    "file": filepath,
                    "line": None,
                    "detail": (
                        f"ツアーセレクタ '{selector}' のクラスがテンプレート内に見つからない"
                    ),
                })
        elif selector.startswith("#"):
            id_name = selector[1:].split(" ")[0]
            if f'id="{id_name}"' not in content and f"id='{id_name}'" not in content:
                findings.append({
                    "file": filepath,
                    "line": None,
                    "detail": (
                        f"ツアーセレクタ '{selector}' のIDがテンプレート内に見つからない"
                    ),
                })

    return findings


def _check_modal_aria(content, filepath):
    """モーダル要素にaria属性が設定されているか"""
    findings = []
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        if "x-show" not in line:
            continue

        is_modal = bool(re.search(
            r'class="[^"]*(?:modal|overlay|tpl-overlay|dialog)[^"]*"',
            line,
            re.I,
        ))

        if not is_modal:
            continue

        has_aria = "role=" in line or "aria-modal" in line
        if not has_aria:
            findings.append({
                "file": filepath,
                "line": i,
                "detail": "モーダルにrole=\"dialog\"やaria-modal属性が未設定",
            })

    return findings


def _check_loading_span_cloak(content, filepath):
    """x-showで切り替える保存中/読み込み中spanにx-cloakがあるか"""
    findings = []
    lines = content.split("\n")
    loading_patterns = re.compile(
        r'x-show="(saving|loading|submitting|stSaving|pxSubmitting)'
    )

    for i, line in enumerate(lines, 1):
        if not loading_patterns.search(line):
            continue
        if "x-cloak" in line:
            continue
        findings.append({
            "file": filepath,
            "line": i,
            "detail": (
                "「保存中」「読み込み中」等のx-show要素にx-cloakが未設定。"
                "Alpine初期化前に両テキストが同時表示される。"
            ),
        })

    return findings


def _check_inline_style_count(content, filepath):
    """インラインスタイルの多用をチェック"""
    findings = []

    # style="..." のカウント（<style>ブロック内は除外）
    # 簡易的に行ベースでチェック
    in_style_block = False
    count = 0
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("<style"):
            in_style_block = True
        if "</style>" in stripped:
            in_style_block = False
            continue
        if in_style_block:
            continue

        count += len(re.findall(r'style="[^"]{10,}"', line))

    if count >= 10:
        findings.append({
            "file": filepath,
            "line": None,
            "detail": f"インラインstyleが{count}箇所（CSSクラスへの抽出推奨）",
        })

    return findings
