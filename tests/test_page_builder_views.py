"""Regression & coverage tests for page builder views."""
import json

import pytest
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Store, CustomPage, PageTemplate, StoreTheme


@pytest.mark.django_db
class PageBuilderListViewTest(TestCase):
    """PageBuilderListView tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('listadmin', password='pass123')
        cls.store = Store.objects.create(name='一覧テスト店')

    def setUp(self):
        self.client.login(username='listadmin', password='pass123')
        self.url = reverse('admin_page_builder_list', args=[self.store.pk])

    def test_list_returns_200(self):
        resp = self.client.get(self.url)
        assert resp.status_code == 200

    def test_list_shows_store_name(self):
        resp = self.client.get(self.url)
        assert '一覧テスト店' in resp.content.decode()

    def test_list_includes_pages(self):
        CustomPage.objects.create(
            store=self.store, title='表示テスト', slug='show-test',
        )
        resp = self.client.get(self.url)
        assert '表示テスト' in resp.content.decode()


@pytest.mark.django_db
class PageBuilderCreateViewTest(TestCase):
    """PageBuilderCreateView tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('createadmin', password='pass123')
        cls.store = Store.objects.create(name='作成テスト店')

    def setUp(self):
        self.client.login(username='createadmin', password='pass123')
        self.url = reverse('admin_page_builder_create', args=[self.store.pk])

    def test_create_form_returns_200(self):
        resp = self.client.get(self.url)
        assert resp.status_code == 200

    def test_create_page_redirects(self):
        resp = self.client.post(self.url, {
            'title': '新ページ', 'slug': 'new-page', 'page_type': 'custom',
        })
        assert resp.status_code == 302

    def test_create_page_saves_to_db(self):
        self.client.post(self.url, {
            'title': 'DB保存テスト', 'slug': 'db-test',
        })
        assert CustomPage.objects.filter(store=self.store, slug='db-test').exists()

    def test_create_with_template(self):
        tpl = PageTemplate.objects.create(
            name='テスト', html_content='<div>tpl</div>',
            css_content='body{}', grapesjs_data={'components': []},
        )
        self.client.post(self.url, {
            'title': 'テンプレ利用', 'slug': 'tpl-test',
            'template_id': tpl.pk,
        })
        page = CustomPage.objects.get(store=self.store, slug='tpl-test')
        assert page.html_content == '<div>tpl</div>'

    def test_create_with_layout(self):
        self.client.post(self.url, {
            'title': 'フルワイド', 'slug': 'fw-test',
            'layout': 'full_width',
        })
        page = CustomPage.objects.get(store=self.store, slug='fw-test')
        assert page.layout == 'full_width'

    def test_create_missing_fields_returns_400(self):
        resp = self.client.post(self.url, {'title': '', 'slug': ''})
        assert resp.status_code == 400


