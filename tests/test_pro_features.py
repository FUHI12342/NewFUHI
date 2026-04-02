"""Tests for pro designer features: SEO fields, page duplication, saved blocks."""
import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.urls import reverse
from booking.models import Store, CustomPage, SavedBlock


@pytest.mark.django_db
class CustomPageSEOFieldsTest(TestCase):
    """SEO fields on CustomPage model."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('testadmin', password='pass')
        cls.store = Store.objects.create(name='SEOテスト店')

    def test_seo_fields_default_empty(self):
        page = CustomPage.objects.create(
            store=self.store, title='テスト', slug='test',
        )
        assert page.meta_title == ''
        assert page.meta_description == ''
        assert page.og_image_url == ''

    def test_seo_fields_save_and_retrieve(self):
        page = CustomPage.objects.create(
            store=self.store, title='SEOページ', slug='seo',
            meta_title='カスタムタイトル',
            meta_description='これはテスト説明文です',
            og_image_url='https://example.com/og.jpg',
        )
        page.refresh_from_db()
        assert page.meta_title == 'カスタムタイトル'
        assert page.meta_description == 'これはテスト説明文です'
        assert page.og_image_url == 'https://example.com/og.jpg'

    def test_seo_meta_title_max_length(self):
        field = CustomPage._meta.get_field('meta_title')
        assert field.max_length == 70

    def test_seo_meta_description_max_length(self):
        field = CustomPage._meta.get_field('meta_description')
        assert field.max_length == 160

    def test_seo_og_image_url_max_length(self):
        field = CustomPage._meta.get_field('og_image_url')
        assert field.max_length == 500


@pytest.mark.django_db
class PageDuplicationTest(TestCase):
    """Page duplication view."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            'dupadmin', password='dupadminpass',
        )
        cls.store = Store.objects.create(name='複製テスト店')
        cls.page = CustomPage.objects.create(
            store=cls.store, title='元ページ', slug='original',
            html_content='<div>Content</div>',
            css_content='div { color: red; }',
            page_type='landing', layout='full_width',
        )

    def setUp(self):
        self.client.login(username='dupadmin', password='dupadminpass')
        self.url = reverse(
            'admin_page_builder_duplicate',
            args=[self.store.pk, self.page.pk],
        )

    def test_duplicate_creates_copy(self):
        initial_count = CustomPage.objects.filter(store=self.store).count()
        self.client.post(self.url)
        assert CustomPage.objects.filter(store=self.store).count() == initial_count + 1

    def test_duplicate_slug_has_copy_suffix(self):
        self.client.post(self.url)
        copy = CustomPage.objects.filter(store=self.store, slug='original-copy').first()
        assert copy is not None

    def test_duplicate_preserves_content(self):
        self.client.post(self.url)
        copy = CustomPage.objects.get(store=self.store, slug='original-copy')
        assert copy.html_content == '<div>Content</div>'
        assert copy.css_content == 'div { color: red; }'
        assert copy.layout == 'full_width'
        assert copy.page_type == 'landing'

    def test_duplicate_title_has_copy_label(self):
        self.client.post(self.url)
        copy = CustomPage.objects.get(store=self.store, slug='original-copy')
        assert 'コピー' in copy.title

    def test_duplicate_increments_slug_on_collision(self):
        self.client.post(self.url)  # First copy
        self.client.post(self.url)  # Second copy
        assert CustomPage.objects.filter(
            store=self.store, slug='original-copy-1',
        ).exists()


@pytest.mark.django_db
class SavedBlockModelTest(TestCase):
    """SavedBlock model tests."""

    @classmethod
    def setUpTestData(cls):
        cls.store = Store.objects.create(name='ブロックテスト店')

    def test_create_saved_block(self):
        block = SavedBlock.objects.create(
            store=self.store,
            label='ヘッダーブロック',
            html_content='<header>Test</header>',
        )
        assert block.pk is not None
        assert block.label == 'ヘッダーブロック'

    def test_default_category(self):
        block = SavedBlock.objects.create(
            store=self.store, label='テスト',
            html_content='<div>test</div>',
        )
        assert block.category == '保存済み'

    def test_ordering_newest_first(self):
        b1 = SavedBlock.objects.create(
            store=self.store, label='First',
            html_content='<div>1</div>',
        )
        b2 = SavedBlock.objects.create(
            store=self.store, label='Second',
            html_content='<div>2</div>',
        )
        blocks = list(SavedBlock.objects.filter(store=self.store))
        assert blocks[0].pk == b2.pk

    def test_cascade_delete_with_store(self):
        store2 = Store.objects.create(name='削除テスト店')
        SavedBlock.objects.create(
            store=store2, label='消える',
            html_content='<div>gone</div>',
        )
        store2.delete()
        assert SavedBlock.objects.filter(store=store2).count() == 0

    def test_str_representation(self):
        block = SavedBlock.objects.create(
            store=self.store, label='テストブロック',
            html_content='<div>test</div>',
        )
        assert 'テストブロック' in str(block)


@pytest.mark.django_db
class SavedBlockAPITest(TestCase):
    """SavedBlock API view tests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            'blockadmin', password='blockadminpass',
        )
        cls.store = Store.objects.create(name='API店')

    def setUp(self):
        self.client.login(username='blockadmin', password='blockadminpass')
        self.list_url = reverse('admin_saved_block_list', args=[self.store.pk])
        self.create_url = reverse('admin_saved_block_create', args=[self.store.pk])

    def test_list_empty(self):
        resp = self.client.get(self.list_url)
        assert resp.status_code == 200
        data = resp.json()
        assert data['blocks'] == []

    def test_create_block(self):
        resp = self.client.post(
            self.create_url,
            {'label': 'APIブロック', 'html_content': '<section>API</section>'},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'ok'
        assert data['block']['label'] == 'APIブロック'

    def test_create_block_requires_label(self):
        resp = self.client.post(
            self.create_url,
            {'label': '', 'html_content': '<div>test</div>'},
        )
        assert resp.status_code == 400

    def test_create_block_requires_html(self):
        resp = self.client.post(
            self.create_url,
            {'label': 'テスト', 'html_content': ''},
        )
        assert resp.status_code == 400

    def test_list_returns_created_blocks(self):
        self.client.post(
            self.create_url,
            {'label': 'ブロック1', 'html_content': '<div>1</div>'},
        )
        self.client.post(
            self.create_url,
            {'label': 'ブロック2', 'html_content': '<div>2</div>'},
        )
        resp = self.client.get(self.list_url)
        data = resp.json()
        assert len(data['blocks']) == 2

    def test_delete_block(self):
        block = SavedBlock.objects.create(
            store=self.store, label='削除対象',
            html_content='<div>delete me</div>',
        )
        delete_url = reverse(
            'admin_saved_block_delete',
            args=[self.store.pk, block.pk],
        )
        resp = self.client.post(delete_url)
        assert resp.status_code == 200
        assert resp.json()['status'] == 'ok'
        assert not SavedBlock.objects.filter(pk=block.pk).exists()

    def test_delete_nonexistent_returns_404(self):
        delete_url = reverse(
            'admin_saved_block_delete',
            args=[self.store.pk, 99999],
        )
        resp = self.client.post(delete_url)
        assert resp.status_code == 404
