# booking/services/ai_chat.py
"""AI Chat services using Claude API with RAG knowledge bases."""
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

# Cache for knowledge file contents
_knowledge_cache = {}


def _load_knowledge(file_path):
    """Load and cache a knowledge text file."""
    if file_path in _knowledge_cache:
        return _knowledge_cache[file_path]

    full_path = os.path.join(settings.BASE_DIR, file_path)
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        _knowledge_cache[file_path] = content
        return content
    except FileNotFoundError:
        logger.warning('Knowledge file not found: %s', full_path)
        return ''


def _get_client():
    """Get Anthropic client, or None if not configured."""
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '') or os.getenv('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.warning('anthropic package not installed')
        return None


class AdminChatService:
    """管理画面ガイド用RAGチャット"""
    KNOWLEDGE_FILE = 'static/knowledge/admin_guide.txt'
    SYSTEM_PROMPT = (
        'あなたは占いサロンチャンスの管理画面アシスタントです。'
        '以下のナレッジベースを参照して、管理画面の使い方に関する質問に日本語で回答してください。'
        'ナレッジにない情報は「その情報はガイドに記載されていません」と正直に答えてください。'
        '回答は簡潔に、箇条書きを活用してください。'
    )

    def get_response(self, user_message, conversation_history=None):
        client = _get_client()
        if not client:
            return 'AI チャットは現在利用できません。ANTHROPIC_API_KEY が設定されていません。'

        knowledge = _load_knowledge(self.KNOWLEDGE_FILE)

        messages = []
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages
                messages.append({
                    'role': msg.get('role', 'user'),
                    'content': msg.get('content', ''),
                })

        messages.append({'role': 'user', 'content': user_message})

        try:
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=1024,
                system=f"{self.SYSTEM_PROMPT}\n\n---\nナレッジベース:\n{knowledge}",
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error('AI chat error: %s', e)
            return 'エラーが発生しました。しばらく経ってからお試しください。'


class GuideChatService:
    """予約ガイド用RAGチャット"""
    KNOWLEDGE_FILE = 'static/knowledge/booking_guide.txt'
    SYSTEM_PROMPT = (
        'あなたは占いサロンチャンスの予約ガイドアシスタントです。'
        '以下のナレッジベースを参照して、予約方法やサービスに関する質問に日本語で回答してください。'
        'ナレッジにない情報は「その情報はガイドに記載されていません」と正直に答えてください。'
        '回答は簡潔で親切に、お客様目線でお答えください。'
    )

    def get_response(self, user_message, conversation_history=None):
        client = _get_client()
        if not client:
            return 'AI チャットは現在利用できません。'

        knowledge = _load_knowledge(self.KNOWLEDGE_FILE)

        messages = []
        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append({
                    'role': msg.get('role', 'user'),
                    'content': msg.get('content', ''),
                })

        messages.append({'role': 'user', 'content': user_message})

        try:
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=1024,
                system=f"{self.SYSTEM_PROMPT}\n\n---\nナレッジベース:\n{knowledge}",
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error('Guide chat error: %s', e)
            return 'エラーが発生しました。しばらく経ってからお試しください。'
