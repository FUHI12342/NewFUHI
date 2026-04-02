"""Theme preview, customizer, and API views."""
import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from booking.models import Store, StoreTheme
from booking.services.theme_presets import THEME_PRESETS


class ThemePreviewView(View):
    """iframe 用テーマプレビュー。管理画面からのみアクセス想定。

    ?preview=1 のとき、URL パラメータで渡されたテーマ値を一時適用。
    """

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        try:
            theme = store.store_theme
        except StoreTheme.DoesNotExist:
            theme = None

        # プレビューモード: パラメータからテーマ値を一時上書き
        is_preview = request.GET.get('preview') == '1'
        if is_preview and theme:
            # 保存せずにオーバーライド（テンプレートに渡すだけ）
            color_fields = [
                'primary_color', 'secondary_color', 'accent_color',
                'text_color', 'header_bg_color', 'footer_bg_color',
            ]
            for field in color_fields:
                val = request.GET.get(field)
                if val:
                    setattr(theme, field, val)
            for font_field in ('heading_font', 'body_font'):
                val = request.GET.get(font_field)
                if val:
                    setattr(theme, font_field, val)

        # セクション情報を追加（booking_top.html が必要とする）
        from booking.models import SiteSettings, HeroBanner, HomepageCustomBlock
        from booking.services.page_layout_service import get_page_sections
        site_settings = SiteSettings.load()

        context = {
            'store_theme': theme,
            'is_preview': True,
            'site_settings': site_settings,
            'page_sections': get_page_sections(store, 'home'),
        }
        if site_settings.show_hero_banner:
            context['hero_banners'] = HeroBanner.objects.filter(
                is_active=True,
            ).order_by('sort_order')

        active_blocks = HomepageCustomBlock.objects.filter(is_active=True)
        context['custom_blocks_above'] = active_blocks.filter(position='above_cards')
        context['custom_blocks_below'] = active_blocks.filter(position='below_cards')

        return render(request, 'booking/booking_top.html', context)


class ThemePresetsAPIView(View):
    """プリセット一覧を JSON で返す API。管理画面のJS から使用。"""

    def get(self, request):
        return JsonResponse(THEME_PRESETS)


class ThemeCustomizerView(View):
    """WordPress Customizer 風のテーマカスタマイザー。

    左ペイン: 設定パネル（カラーピッカー、フォント選択、プリセット）
    右ペイン: iframe でリアルタイムプレビュー
    """

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        try:
            theme = store.store_theme
        except StoreTheme.DoesNotExist:
            theme = StoreTheme(store=store)

        return render(request, 'admin/booking/theme_customizer/editor.html', {
            'store': store,
            'theme': theme,
            'presets_json': json.dumps(THEME_PRESETS, ensure_ascii=False),
            'title': f'{store.name} - テーマカスタマイザー',
        })

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        theme, created = StoreTheme.objects.get_or_create(store=store)

        color_fields = [
            'primary_color', 'secondary_color', 'accent_color',
            'text_color', 'header_bg_color', 'footer_bg_color',
        ]
        for field in color_fields:
            val = request.POST.get(field)
            if val:
                setattr(theme, field, val)

        for font_field in ('heading_font', 'body_font'):
            val = request.POST.get(font_field)
            if val:
                setattr(theme, font_field, val)

        preset = request.POST.get('preset')
        if preset:
            theme.preset = preset

        custom_css = request.POST.get('custom_css')
        if custom_css is not None:
            theme.custom_css = custom_css

        theme.save()
        return JsonResponse({'status': 'ok', 'message': 'テーマを保存しました'})
