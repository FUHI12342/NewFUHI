"""GrapesJS page builder views."""
import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views import View

from booking.models import Store, CustomPage, PageTemplate, StoreTheme, SavedBlock


class PageBuilderListView(View):
    """カスタムページ一覧。"""

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        pages = CustomPage.objects.filter(store=store).order_by('-updated_at')
        return render(request, 'admin/booking/page_builder/list.html', {
            'store': store,
            'pages': pages,
            'title': f'{store.name} - カスタムページ',
        })


class PageBuilderCreateView(View):
    """新規カスタムページ作成。"""

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        templates = PageTemplate.objects.all().order_by('category', 'name')
        return render(request, 'admin/booking/page_builder/create.html', {
            'store': store,
            'templates': templates,
            'title': f'{store.name} - 新規ページ作成',
        })

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        title = request.POST.get('title', '').strip()
        slug = request.POST.get('slug', '').strip()
        page_type = request.POST.get('page_type', 'custom')
        layout = request.POST.get('layout', 'standard')
        template_id = request.POST.get('template_id')

        if not title or not slug:
            return JsonResponse({'error': 'タイトルとスラッグは必須です'}, status=400)

        grapesjs_data = {}
        html_content = ''
        css_content = ''
        if template_id:
            try:
                tpl = PageTemplate.objects.get(pk=template_id)
                grapesjs_data = tpl.grapesjs_data
                html_content = tpl.html_content
                css_content = tpl.css_content
            except PageTemplate.DoesNotExist:
                pass

        page = CustomPage.objects.create(
            store=store, title=title, slug=slug,
            page_type=page_type,
            layout=layout,
            grapesjs_data=grapesjs_data,
            html_content=html_content,
            css_content=css_content,
        )
        from django.urls import reverse
        return redirect(reverse('admin_page_builder_edit', args=[store.pk, page.pk]))


