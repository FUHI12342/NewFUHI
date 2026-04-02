"""Tests for StoreTheme (Phase 1: CSS Custom Properties theme system)."""
import pytest
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth.models import User

from booking.models import Store, StoreTheme
from booking.services.theme_presets import THEME_PRESETS, get_preset, get_preset_names
from booking.context_processors import store_theme


class StoreThemeModelTest(TestCase):
    """StoreTheme model unit tests."""

    def setUp(self):
        self.store = Store.objects.create(name='Test Store')

    def test_create_default_theme(self):
        theme = StoreTheme.objects.create(store=self.store)
        assert theme.primary_color == '#8c876c'
        assert theme.secondary_color == '#f1f0ec'
        assert theme.preset == 'default'

    def test_str_representation(self):
        theme = StoreTheme.objects.create(store=self.store)
        assert 'Test Store' in str(theme)
        assert 'デフォルト' in str(theme)

    def test_one_to_one_constraint(self):
        StoreTheme.objects.create(store=self.store)
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            StoreTheme.objects.create(store=self.store)

    def test_apply_preset_elegant(self):
        theme = StoreTheme(store=self.store)
        theme.apply_preset('elegant')
        assert theme.primary_color == '#2c3e50'
        assert theme.accent_color == '#c0392b'
        assert theme.preset == 'elegant'

    def test_apply_preset_unknown(self):
        theme = StoreTheme(store=self.store)
        original_color = theme.primary_color
        theme.apply_preset('nonexistent')
        assert theme.primary_color == original_color

    def test_custom_css_blank_by_default(self):
        theme = StoreTheme.objects.create(store=self.store)
        assert theme.custom_css == ''


class ThemePresetsTest(TestCase):
    """Theme presets service tests."""

    def test_all_presets_defined(self):
        names = get_preset_names()
        assert 'default' in names
        assert 'elegant' in names
        assert 'modern' in names
        assert 'natural' in names
        assert 'luxury' in names
        assert 'pop' in names
        assert 'japanese' in names
        assert len(names) == 7

    def test_preset_has_required_keys(self):
        required_keys = {
            'primary_color', 'secondary_color', 'accent_color',
            'text_color', 'header_bg_color', 'footer_bg_color',
            'heading_font', 'body_font',
        }
        for name, preset in THEME_PRESETS.items():
            assert required_keys.issubset(preset.keys()), f'{name} missing keys'

    def test_color_values_are_valid_hex(self):
        import re
        hex_pattern = re.compile(r'^#[0-9a-fA-F]{6}$')
        color_keys = {'primary_color', 'secondary_color', 'accent_color',
                      'text_color', 'header_bg_color', 'footer_bg_color'}
        for name, preset in THEME_PRESETS.items():
            for key in color_keys:
                assert hex_pattern.match(preset[key]), f'{name}.{key} = {preset[key]} is invalid hex'

    def test_get_preset_returns_dict(self):
        result = get_preset('default')
        assert isinstance(result, dict)
        assert result['primary_color'] == '#8c876c'

    def test_get_preset_unknown_returns_none(self):
        assert get_preset('nonexistent') is None


class StoreThemeContextProcessorTest(TestCase):
    """Context processor tests."""

    def setUp(self):
        self.factory = RequestFactory()
        self.store = Store.objects.create(name='Test Store')
        self.user = User.objects.create_user('testuser', password='pass')

    def test_non_admin_path_returns_theme(self):
        StoreTheme.objects.create(store=self.store)
        request = self.factory.get('/')
        request.user = self.user
        # resolver_match needed for URL kwargs
        request.resolver_match = None
        ctx = store_theme(request)
        assert ctx.get('store_theme') is not None

    def test_admin_path_returns_empty(self):
        StoreTheme.objects.create(store=self.store)
        request = self.factory.get('/admin/')
        request.user = self.user
        request.resolver_match = None
        ctx = store_theme(request)
        assert ctx == {}

    def test_no_theme_returns_none(self):
        # Store exists but no theme
        request = self.factory.get('/')
        request.user = self.user
        request.resolver_match = None
        ctx = store_theme(request)
        assert ctx.get('store_theme') is None

    def test_no_store_returns_none(self):
        Store.objects.all().delete()
        request = self.factory.get('/')
        request.user = self.user
        request.resolver_match = None
        ctx = store_theme(request)
        assert ctx.get('store_theme') is None
