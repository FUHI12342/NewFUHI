# booking/context_processors.py
from django.conf import settings
from django.utils.translation import get_language

from .models import Store, Company, Notice, Media, SiteSettings


def global_context(request):
    """全テンプレートで共通して使う値を提供する"""
    return {
        'stores': Store.objects.all(),
        'company': Company.objects.first(),
        'notices': Notice.objects.order_by('-updated_at')[:5],
        'medias': Media.objects.order_by('-created_at')[:5],
        'current_language': get_language() or settings.LANGUAGE_CODE,
        'available_languages': settings.LANGUAGES,
        'site_settings': SiteSettings.load(),
    }


def admin_user_flags(request):
    """管理画面用のユーザー権限フラグを注入"""
    if not request.path.startswith('/admin/'):
        return {}
    is_dev = False
    if hasattr(request, 'user') and request.user.is_authenticated:
        if request.user.is_superuser:
            is_dev = True
        else:
            try:
                is_dev = request.user.staff.is_developer
            except Exception:
                pass
    return {'is_developer_or_superuser': is_dev}


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
