# booking/views_chat.py
"""AI Chat API views."""
import json
import logging

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AdminChatAPIView(View):
    """管理画面 AI チャット API (is_staff 必須)"""

    def post(self, request):
        if not request.user.is_authenticated or not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        message = data.get('message', '').strip()
        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)

        history = data.get('history', [])

        from .services.ai_chat import AdminChatService
        service = AdminChatService()
        reply = service.get_response(message, history)

        return JsonResponse({'reply': reply})


@method_decorator(csrf_exempt, name='dispatch')
class GuideChatAPIView(View):
    """予約ガイド AI チャット API (認証不要、レートリミット付き)"""

    def post(self, request):
        # Simple session-based rate limiting: 10 requests per 5 minutes
        import time
        session_key = 'guide_chat_timestamps'
        now = time.time()
        timestamps = request.session.get(session_key, [])
        # Remove timestamps older than 5 minutes
        timestamps = [t for t in timestamps if now - t < 300]
        if len(timestamps) >= 10:
            return JsonResponse(
                {'error': 'リクエストが多すぎます。しばらく経ってからお試しください。'},
                status=429,
            )

        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        message = data.get('message', '').strip()
        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)

        history = data.get('history', [])

        from .services.ai_chat import GuideChatService
        service = GuideChatService()
        reply = service.get_response(message, history)

        # Record timestamp
        timestamps.append(now)
        request.session[session_key] = timestamps

        return JsonResponse({'reply': reply})
