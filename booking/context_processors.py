# booking/context_processors.py
from django.conf import settings
from django.utils.translation import get_language

from .models import Store, Company, Notice, Media


def global_context(request):
    """全テンプレートで共通して使う値を提供する"""
    return {
        'stores': Store.objects.all(),
        'company': Company.objects.first(),
        'notices': Notice.objects.order_by('-updated_at')[:5],
        'medias': Media.objects.order_by('-created_at')[:5],
        'current_language': get_language() or settings.LANGUAGE_CODE,
        'available_languages': settings.LANGUAGES,
    }