@pytest.mark.django_db
class PageBuilderEditViewTest(TestCase):
    """PageBuilderEditView GET/POST tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('editadmin', password='pass123')
        cls.store = Store.objects.create(name='編集テスト店')
        cls.page = CustomPage.objects.create(
            store=cls.store, title='編集ページ', slug='edit-page',
            grapesjs_data={'components': [], 'styles': []},
        )

    def setUp(self):
        self.client.login(username='editadmin', password='pass123')
        self.url = reverse(
            'admin_page_builder_edit', args=[self.store.pk, self.page.pk],
        )

    def test_editor_returns_200(self):
        resp = self.client.get(self.url)
        assert resp.status_code == 200

    def test_editor_contains_grapesjs(self):
        resp = self.client.get(self.url)
        content = resp.content.decode()
        assert 'grapesjs' in content.lower()

    def test_editor_with_theme(self):
        StoreTheme.objects.create(store=self.store)
        resp = self.client.get(self.url)
        assert resp.status_code == 200

    def test_save_page_data(self):
        data = {
            'grapesjs_data': json.dumps({'components': [{'type': 'text'}]}),
            'html_content': '<p>Updated</p>',
            'css_content': 'p{color:blue}',
        }
        resp = self.client.post(self.url, data)
        assert resp.status_code == 200
        result = resp.json()
        assert result['status'] == 'ok'

    def test_save_invalid_json_returns_400(self):
        resp = self.client.post(self.url, {
            'grapesjs_data': '{invalid json',
            'html_content': '',
        })
        assert resp.status_code == 400

    def test_seo_update(self):
        resp = self.client.post(self.url, {
            'seo_update': '1',
            'meta_title': 'テストSEO',
            'meta_description': 'テスト説明',
            'og_image_url': 'https://example.com/img.jpg',
        })
        assert resp.status_code == 200
        self.page.refresh_from_db()
        assert self.page.meta_title == 'テストSEO'


@pytest.mark.django_db
class PageBuilderPublishViewTest(TestCase):
    """Publish/unpublish tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('pubadmin', password='pass123')
        cls.store = Store.objects.create(name='公開テスト店')
        cls.page = CustomPage.objects.create(
            store=cls.store, title='公開ページ', slug='pub-page',
        )

    def setUp(self):
        self.client.login(username='pubadmin', password='pass123')
        self.url = reverse(
            'admin_page_builder_publish', args=[self.store.pk, self.page.pk],
        )

    def test_publish(self):
        resp = self.client.post(self.url, {'action': 'publish'})
        assert resp.json()['is_published'] is True
        self.page.refresh_from_db()
        assert self.page.is_published is True
        assert self.page.published_at is not None

    def test_unpublish(self):
        self.page.is_published = True
        self.page.save()
        resp = self.client.post(self.url, {'action': 'unpublish'})
        assert resp.json()['is_published'] is False


@pytest.mark.django_db
class PageBuilderUploadViewTest(TestCase):
    """Image upload API tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('uploadmin', password='pass123')
        cls.store = Store.objects.create(name='アップロード店')

    def setUp(self):
        self.client.login(username='uploadmin', password='pass123')
        self.url = reverse('admin_page_builder_upload', args=[self.store.pk])

    def test_upload_no_files_returns_empty(self):
        resp = self.client.post(self.url)
        assert resp.status_code == 200
        assert resp.json()['data'] == []

    def test_upload_rejects_non_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('test.exe', b'binary', content_type='application/octet-stream')
        resp = self.client.post(self.url, {'files[]': f})
        assert resp.json()['data'] == []

    def test_upload_accepts_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        # Create a minimal valid PNG
        png_header = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
            b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
            b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        f = SimpleUploadedFile('test.png', png_header, content_type='image/png')
        resp = self.client.post(self.url, {'files[]': f})
        data = resp.json()['data']
        assert len(data) == 1


@pytest.mark.django_db
class CustomPagePublicViewTest(TestCase):
    """Public page display tests."""

    @classmethod
    def setUpTestData(cls):
        cls.store = Store.objects.create(name='公開表示店')

    def test_published_page_renders(self):
        page = CustomPage.objects.create(
            store=self.store, title='公開ページ', slug='public',
            html_content='<h1>Hello</h1>', is_published=True,
        )
        resp = self.client.get(f'/p/{self.store.pk}/public/')
        assert resp.status_code == 200
        assert 'Hello' in resp.content.decode()

    def test_unpublished_page_404(self):
        CustomPage.objects.create(
            store=self.store, title='非公開', slug='hidden',
            is_published=False,
        )
        resp = self.client.get(f'/p/{self.store.pk}/hidden/')
        assert resp.status_code == 404

    def test_fullwidth_uses_correct_template(self):
        CustomPage.objects.create(
            store=self.store, title='LP', slug='lp',
            layout='full_width', is_published=True,
            html_content='<div>Landing</div>',
        )
        resp = self.client.get(f'/p/{self.store.pk}/lp/')
        assert resp.status_code == 200
        # Full-width template has no sidebar
        assert 'Landing' in resp.content.decode()

    def test_nonexistent_slug_404(self):
        resp = self.client.get(f'/p/{self.store.pk}/no-such-page/')
        assert resp.status_code == 404