class PageBuilderEditView(View):
    """GrapesJS エディタ画面。"""

    def get(self, request, store_id, page_id):
        store = get_object_or_404(Store, pk=store_id)
        page = get_object_or_404(CustomPage, pk=page_id, store=store)
        store_theme = StoreTheme.objects.filter(store=store).first()
        theme_css_vars = ''
        theme_fonts = []
        if store_theme:
            theme_css_vars = (
                f':root {{'
                f' --color-primary: {store_theme.primary_color};'
                f' --color-secondary: {store_theme.secondary_color};'
                f' --color-accent: {store_theme.accent_color};'
                f' --color-text: {store_theme.text_color};'
                f' --color-header-bg: {store_theme.header_bg_color};'
                f' --color-footer-bg: {store_theme.footer_bg_color};'
                f' --font-heading: "{store_theme.heading_font}", sans-serif;'
                f' --font-body: "{store_theme.body_font}", sans-serif;'
                f'}}'
            )
            for font in [store_theme.heading_font, store_theme.body_font]:
                if font and font not in theme_fonts:
                    theme_fonts.append(font)
        return render(request, 'admin/booking/page_builder/editor.html', {
            'store': store,
            'page': page,
            'store_theme': store_theme,
            'grapesjs_data_json': json.dumps(page.grapesjs_data, ensure_ascii=False),
            'theme_css_vars': theme_css_vars,
            'theme_fonts_json': json.dumps(theme_fonts, ensure_ascii=False),
            'title': f'{page.title} - ページビルダー',
        })

    def post(self, request, store_id, page_id):
        store = get_object_or_404(Store, pk=store_id)
        page = get_object_or_404(CustomPage, pk=page_id, store=store)

        # SEO-only update
        if request.POST.get('seo_update'):
            page.meta_title = request.POST.get('meta_title', '')[:70]
            page.meta_description = request.POST.get('meta_description', '')[:160]
            page.og_image_url = request.POST.get('og_image_url', '')[:500]
            page.save(update_fields=['meta_title', 'meta_description', 'og_image_url'])
            return JsonResponse({'status': 'ok', 'message': 'SEO設定を保存しました'})

        # GrapesJS data update
        try:
            grapesjs_data = json.loads(request.POST.get('grapesjs_data', '{}'))
        except (json.JSONDecodeError, TypeError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        html_content = request.POST.get('html_content', '')
        css_content = request.POST.get('css_content', '')

        page.grapesjs_data = grapesjs_data
        page.html_content = html_content
        page.css_content = css_content
        page.save()

        return JsonResponse({'status': 'ok', 'message': '保存しました'})


class PageBuilderPublishView(View):
    """公開/非公開切り替え。"""

    def post(self, request, store_id, page_id):
        store = get_object_or_404(Store, pk=store_id)
        page = get_object_or_404(CustomPage, pk=page_id, store=store)

        action = request.POST.get('action', 'publish')
        if action == 'publish':
            page.is_published = True
            page.published_at = timezone.now()
        else:
            page.is_published = False

        page.save()
        return JsonResponse({
            'status': 'ok',
            'is_published': page.is_published,
        })


class PageBuilderDuplicateView(View):
    """既存ページを複製。"""

    def post(self, request, store_id, page_id):
        store = get_object_or_404(Store, pk=store_id)
        page = get_object_or_404(CustomPage, pk=page_id, store=store)

        # Generate unique slug
        base_slug = f'{page.slug}-copy'
        slug = base_slug
        counter = 1
        while CustomPage.objects.filter(store=store, slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1

        new_page = CustomPage.objects.create(
            store=store,
            title=f'{page.title} (コピー)',
            slug=slug,
            page_type=page.page_type,
            layout=page.layout,
            grapesjs_data=page.grapesjs_data,
            html_content=page.html_content,
            css_content=page.css_content,
        )
        from django.urls import reverse
        return redirect(reverse('admin_page_builder_edit', args=[store.pk, new_page.pk]))


class PageBuilderUploadView(View):
    """画像アップロード API（GrapesJS Asset Manager 用）。"""

    def post(self, request, store_id):
        import os
        from django.conf import settings
        from django.core.files.storage import default_storage

        store = get_object_or_404(Store, pk=store_id)
        uploaded = request.FILES.getlist('files[]')
        if not uploaded:
            uploaded = request.FILES.getlist('file')

        results = []
        for f in uploaded:
            # Validate file type
            allowed_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'}
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in allowed_ext:
                continue

            path = f'page_builder/{store.pk}/{f.name}'
            saved_path = default_storage.save(path, f)
            url = default_storage.url(saved_path)
            results.append(url)

        return JsonResponse({'data': results})


class SavedBlockListView(View):
    """保存済みブロック一覧API。"""

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        blocks = SavedBlock.objects.filter(store=store)
        data = [
            {
                'id': b.pk,
                'label': b.label,
                'category': b.category,
                'html_content': b.html_content,
                'css_content': b.css_content,
            }
            for b in blocks
        ]
        return JsonResponse({'blocks': data})


class SavedBlockCreateView(View):
    """ブロック保存API。"""

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        label = request.POST.get('label', '').strip()
        if not label:
            return JsonResponse({'error': 'ブロック名は必須です'}, status=400)

        html_content = request.POST.get('html_content', '')
        if not html_content.strip():
            return JsonResponse({'error': 'HTMLコンテンツは必須です'}, status=400)

        block = SavedBlock.objects.create(
            store=store,
            label=label,
            category=request.POST.get('category', '保存済み'),
            html_content=html_content,
            css_content=request.POST.get('css_content', ''),
        )
        return JsonResponse({
            'status': 'ok',
            'block': {
                'id': block.pk,
                'label': block.label,
                'category': block.category,
                'html_content': block.html_content,
                'css_content': block.css_content,
            },
        })


class SavedBlockDeleteView(View):
    """ブロック削除API。"""

    def post(self, request, store_id, block_id):
        store = get_object_or_404(Store, pk=store_id)
        block = get_object_or_404(SavedBlock, pk=block_id, store=store)
        block.delete()
        return JsonResponse({'status': 'ok'})


class CustomPageView(View):
    """公開カスタムページ表示（顧客向け）。"""

    def get(self, request, store_id, slug):
        page = get_object_or_404(
            CustomPage,
            store_id=store_id, slug=slug, is_published=True,
        )
        template = (
            'booking/custom_page_full_width.html'
            if page.layout == 'full_width'
            else 'booking/custom_page.html'
        )
        return render(request, template, {
            'page': page,
            'store': page.store,
        })
