"""AI 下書き生成サービス — Gemini API で SNS 投稿文を生成"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

DRAFT_SYSTEM_PROMPT_BASE = """あなたは占いサロンのSNS投稿作成アシスタントです。
以下の共通ルールを厳守してください:

1. 店舗名・キャスト名は提供された情報から正確に記載すること
2. 事実と異なる情報（架空のキャスト名、存在しないサービス等）は絶対に書かないこと
3. 日本語で投稿すること
4. CTA（来店促進の一言）を含めること
5. 出力は投稿テキストのみ（説明やメタ情報は不要）"""

PLATFORM_RULES = {
    'x': """【X (Twitter) 専用ルール】
- **加重文字数200文字以内**に厳守（全角=2, 半角=1, 絵文字=2で計算）
- URLは投稿テキストに含めない（システムが自動で予約リンクを追加する）
- 改行は最小限（1〜2回まで）。段落分けはしない
- コンパクトで一息で読める文章にする
- 絵文字は2〜3個にとどめ、テキスト中に自然に配置
- ハッシュタグは1〜2個のみ、末尾に配置
- 「〜はこちら」「詳しくは」等のリンク誘導文は不要
- 長い宣伝調の文章は避け、友人にお知らせするような自然なトーンで書く
- 例: 「✨本日の出勤✨ ○○先生が11時からお待ちしております！ご予約お気軽に🔮 #占いサロン」""",

    'instagram': """【Instagram 専用ルール】
- 2200文字以内
- 読みやすさのため、段落ごとに空行（改行2回）を入れる
- 最初の1行は注目を引くキャッチコピー（絵文字付き）
- 本文は3〜5段落で構成（導入→キャスト紹介→サービス詳細→CTA）
- 絵文字を豊富に使用（各段落の先頭や文中に自然に配置）
- 末尾にハッシュタグブロックを設置（5〜10個、改行で本文と分離）
- ハッシュタグ例: #占い #タロット #占いサロン #当たる占い #恋愛占い
- 長めの丁寧な文章で世界観を伝える""",

    'gbp': """【Google Business Profile 専用ルール】
- 1500文字以内
- ビジネス寄りのフォーマルな文体
- 構造化された情報提示（箇条書きを活用）
- 改行で「本日の出勤」「サービス内容」「ご予約方法」等をセクション分け
- 絵文字は控えめ（0〜2個）
- ハッシュタグは不要
- 営業時間・アクセス情報があれば末尾に記載
- 来店・予約への明確なCTAを含める""",
}


def _call_gemini_for_draft(prompt, max_tokens=4096, temperature=0.8,
                           disable_thinking=False):
    """Gemini API 呼び出し（下書き生成用）"""
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        logger.error('GEMINI_API_KEY is not configured')
        return None

    url = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'gemini-2.5-flash:generateContent?key={api_key}'
    )

    body = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'maxOutputTokens': max_tokens,
            'temperature': temperature,
        },
    }
    if disable_thinking:
        body['generationConfig']['thinkingConfig'] = {'thinkingBudget': 0}

    payload = json.dumps(body).encode('utf-8')

    req = urllib.request.Request(
        url, data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                candidates = data.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if parts:
                        return parts[0].get('text', '').strip()
                return None
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                import time
                time.sleep(2 ** attempt)
                continue
            logger.error("Gemini API error %d: %s", e.code, e.read().decode())
            return None
        except Exception as e:
            logger.error("Gemini API call failed: %s", e)
            return None
    return None


def generate_daily_draft(store, target_date=None, platforms=None):
    """日次下書きを AI 生成して DraftPost レコードを作成

    Args:
        store: Store インスタンス
        target_date: 対象日 (None=今日)
        platforms: プラットフォームリスト (None=["x"])

    Returns:
        DraftPost or None
    """
    from booking.models import DraftPost
    from booking.services.sns_knowledge_service import build_knowledge_context

    if target_date is None:
        target_date = timezone.localdate()
    if platforms is None:
        platforms = ['x']

    context = build_knowledge_context(store, target_date)

    # プラットフォーム別ルールを構築
    platform_rules = '\n\n'.join(
        PLATFORM_RULES.get(p, '') for p in platforms if p in PLATFORM_RULES
    )
    if not platform_rules:
        platform_rules = PLATFORM_RULES['x']  # デフォルト

    platform_str = ', '.join(platforms)
    prompt = (
        f"{DRAFT_SYSTEM_PROMPT_BASE}\n\n"
        f"{platform_rules}\n\n"
        f"---\n投稿先: {platform_str}\n"
        f"対象日: {target_date.strftime('%Y年%m月%d日')}\n\n"
        f"---\n参照情報:\n{context}\n\n"
        f"---\n上記の情報とプラットフォーム専用ルールに従い、"
        f"本日の出勤キャスト紹介投稿を作成してください。"
    )

    generated_text = _call_gemini_for_draft(prompt)
    if not generated_text:
        logger.warning("Draft generation failed for store %s", store.name)
        return None

    draft = DraftPost.objects.create(
        store=store,
        content=generated_text,
        ai_generated_content=generated_text,
        platforms=platforms,
        status='generated',
        target_date=target_date,
    )

    # 画像自動添付
    from booking.services.sns_image_selector import attach_image_to_draft, select_image_for_draft

    image_field = select_image_for_draft(store, target_date)
    if image_field:
        attach_image_to_draft(draft, image_field)

    logger.info("Draft generated for store %s: draft_id=%d, has_image=%s",
                store.name, draft.pk, bool(draft.image))
    return draft
