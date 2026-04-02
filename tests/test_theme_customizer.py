"""Tests for Phase 4: Theme Customizer (WordPress-style live preview)."""
import json

from django.test import TestCase
from django.contrib.auth.models import User

from booking.models import Store, StoreTheme
from booking.services.theme_presets import THEME_PRESETS


class ThemeCustomizerViewTest(TestCase):
    """Theme customizer editor view tests."""

    def setUp(self):
        self.store = Store.objects.create(name='Test Store')
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')

    def test_customizer_get_without_theme(self):
        self.client.force_login(self.user)
        resp = self.client.get(f'/admin/theme/customizer/{self.store.pk}/')
        assert resp.status_code == 200
        assert 'presets_json' in resp.context

    def test_customizer_get_with_theme(self):
        StoreTheme.objects.create(store=self.store, preset='elegant')
        self.client.force_login(self.user)
        resp = self.client.get(f'/admin/theme/customizer/{self.store.pk}/')
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'テーマカスタマイザー' in content

    def test_customizer_presets_json_in_context(self):
        self.client.force_login(self.user)
        resp = self.client.get(f'/admin/theme/customizer/{self.store.pk}/')
        presets_json = resp.context['presets_json']
        presets = json.loads(presets_json)
        assert 'default' in presets
        assert 'elegant' in presets

    def test_customizer_post_saves_theme(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            f'/admin/theme/customizer/{self.store.pk}/',
            {
                'primary_color': '#ff0000',
                'secondary_color': '#00ff00',
                'accent_color': '#0000ff',
                'text_color': '#111111',
                'header_bg_color': '#222222',
                'footer_bg_color': '#333333',
                'heading_font': 'Noto Sans JP',
                'body_font': 'Noto Serif JP',
                'preset': 'custom',
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'ok'

        theme = StoreTheme.objects.get(store=self.store)
        assert theme.primary_color == '#ff0000'
        assert theme.heading_font == 'Noto Sans JP'
        assert theme.preset == 'custom'

    def test_customizer_post_updates_existing_theme(self):
        StoreTheme.objects.create(store=self.store, primary_color='#8c876c')
        self.client.force_login(self.user)
        resp = self.client.post(
            f'/admin/theme/customizer/{self.store.pk}/',
            {
                'primary_color': '#aabbcc',
                'secondary_color': '#f1f0ec',
                'accent_color': '#b8860b',
                'text_color': '#333333',
                'header_bg_color': '#8c876c',
                'footer_bg_color': '#333333',
                'heading_font': 'M PLUS 1p',
                'body_font': 'M PLUS 1p',
                'preset': 'modern',
            },
        )
        assert resp.status_code == 200
        theme = StoreTheme.objects.get(store=self.store)
        assert theme.primary_color == '#aabbcc'
        assert theme.preset == 'modern'

    def test_customizer_post_custom_css(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            f'/admin/theme/customizer/{self.store.pk}/',
            {
                'primary_color': '#8c876c',
                'secondary_color': '#f1f0ec',
                'accent_color': '#b8860b',
                'text_color': '#333333',
                'header_bg_color': '#8c876c',
                'footer_bg_color': '#333333',
                'heading_font': 'Hiragino Kaku Gothic Pro',
                'body_font': 'Hiragino Kaku Gothic Pro',
                'preset': 'custom',
                'custom_css': '.hero { padding: 40px; }',
            },
        )
        assert resp.status_code == 200
        theme = StoreTheme.objects.get(store=self.store)
        assert theme.custom_css == '.hero { padding: 40px; }'

    def test_customizer_requires_auth(self):
        resp = self.client.get(f'/admin/theme/customizer/{self.store.pk}/')
        assert resp.status_code == 302  # redirect to login


class ThemePreviewViewTest(TestCase):
    """Theme preview iframe view tests."""

    def setUp(self):
        self.store = Store.objects.create(name='Test Store')
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')

    def test_preview_renders(self):
        StoreTheme.objects.create(store=self.store)
        self.client.force_login(self.user)
        resp = self.client.get(
            f'/admin/theme/preview/{self.store.pk}/?preview=1',
        )
        assert resp.status_code == 200
        assert 'store_theme' in resp.context

    def test_preview_overrides_color(self):
        theme = StoreTheme.objects.create(
            store=self.store, primary_color='#8c876c',
        )
        self.client.force_login(self.user)
        resp = self.client.get(
            f'/admin/theme/preview/{self.store.pk}/'
            '?preview=1&primary_color=%23ff0000',
        )
        assert resp.status_code == 200
        # テンプレートに渡されたテーマの primary_color が上書きされていること
        preview_theme = resp.context['store_theme']
        assert preview_theme.primary_color == '#ff0000'

    def test_preview_without_theme(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            f'/admin/theme/preview/{self.store.pk}/?preview=1',
        )
        assert resp.status_code == 200

    def test_preview_nonexistent_store_404(self):
        self.client.force_login(self.user)
        resp = self.client.get('/admin/theme/preview/99999/?preview=1')
        assert resp.status_code == 404


class ThemePresetsAPIViewTest(TestCase):
    """Theme presets API tests."""

    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')

    def test_presets_api_returns_json(self):
        self.client.force_login(self.user)
        resp = self.client.get('/admin/theme/presets/')
        assert resp.status_code == 200
        data = resp.json()
        assert 'default' in data
        assert 'elegant' in data
        assert len(data) == 7
