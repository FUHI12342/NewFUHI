"""Tests for ChannelSalesAPIView — channel breakdown sales analytics."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from booking.models import Order, OrderItem, Product, Staff, Store, SiteSettings


def _make_store(name='テスト店舗'):
    return Store.objects.create(name=name)


def _make_staff_user(store, username='staff1', name='テストスタッフ', is_superuser=False):
    user = User.objects.create_user(
        username=username, password='testpass123',
        is_staff=True, is_superuser=is_superuser,
    )
    staff = Staff.objects.create(user=user, store=store, name=name)
    return user, staff


def _make_product(store, name='テスト商品', price=1000):
    return Product.objects.create(store=store, name=name, price=price, is_active=True)


def _make_order_with_item(store, product, channel='pos', qty=1, unit_price=1000, days_ago=1):
    order = Order.objects.create(
        store=store,
        channel=channel,
        created_at=timezone.now() - timedelta(days=days_ago),
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        qty=qty,
        unit_price=unit_price,
    )
    return order


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
class ChannelSalesAPITestBase(TestCase):
    def setUp(self):
        self.store = _make_store()
        self.admin_user = User.objects.create_superuser(
            username='admin', password='admin123',
        )
        self.product = _make_product(self.store)
        self.client = APIClient()
        self.url = reverse('booking_api:channel_sales_api')
        # Ensure SiteSettings exists with defaults (all enabled)
        self.settings = SiteSettings.load()


class TestChannelSalesAuth(ChannelSalesAPITestBase):
    """1. 未認証 → 403"""

    def test_unauthenticated_returns_403(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)


class TestChannelSalesBasic(ChannelSalesAPITestBase):
    """2. 認証済み → 200 + channels/trend 含む"""

    def test_authenticated_returns_200_with_structure(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('channels', data)
        self.assertIn('trend', data)
        self.assertIn('channel_labels', data)


class TestChannelSalesECDisabled(ChannelSalesAPITestBase):
    """3. EC無効時 → channels に 'ec' なし"""

    def test_ec_disabled_excludes_ec(self):
        self.settings.show_admin_ec_shop = False
        self.settings.save()
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(self.url)
        data = response.json()
        self.assertNotIn('ec', data['channels'])


class TestChannelSalesPOSDisabled(ChannelSalesAPITestBase):
    """4. POS無効時 → channels に 'pos','table' なし"""

    def test_pos_disabled_excludes_pos_and_table(self):
        self.settings.show_admin_pos = False
        self.settings.save()
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(self.url)
        data = response.json()
        self.assertNotIn('pos', data['channels'])
        self.assertNotIn('table', data['channels'])


class TestChannelSalesReservationDisabled(ChannelSalesAPITestBase):
    """5. 予約無効時 → channels に 'reservation' なし"""

    def test_reservation_disabled_excludes_reservation(self):
        self.settings.show_admin_reservation = False
        self.settings.save()
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(self.url)
        data = response.json()
        self.assertNotIn('reservation', data['channels'])


class TestChannelSalesPeriodDaily(ChannelSalesAPITestBase):
    """6. period=daily → TruncDate で集計"""

    def test_period_daily(self):
        _make_order_with_item(self.store, self.product, channel='pos', days_ago=1)
        _make_order_with_item(self.store, self.product, channel='pos', days_ago=2)

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url, {'period': 'daily'})
        data = response.json()
        self.assertEqual(response.status_code, 200)
        # Daily should have separate entries per date
        dates = [t['date'] for t in data['trend']]
        self.assertEqual(len(dates), len(set(dates)))  # unique dates


class TestChannelSalesPeriodWeekly(ChannelSalesAPITestBase):
    """7. period=weekly → TruncWeek で集計"""

    def test_period_weekly(self):
        _make_order_with_item(self.store, self.product, channel='pos', days_ago=1)
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url, {'period': 'weekly'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data['trend'], list)


class TestChannelSalesPeriodMonthly(ChannelSalesAPITestBase):
    """8. period=monthly → TruncMonth で集計"""

    def test_period_monthly(self):
        _make_order_with_item(self.store, self.product, channel='pos', days_ago=1)
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url, {'period': 'monthly'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data['trend'], list)


class TestChannelSalesAmounts(ChannelSalesAPITestBase):
    """9. チャネル別金額が正確"""

    def test_channel_amounts_accurate(self):
        _make_order_with_item(self.store, self.product, channel='pos', qty=2, unit_price=500, days_ago=1)
        _make_order_with_item(self.store, self.product, channel='ec', qty=3, unit_price=1000, days_ago=1)

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        data = response.json()

        # Build channel → total map from trend
        channel_totals = {}
        for t in data['trend']:
            ch = t['channel']
            channel_totals[ch] = channel_totals.get(ch, 0) + t['total']

        self.assertEqual(channel_totals.get('pos', 0), 1000)   # 2 * 500
        self.assertEqual(channel_totals.get('ec', 0), 3000)    # 3 * 1000


class TestChannelSalesStoreScope(ChannelSalesAPITestBase):
    """10. store scope: スタッフは自店舗のみ"""

    def test_staff_sees_only_own_store(self):
        store2 = _make_store(name='他店舗')
        product2 = _make_product(store2, name='他店商品')
        user, staff = _make_staff_user(self.store, username='staffA', name='スタッフA')

        _make_order_with_item(self.store, self.product, channel='pos', qty=1, unit_price=500, days_ago=1)
        _make_order_with_item(store2, product2, channel='pos', qty=1, unit_price=2000, days_ago=1)

        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        data = response.json()

        total = sum(t['total'] for t in data['trend'])
        self.assertEqual(total, 500)  # Only own store


class TestChannelSalesAllDisabled(ChannelSalesAPITestBase):
    """11. 全チャネル無効 → 空結果"""

    def test_all_channels_disabled_returns_empty(self):
        self.settings.show_admin_ec_shop = False
        self.settings.show_admin_pos = False
        self.settings.show_admin_reservation = False
        self.settings.save()

        _make_order_with_item(self.store, self.product, channel='pos', days_ago=1)

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        data = response.json()

        self.assertEqual(data['channels'], [])
        self.assertEqual(data['trend'], [])
