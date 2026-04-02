"""Tests for CustomPage layout field and full-width rendering."""
import pytest
from django.test import TestCase, RequestFactory
from django.urls import reverse

from booking.models import Store, CustomPage


class CustomPageLayoutFieldTest(TestCase):
    """Test the layout field on CustomPage."""

    @classmethod
    def setUpTestData(cls):
        cls.store = Store.objects.create(name='テストサロン')

    def test_layout_default_is_standard(self):
        page = CustomPage.objects.create(
            store=self.store,
            title='テストページ',
            slug='test-page',
        )
        assert page.layout == 'standard'

    def test_layout_full_width_save_and_retrieve(self):
        page = CustomPage.objects.create(
            store=self.store,
            title='LP ページ',
            slug='lp-page',
            layout='full_width',
        )
        page.refresh_from_db()
        assert page.layout == 'full_width'

    def test_layout_choices(self):
        from booking.models.custom_page import LAYOUT_CHOICES
        layout_values = [c[0] for c in LAYOUT_CHOICES]
        assert 'standard' in layout_values
        assert 'full_width' in layout_values


class CustomPageFullWidthRenderTest(TestCase):
    """Test that full_width pages use the correct template."""

    @classmethod
    def setUpTestData(cls):
        cls.store = Store.objects.create(name='テストサロン')
        cls.standard_page = CustomPage.objects.create(
            store=cls.store,
            title='標準ページ',
            slug='standard-page',
            layout='standard',
            is_published=True,
            html_content='<p>Standard content</p>',
        )
        cls.fullwidth_page = CustomPage.objects.create(
            store=cls.store,
            title='フルワイドページ',
            slug='fullwidth-page',
            layout='full_width',
            is_published=True,
            html_content='<p>Full width content</p>',
        )

    def test_standard_page_uses_standard_template(self):
        url = reverse('custom_page_public', args=[self.store.pk, 'standard-page'])
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'booking/custom_page.html')

    def test_fullwidth_page_uses_fullwidth_template(self):
        url = reverse('custom_page_public', args=[self.store.pk, 'fullwidth-page'])
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'booking/custom_page_full_width.html')

    def test_fullwidth_page_content_rendered(self):
        url = reverse('custom_page_public', args=[self.store.pk, 'fullwidth-page'])
        response = self.client.get(url)
        assert 'Full width content' in response.content.decode()
