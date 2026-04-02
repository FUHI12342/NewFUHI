"""Tests for Phase 3: GrapesJS custom page builder."""
import json
import pytest
from django.test import TestCase
from django.contrib.auth.models import User

from booking.models import Store, CustomPage, PageTemplate


class CustomPageModelTest(TestCase):
    """CustomPage model tests."""

    def setUp(self):
        self.store = Store.objects.create(name='Test Store')

    def test_create_page(self):
        page = CustomPage.objects.create(
            store=self.store, title='Spring Campaign',
            slug='spring-campaign', page_type='campaign',
        )
        assert page.title == 'Spring Campaign'
        assert page.is_published is False
        assert page.grapesjs_data == {}

    def test_unique_together_slug(self):
        CustomPage.objects.create(
            store=self.store, title='Page 1', slug='test-slug',
        )
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            CustomPage.objects.create(
                store=self.store, title='Page 2', slug='test-slug',
            )

    def test_str_representation(self):
        page = CustomPage.objects.create(
            store=self.store, title='My Page', slug='my-page',
        )
        assert 'Test Store' in str(page)
        assert 'My Page' in str(page)

    def test_get_absolute_url(self):
        page = CustomPage.objects.create(
            store=self.store, title='My Page', slug='my-page',
        )
        url = page.get_absolute_url()
        assert f'/p/{self.store.pk}/my-page/' in url


class PageTemplateModelTest(TestCase):
    """PageTemplate model tests."""

    def test_create_template(self):
        tpl = PageTemplate.objects.create(
            name='Salon Basic', category='salon',
            html_content='<div>Hello</div>',
        )
        assert tpl.is_system is True
        assert 'サロン' in str(tpl)


class PageBuilderListViewTest(TestCase):
    """Page builder list view tests."""

    def setUp(self):
        self.store = Store.objects.create(name='Test Store')
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')

    def test_list_view(self):
        self.client.force_login(self.user)
        resp = self.client.get(f'/admin/pages/{self.store.pk}/')
        assert resp.status_code == 200

    def test_create_view_get(self):
        self.client.force_login(self.user)
        resp = self.client.get(f'/admin/pages/{self.store.pk}/new/')
        assert resp.status_code == 200


class PageBuilderEditViewTest(TestCase):
    """Page builder edit view tests."""

    def setUp(self):
        self.store = Store.objects.create(name='Test Store')
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        self.page = CustomPage.objects.create(
            store=self.store, title='Test Page', slug='test-page',
        )

    def test_edit_view_get(self):
        self.client.force_login(self.user)
        resp = self.client.get(f'/admin/pages/{self.store.pk}/{self.page.pk}/edit/')
        assert resp.status_code == 200
        assert 'grapesjs_data_json' in resp.context

    def test_edit_view_post_saves(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            f'/admin/pages/{self.store.pk}/{self.page.pk}/edit/',
            {
                'grapesjs_data': json.dumps({'components': [], 'styles': []}),
                'html_content': '<div>test</div>',
                'css_content': '.test { color: red; }',
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'ok'
        self.page.refresh_from_db()
        assert self.page.html_content == '<div>test</div>'

    def test_publish_view(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            f'/admin/pages/{self.store.pk}/{self.page.pk}/publish/',
            {'action': 'publish'},
        )
        assert resp.status_code == 200
        self.page.refresh_from_db()
        assert self.page.is_published is True

    def test_unpublish_view(self):
        self.page.is_published = True
        self.page.save()
        self.client.force_login(self.user)
        resp = self.client.post(
            f'/admin/pages/{self.store.pk}/{self.page.pk}/publish/',
            {'action': 'unpublish'},
        )
        self.page.refresh_from_db()
        assert self.page.is_published is False


class CustomPagePublicViewTest(TestCase):
    """Public custom page view tests."""

    def setUp(self):
        self.store = Store.objects.create(name='Test Store')

    def test_published_page_accessible(self):
        page = CustomPage.objects.create(
            store=self.store, title='Public Page', slug='public',
            html_content='<p>Hello World</p>', is_published=True,
        )
        resp = self.client.get(f'/p/{self.store.pk}/public/')
        assert resp.status_code == 200
        assert 'Hello World' in resp.content.decode()

    def test_unpublished_page_404(self):
        CustomPage.objects.create(
            store=self.store, title='Draft', slug='draft',
            is_published=False,
        )
        resp = self.client.get(f'/p/{self.store.pk}/draft/')
        assert resp.status_code == 404

    def test_nonexistent_page_404(self):
        resp = self.client.get(f'/p/{self.store.pk}/nonexistent/')
        assert resp.status_code == 404
