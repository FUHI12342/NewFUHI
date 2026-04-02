"""Site setup wizard — 3-step guide for store customization."""
from django.shortcuts import get_object_or_404, render
from django.views import View

from booking.models import Store, StoreTheme, PageLayout, CustomPage


class SiteSetupWizardView(View):
    """3ステップのサイトセットアップウィザード。"""

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)

        # Check completion status for each step
        has_theme = StoreTheme.objects.filter(store=store).exists()
        has_layout = PageLayout.objects.filter(store=store).exists()
        has_pages = CustomPage.objects.filter(store=store).exists()

        steps = [
            {
                'number': 1,
                'title': 'テーマを選ぶ',
                'description': '7種類のプリセットからサロンの雰囲気に合ったテーマを選択。カラー・フォントが一括で設定されます。',
                'icon': '🎨',
                'completed': has_theme,
                'url_name': 'admin_theme_customizer',
                'url_args': [store.pk],
            },
            {
                'number': 2,
                'title': 'レイアウトを設定',
                'description': 'トップページのセクション（ヒーローバナー・スタッフ一覧・ランキング等）の表示順と表示/非表示を設定。',
                'icon': '📐',
                'completed': has_layout,
                'url_name': 'admin_page_layout_editor',
                'url_args': [store.pk],
            },
            {
                'number': 3,
                'title': 'ページを作成',
                'description': 'テンプレートを選んでオリジナルページを作成。GrapesJSエディタでドラッグ&ドロップ編集できます。',
                'icon': '📄',
                'completed': has_pages,
                'url_name': 'admin_page_builder_list',
                'url_args': [store.pk],
            },
        ]

        completed_count = sum(1 for s in steps if s['completed'])

        return render(request, 'admin/booking/site_wizard/index.html', {
            'store': store,
            'steps': steps,
            'completed_count': completed_count,
            'total_steps': len(steps),
            'title': f'{store.name} - サイトセットアップ',
        })
