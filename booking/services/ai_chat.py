# booking/services/ai_chat.py
"""AI Chat services using Google Gemini API with RAG knowledge bases."""
import json
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

# Cache for knowledge file contents
_knowledge_cache = {}

GEMINI_API_KEY = 'AIzaSyA9v0lQ9bZHW-vsYFt-pBOqmV0w6WTYQlw'


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


def _call_gemini(system_prompt, knowledge, user_message, conversation_history=None):
    """Call Google Gemini API."""
    import urllib.request

    api_key = getattr(settings, 'GEMINI_API_KEY', '') or GEMINI_API_KEY
    if not api_key:
        return 'AI チャットは現在利用できません。API キーが設定されていません。'

    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}'

    # Build conversation contents
    contents = []

    # Add conversation history
    if conversation_history:
        for msg in conversation_history[-10:]:
            role = 'user' if msg.get('role') == 'user' else 'model'
            contents.append({
                'role': role,
                'parts': [{'text': msg.get('content', '')}],
            })

    # Add current user message with knowledge context
    full_user_message = f"{system_prompt}\n\n---\nナレッジベース:\n{knowledge}\n\n---\nユーザーの質問: {user_message}"
    contents.append({
        'role': 'user',
        'parts': [{'text': full_user_message}],
    })

    payload = json.dumps({
        'contents': contents,
        'generationConfig': {
            'maxOutputTokens': 1024,
            'temperature': 0.7,
        },
    }).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        candidates = data.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            if parts:
                return parts[0].get('text', 'レスポンスが空でした。')
        return 'レスポンスを取得できませんでした。'
    except Exception as e:
        logger.error('Gemini API error: %s', e)
        return 'エラーが発生しました。しばらく経ってからお試しください。'


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
        knowledge = _load_knowledge(self.KNOWLEDGE_FILE)
        return _call_gemini(self.SYSTEM_PROMPT, knowledge, user_message, conversation_history)


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
        knowledge = _load_knowledge(self.KNOWLEDGE_FILE)
        return _call_gemini(self.SYSTEM_PROMPT, knowledge, user_message, conversation_history)
