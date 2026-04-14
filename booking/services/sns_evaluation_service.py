"""LLM Judge 品質評価サービス — ルールベース + Gemini による品質スコアリング"""
import json
import logging
import re

from booking.services.post_generator import weighted_length, MAX_WEIGHTED_LENGTH

logger = logging.getLogger(__name__)

# 禁止ワード
BANNED_WORDS = ['死', '殺', '自殺', '暴力', 'エロ', 'セックス', 'ギャンブル']

# プラットフォーム別文字数制限
PLATFORM_CHAR_LIMITS = {
    'x': {'max_weighted': 230, 'label': 'X'},
    'instagram': {'max_chars': 2200, 'label': 'Instagram'},
    'gbp': {'max_chars': 1500, 'label': 'Google Business Profile'},
}


def _rule_based_check(draft_post):
    """同期ルールベースチェック

    Returns:
        (issues: list[str], deductions: float)
    """
    issues = []
    deductions = 0.0
    content = draft_post.content
    platforms = draft_post.platforms or []

    # 1. プラットフォーム別文字数チェック
    for platform in platforms:
        limit = PLATFORM_CHAR_LIMITS.get(platform)
        if not limit:
            continue
        if 'max_weighted' in limit:
            wlen = weighted_length(content)
            if wlen > limit['max_weighted']:
                issues.append(
                    f"{limit['label']}向けの加重文字数が{wlen}/{limit['max_weighted']}を超過"
                )
                deductions += 0.2
        elif 'max_chars' in limit:
            clen = len(content)
            if clen > limit['max_chars']:
                issues.append(
                    f"{limit['label']}向けの文字数が{clen}/{limit['max_chars']}を超過"
                )
                deductions += 0.15

    # 2. 空コンテンツ
    if not content.strip():
        issues.append("投稿内容が空です")
        deductions += 1.0

    # 3. 禁止ワード
    for word in BANNED_WORDS:
        if word in content:
            issues.append(f"禁止ワード '{word}' が含まれています")
            deductions += 0.3

    # 4. 店舗名チェック
    if draft_post.store.name not in content:
        issues.append("店舗名が含まれていません")
        deductions += 0.1

    # 5. Instagram ハッシュタグチェック
    if 'instagram' in platforms:
        hashtag_count = content.count('#')
        if hashtag_count < 3:
            issues.append(f"Instagramのハッシュタグが少なすぎます ({hashtag_count}個、推奨: 5-10個)")
            deductions += 0.05

    return issues, min(deductions, 1.0)


def _llm_judge_check(draft_post, context=''):
    """Gemini Flash による品質評価

    Returns:
        (score: float, feedback: str) or (None, '')
    """
    from booking.services.sns_draft_service import _call_gemini_for_draft

    eval_prompt = f"""以下のSNS投稿を4つの基準で評価してください。

【投稿内容】
{draft_post.content}

【店舗情報】
店舗名: {draft_post.store.name}

【評価基準と配点】
1. 事実正確性 (0.0-1.0, 配点30%): 架空の情報がないか
2. 文章品質 (0.0-1.0, 配点30%): 読みやすさ、絵文字の使い方
3. 集客効果 (0.0-1.0, 配点20%): CTAの有無、魅力的な表現
4. プラットフォーム適合 (0.0-1.0, 配点20%): 文字数、ハッシュタグ等

JSON形式のみで回答してください（説明不要、JSONのみ出力）。feedbackは1-2文で簡潔に:
{{"accuracy": 0.9, "quality": 0.8, "marketing": 0.7, "platform_fit": 0.8, "feedback": "簡潔なフィードバック"}}"""

    result_text = _call_gemini_for_draft(
        eval_prompt, max_tokens=1024, temperature=0.2, disable_thinking=True,
    )
    if not result_text:
        return None, ''

    try:
        # マークダウンコードブロックを除去してJSON部分を抽出
        cleaned = re.sub(r'```(?:json)?\s*', '', result_text).strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if not json_match:
            return None, result_text
        data = json.loads(json_match.group())

        accuracy = float(data.get('accuracy', 0.5))
        quality = float(data.get('quality', 0.5))
        marketing = float(data.get('marketing', 0.5))
        platform_fit = float(data.get('platform_fit', 0.5))
        feedback = data.get('feedback', '')

        # 加重平均
        score = (accuracy * 0.3) + (quality * 0.3) + (marketing * 0.2) + (platform_fit * 0.2)
        return round(score, 2), feedback
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM Judge parse error: %s", e)
        return None, result_text


def evaluate_draft_quality(draft_post):
    """下書きの品質を総合評価してスコアとフィードバックを DraftPost に保存

    Returns:
        (score: float, feedback: str)
    """
    # 1. ルールベースチェック
    rule_issues, rule_deduction = _rule_based_check(draft_post)

    # 2. LLM Judge
    llm_score, llm_feedback = _llm_judge_check(draft_post)

    # 3. スコア統合
    if llm_score is not None:
        # LLM スコアからルール減点を引く
        final_score = max(0.0, llm_score - rule_deduction)
    else:
        # LLM 利用不可の場合はルールベースのみ
        final_score = max(0.0, 0.7 - rule_deduction)

    # フィードバック統合
    feedback_parts = []
    if rule_issues:
        feedback_parts.append("ルールチェック: " + '; '.join(rule_issues))
    if llm_feedback:
        feedback_parts.append("AI評価: " + llm_feedback)
    final_feedback = '\n'.join(feedback_parts)

    # 保存
    draft_post.quality_score = round(final_score, 2)
    draft_post.quality_feedback = final_feedback
    draft_post.save(update_fields=['quality_score', 'quality_feedback', 'updated_at'])

    return final_score, final_feedback
