"""Tests for site setup wizard."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from booking.models import Store, StoreTheme, CustomPage


class SiteSetupWizardTest(TestCase):
    """Test the site setup wizard view."""

    @classmethod
    def setUpTestData(cls):
        cls.store = Store.objects.create(name='テストサロン')
        cls.admin_user = User.objects.create_superuser(
            username='admin', password='testpass123',
        )

    def setUp(self):
        self.client.login(username='admin', password='testpass123')

    def test_wizard_returns_200(self):
        url = reverse('admin_site_wizard', args=[self.store.pk])
        response = self.client.get(url)
        assert response.status_code == 200

    def test_wizard_shows_store_name(self):
        url = reverse('admin_site_wizard', args=[self.store.pk])
        response = self.client.get(url)
        assert 'テストサロン' in response.content.decode()

    def test_wizard_shows_three_steps(self):
        url = reverse('admin_site_wizard', args=[self.store.pk])
        response = self.client.get(url)
        content = response.content.decode()
        assert 'STEP 1' in content
        assert 'STEP 2' in content
        assert 'STEP 3' in content

    def test_wizard_step_links(self):
        url = reverse('admin_site_wizard', args=[self.store.pk])
        response = self.client.get(url)
        content = response.content.decode()
        # Should contain links to theme customizer, layout editor, page builder
        assert reverse('admin_theme_customizer', args=[self.store.pk]) in content
        assert reverse('admin_page_layout_editor', args=[self.store.pk]) in content
        assert reverse('admin_page_builder_list', args=[self.store.pk]) in content

    def test_wizard_completion_count_zero(self):
        url = reverse('admin_site_wizard', args=[self.store.pk])
        response = self.client.get(url)
        assert response.context['completed_count'] == 0

    def test_wizard_completion_with_theme(self):
        StoreTheme.objects.create(store=self.store)
        url = reverse('admin_site_wizard', args=[self.store.pk])
        response = self.client.get(url)
        assert response.context['completed_count'] == 1

    def test_wizard_completion_all(self):
        StoreTheme.objects.create(store=self.store)
        from booking.models import PageLayout
        PageLayout.objects.create(store=self.store, page_type='home', sections_json=[])
        CustomPage.objects.create(store=self.store, title='Test', slug='test')
        url = reverse('admin_site_wizard', args=[self.store.pk])
        response = self.client.get(url)
        assert response.context['completed_count'] == 3

    def test_wizard_404_invalid_store(self):
        url = reverse('admin_site_wizard', args=[99999])
        response = self.client.get(url)
        assert response.status_code == 404
