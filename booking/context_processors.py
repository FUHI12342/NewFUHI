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


def admin_theme(request):
    """管理画面用のテーマ設定をコンテキストに注入"""
    if not request.path.startswith('/admin/'):
        return {}
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}
    try:
        from .models import Staff
        staff = Staff.objects.select_related('store__admin_theme').get(user=request.user)
        theme = staff.store.admin_theme
        return {'admin_theme': theme}
    except Exception:
        return {}
