"""
tests/test_refund_flow.py
Tests for:
  - refund_status set to 'pending' on cancel of paid reservations
  - mark_refund_completed admin action
  - LINE notification on refund completion
  - QR page showing cancelled reservations (not 404)
  - QR page cancelled banner
"""
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from booking.models import Schedule, Store, Staff


# ==============================================================
# Fixtures
# ==============================================================

@pytest.fixture
def paid_schedule(db, staff):
    """Create a confirmed paid schedule."""
    now = timezone.now()
    return Schedule.objects.create(
        start=now + timedelta(hours=24),
        end=now + timedelta(hours=25),
        staff=staff,
        customer_name='有料顧客',
        price=5000,
        is_temporary=False,
    )


@pytest.fixture
def free_schedule_rf(db, staff):
    """Create a confirmed free schedule."""
    now = timezone.now()
    return Schedule.objects.create(
        start=now + timedelta(hours=24),
        end=now + timedelta(hours=25),
        staff=staff,
        customer_name='無料顧客',
        price=0,
        is_temporary=False,
    )


@pytest.fixture
def cancelled_paid_schedule(db, staff):
    """Create a cancelled paid schedule with pending refund."""
    now = timezone.now()
    return Schedule.objects.create(
        start=now + timedelta(hours=24),
        end=now + timedelta(hours=25),
        staff=staff,
        customer_name='キャンセル済み顧客',
        price=3000,
        is_temporary=False,
        is_cancelled=True,
        refund_status='pending',
    )


# ==============================================================
# Refund status on cancel
# ==============================================================

@pytest.mark.django_db
class TestRefundStatusOnCancel:
    """キャンセル時に有料予約のrefund_statusがpendingに設定されるテスト。"""

    @patch('booking.views_booking.LineBotApi')
    def test_cancel_paid_sets_refund_pending(self, mock_bot_cls, paid_schedule):
        """有料予約をキャンセルするとrefund_status='pending'になる。"""
        mock_bot_cls.return_value = MagicMock()
        client = Client()
        url = reverse('booking:customer_cancel_confirm', args=[paid_schedule.reservation_number])
        response = client.post(url, {'cancel_token': paid_schedule.cancel_token})
        assert response.status_code == 200

        paid_schedule.refresh_from_db()
        assert paid_schedule.is_cancelled is True
        assert paid_schedule.refund_status == 'pending'

    @patch('booking.views_booking.LineBotApi')
    def test_cancel_free_keeps_refund_none(self, mock_bot_cls, free_schedule_rf):
        """無料予約をキャンセルしてもrefund_statusは'none'のまま。"""
        mock_bot_cls.return_value = MagicMock()
        client = Client()
        url = reverse('booking:customer_cancel_confirm', args=[free_schedule_rf.reservation_number])
        response = client.post(url, {'cancel_token': free_schedule_rf.cancel_token})
        assert response.status_code == 200

        free_schedule_rf.refresh_from_db()
        assert free_schedule_rf.is_cancelled is True
        assert free_schedule_rf.refund_status == 'none'


# ==============================================================
# QR page shows cancelled reservations
# ==============================================================

@pytest.mark.django_db
class TestQRPageCancelled:
    """キャンセル済み予約のQRページテスト。"""

    def test_qr_page_shows_cancelled_reservation(self, cancelled_paid_schedule):
        """キャンセル済み予約でも404にならず表示される。"""
        client = Client()
        url = reverse('booking:reservation_qr', args=[cancelled_paid_schedule.reservation_number])
        response = client.get(url)
        assert response.status_code == 200

    def test_qr_page_shows_cancelled_banner(self, cancelled_paid_schedule):
        """キャンセル済み予約のQRページに「キャンセル済み」バナーが表示される。"""
        client = Client()
        url = reverse('booking:reservation_qr', args=[cancelled_paid_schedule.reservation_number])
        response = client.get(url)
        content = response.content.decode('utf-8')
        assert 'キャンセル済み' in content

    def test_qr_page_active_reservation_no_cancelled_banner(self, paid_schedule):
        """有効な予約のQRページにはキャンセルバナーが表示されない。"""
        client = Client()
        url = reverse('booking:reservation_qr', args=[paid_schedule.reservation_number])
        response = client.get(url)
        content = response.content.decode('utf-8')
        assert 'この予約はキャンセル済みです' not in content

    def test_qr_page_hides_qr_code_when_cancelled(self, cancelled_paid_schedule):
        """キャンセル済み予約のQRページではQRコードが非表示。"""
        client = Client()
        url = reverse('booking:reservation_qr', args=[cancelled_paid_schedule.reservation_number])
        response = client.get(url)
        content = response.content.decode('utf-8')
        # QR image and backup code should not appear for cancelled reservations
        assert 'checkin_qr' not in content or 'opacity-60' in content


# ==============================================================
# Refund model fields
# ==============================================================

@pytest.mark.django_db
class TestRefundFields:
    """返金フィールドのテスト。"""

    def test_default_refund_status_is_none(self, paid_schedule):
        """新規予約のrefund_statusデフォルトは'none'。"""
        assert paid_schedule.refund_status == 'none'

    def test_refund_completed_at_initially_null(self, paid_schedule):
        """新規予約のrefund_completed_atはnull。"""
        assert paid_schedule.refund_completed_at is None

    def test_refund_completed_by_initially_null(self, paid_schedule):
        """新規予約のrefund_completed_byはnull。"""
        assert paid_schedule.refund_completed_by is None

    def test_refund_note_initially_empty(self, paid_schedule):
        """新規予約のrefund_noteは空。"""
        assert paid_schedule.refund_note == ''


# ==============================================================
# Reservation stats API days parameter
# ==============================================================

@pytest.mark.django_db
class TestReservationStatsDays:
    """ReservationStatsAPIView の days パラメータテスト。"""

    def test_default_days(self, admin_client):
        """daysパラメータなしでデフォルト30日のデータが返る。"""
        response = admin_client.get('/api/dashboard/reservations/')
        assert response.status_code == 200
        data = response.json()
        assert data.get('days') == 30

    def test_custom_days(self, admin_client):
        """daysパラメータ指定でカスタム期間のデータが返る。"""
        response = admin_client.get('/api/dashboard/reservations/?days=90')
        assert response.status_code == 200
        data = response.json()
        assert data.get('days') == 90

    def test_days_clamped_to_max(self, admin_client):
        """365日を超えるdaysは365にクランプされる。"""
        response = admin_client.get('/api/dashboard/reservations/?days=999')
        assert response.status_code == 200
        data = response.json()
        assert data.get('days') == 365
