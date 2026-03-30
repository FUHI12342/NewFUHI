"""AI 下書き生成サービス — Gemini API で SNS 投稿文を生成"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

DRAFT_SYSTEM_PROMPT = """あなたは占いサロンのSNS投稿作成アシスタントです。
以下のルールを厳守してください:

1. 店舗名・キャスト名は提供された情報から正確に記載すること
2. 絵文字を適度に使用して親しみやすい文章にすること
3. CTA（来店促進の一言）を含めること
4. X (Twitter) の場合は加重文字数280文字以内に収めること
5. Instagram の場合はハッシュタグを5-10個含めること
6. 事実と異なる情報（架空のキャスト名、存在しないサービス等）は絶対に書かないこと
7. 日本語で投稿すること

出力は投稿テキストのみ（説明やメタ情報は不要）。"""


def _call_gemini_for_draft(prompt, max_tokens=512, temperature=0.8):
    """Gemini API 呼び出し（下書き生成用）"""
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        logger.error('GEMINI_API_KEY is not configured')
        return None

    url = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'gemini-2.5-flash:generateContent?key={api_key}'
    )

    payload = json.dumps({
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'maxOutputTokens': max_tokens,
            'temperature': temperature,
        },
    }).encode('utf-8')

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

    platform_str = ', '.join(platforms)
    prompt = (
        f"{DRAFT_SYSTEM_PROMPT}\n\n"
        f"---\n投稿先: {platform_str}\n"
        f"対象日: {target_date.strftime('%Y年%m月%d日')}\n\n"
        f"---\n参照情報:\n{context}\n\n"
        f"---\n上記の情報をもとに、本日の出勤キャスト紹介投稿を作成してください。"
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

    logger.info("Draft generated for store %s: draft_id=%d", store.name, draft.pk)
    return draft
