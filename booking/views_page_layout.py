"""Page layout editor views for admin."""
import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.decorators.http import require_POST

from booking.models import Store, PageLayout
from booking.models.page_layout import DEFAULT_HOME_SECTIONS, PAGE_TYPE_CHOICES


class PageLayoutEditorView(View):
    """セクション並び替え・設定エディタ。"""

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        page_type = request.GET.get('page_type', 'home')

        try:
            layout = PageLayout.objects.get(store=store, page_type=page_type)
            sections = layout.sections_json
        except PageLayout.DoesNotExist:
            sections = DEFAULT_HOME_SECTIONS if page_type == 'home' else []

        return render(request, 'admin/booking/page_layout/editor.html', {
            'store': store,
            'page_type': page_type,
            'page_type_choices': PAGE_TYPE_CHOICES,
            'sections_json': json.dumps(sections, ensure_ascii=False),
            'title': f'{store.name} - ページレイアウト設定',
        })

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        page_type = request.POST.get('page_type', 'home')

        try:
            sections = json.loads(request.POST.get('sections_json', '[]'))
        except (json.JSONDecodeError, TypeError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Validate section structure
        validated = []
        for item in sections:
            if not isinstance(item, dict) or 'type' not in item:
                continue
            validated.append({
                'type': item['type'],
                'enabled': bool(item.get('enabled', True)),
                'settings': item.get('settings', {}),
            })

        layout, _ = PageLayout.objects.update_or_create(
            store=store, page_type=page_type,
            defaults={'sections_json': validated},
        )

        return JsonResponse({
            'status': 'ok',
            'message': 'レイアウトを保存しました',
            'sections': layout.sections_json,
        })
