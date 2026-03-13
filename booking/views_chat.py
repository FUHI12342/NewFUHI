# booking/views_chat.py
"""AI Chat API views."""
import json
import logging
import time

from django.core.cache import cache
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AdminChatAPIView(View):
    """管理画面 AI チャット API (is_staff 必須、レート制限: 20回/5分)"""

    RATE_LIMIT = 20
    RATE_WINDOW = 300  # 5 minutes

    def post(self, request):
        if not request.user.is_authenticated or not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        # Per-user rate limiting via cache
        cache_key = f'admin_chat_rate:{request.user.pk}'
        now = time.time()
        timestamps = cache.get(cache_key, [])
        timestamps = [t for t in timestamps if now - t < self.RATE_WINDOW]
        if len(timestamps) >= self.RATE_LIMIT:
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

        from .services.ai_chat import AdminChatService
        service = AdminChatService()
        reply = service.get_response(message, history)

        timestamps.append(now)
        cache.set(cache_key, timestamps, self.RATE_WINDOW)

        return JsonResponse({'reply': reply})
