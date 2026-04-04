"""Tests for demo data service — demo mode filtering logic."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from booking.models import SiteSettings, Store, Order
from booking.services.demo_data_service import (
    is_demo_mode_active,
    get_demo_exclusion,
    invalidate_demo_mode_cache,
)


class DemoDataServiceTest(TestCase):
    """Test demo mode filtering."""

    def setUp(self):
        self.settings = SiteSettings.load()
        self.store = Store.objects.create(name='テスト店舗')
        invalidate_demo_mode_cache()

    def test_demo_mode_off_returns_false(self):
        self.settings.demo_mode_enabled = False
        self.settings.save()
        invalidate_demo_mode_cache()
        self.assertFalse(is_demo_mode_active())

    def test_demo_mode_on_returns_true(self):
        self.settings.demo_mode_enabled = True
        self.settings.save()
        invalidate_demo_mode_cache()
        self.assertTrue(is_demo_mode_active())

    def test_get_demo_exclusion_when_off(self):
        """デモモードOFF時はis_demo=Falseフィルタを返す"""
        self.settings.demo_mode_enabled = False
        self.settings.save()
        invalidate_demo_mode_cache()
        result = get_demo_exclusion()
        self.assertEqual(result, {'is_demo': False})

    def test_get_demo_exclusion_when_on(self):
        """デモモードON時は空辞書を返す（フィルタなし）"""
        self.settings.demo_mode_enabled = True
        self.settings.save()
        invalidate_demo_mode_cache()
        result = get_demo_exclusion()
        self.assertEqual(result, {})

    def test_get_demo_exclusion_with_prefix(self):
        """prefix指定時に正しいキーを生成"""
        self.settings.demo_mode_enabled = False
        self.settings.save()
        invalidate_demo_mode_cache()
        result = get_demo_exclusion('order__')
        self.assertEqual(result, {'order__is_demo': False})

    def test_demo_filter_excludes_demo_orders(self):
        """実際のクエリでデモデータが除外されることを確認"""
        self.settings.demo_mode_enabled = False
        self.settings.save()
        invalidate_demo_mode_cache()

        Order.objects.create(store=self.store, is_demo=False)
        Order.objects.create(store=self.store, is_demo=True)

        demo_filter = get_demo_exclusion()
        count = Order.objects.filter(**demo_filter).count()
        self.assertEqual(count, 1)

    def test_demo_filter_includes_all_when_on(self):
        """デモモードON時は全データが含まれる"""
        self.settings.demo_mode_enabled = True
        self.settings.save()
        invalidate_demo_mode_cache()

        Order.objects.create(store=self.store, is_demo=False)
        Order.objects.create(store=self.store, is_demo=True)

        demo_filter = get_demo_exclusion()
        count = Order.objects.filter(**demo_filter).count()
        self.assertEqual(count, 2)

    def test_cache_invalidation(self):
        """キャッシュ無効化が正しく動作する"""
        self.settings.demo_mode_enabled = False
        self.settings.save()
        invalidate_demo_mode_cache()
        self.assertFalse(is_demo_mode_active())

        self.settings.demo_mode_enabled = True
        self.settings.save()
        invalidate_demo_mode_cache()
        self.assertTrue(is_demo_mode_active())
