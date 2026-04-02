# booking/context_processors.py
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import get_language

from .models import Store, Staff, Company, Notice, Media, ExternalLink, SiteSettings, StoreTheme


def _get_localized_staff_label(site_settings):
    """現在の言語に対応する staff_label を返す。未設定なら日本語デフォルト。"""
    lang = get_language() or settings.LANGUAGE_CODE
    if lang == 'ja' or not site_settings.staff_label_i18n:
        return site_settings.staff_label
    i18n = site_settings.staff_label_i18n
    # 完全一致 → ベース言語フォールバック → デフォルト
    return i18n.get(lang) or i18n.get(lang.split('-')[0], site_settings.staff_label)


def global_context(request):
    """全テンプレートで共通して使う値を提供する"""
    lang = get_language() or settings.LANGUAGE_CODE
    cache_key = f'global_context:{lang}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    site_settings = SiteSettings.load()
    # staff_label を現在の言語に合わせて上書きしたコピーを作成
    localized_staff_label = _get_localized_staff_label(site_settings)
    # サイドバー並び順
    default_order = ['notice', 'sns', 'media', 'external_links', 'company']
    sidebar_order = site_settings.sidebar_order if site_settings.sidebar_order else default_order
    # 未登録のセクションがあれば末尾に追加
    for key in default_order:
        if key not in sidebar_order:
            sidebar_order.append(key)

    context = {
        'stores': list(Store.objects.all()),
        'company': Company.objects.first(),
        'notices': list(Notice.objects.filter(is_published=True).order_by('-updated_at')[:5]),
        'medias': list(Media.objects.order_by('-created_at')[:5]),
        'external_links': list(ExternalLink.objects.filter(is_active=True)),
        'current_language': lang,
        'available_languages': settings.LANGUAGES,
        'site_settings': site_settings,
        'staff_label': localized_staff_label,
        'price_label': site_settings.price_label if site_settings else '鑑定料',
        'sidebar_order': sidebar_order,
    }
    cache.set(cache_key, context, 60)
    return context


def _is_admin_path(path):
    """言語プレフィックス付きの管理画面パスを判定"""
    import re
    return bool(re.match(r'^(/(?:en|zh-hant|zh-hans|ko|es|pt))?/admin/', path))


def admin_user_flags(request):
    """管理画面用のユーザー権限フラグを注入"""
    if not _is_admin_path(request.path):
        return {}
    is_dev = False
    if hasattr(request, 'user') and request.user.is_authenticated:
        if request.user.is_superuser:
            is_dev = True
        else:
            try:
                is_dev = request.user.staff.is_developer
            except (Staff.DoesNotExist, AttributeError):
                pass
    return {'is_developer_or_superuser': is_dev}


def _resolve_current_store(request):
    """現在のリクエストに対応する Store を判定する。

    優先順位:
    1. URL パラメータ store_id
    2. ログインユーザーの所属 Store
    3. 最初の Store（シングルテナント互換）
    """
    # URL パラメータ
    store_id = request.GET.get('store_id') or request.resolver_match and request.resolver_match.kwargs.get('store_id')
    if store_id:
        try:
            return Store.objects.get(pk=store_id)
        except (Store.DoesNotExist, ValueError):
            pass
    # ログインユーザーの店舗
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            return request.user.staff.store
        except (Staff.DoesNotExist, AttributeError):
            pass
    # フォールバック: 最初の店舗
    return Store.objects.first()


def store_theme(request):
    """顧客向けページ用のテーマ設定をコンテキストに注入。"""
    if _is_admin_path(request.path):
        return {}
    store = _resolve_current_store(request)
    if store:
        try:
            return {'store_theme': store.store_theme}
        except StoreTheme.DoesNotExist:
            pass
    return {'store_theme': None}


def admin_theme(request):
    """管理画面用のテーマ設定をコンテキストに注入"""
    if not _is_admin_path(request.path):
        return {}
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}
    try:
        staff = Staff.objects.select_related('store__admin_theme').get(user=request.user)
        theme = staff.store.admin_theme
        return {'admin_theme': theme}
    except (Staff.DoesNotExist, AttributeError):
        return {}
