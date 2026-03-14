"""
決済完了メッセージにアクセス情報が含まれるか検証するテスト.

- _build_access_lines ヘルパーの単体テスト
- process_payment の LINE / メール通知にアクセス情報が含まれるか
"""
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory
from django.utils import timezone

from booking.models import Store, Staff, Schedule
from booking.views import _build_access_lines

User = get_user_model()


# ==============================
# _build_access_lines 単体テスト
# ==============================

class TestBuildAccessLines:
    """_build_access_lines ヘルパー関数のテスト."""

    def _make_store(self, **kwargs):
        defaults = {
            'name': 'テスト店舗',
            'address': '東京都新宿区1-2-3',
            'nearest_station': '新宿駅',
            'access_info': '',
            'map_url': '',
        }
        defaults.update(kwargs)
        store = Store(**defaults)
        return store

    def test_full_info(self):
        store = self._make_store(
            access_info='東口を出て徒歩5分',
            map_url='https://maps.google.com/?q=test',
        )
        result = _build_access_lines(store)
        assert '■ 店舗アクセス' in result
        assert 'テスト店舗' in result
        assert '東京都新宿区1-2-3' in result
        assert '最寄り駅: 新宿駅' in result
        assert '東口を出て徒歩5分' in result
        assert '地図: https://maps.google.com/?q=test' in result

    def test_no_access_info(self):
        store = self._make_store(map_url='https://maps.google.com/?q=test')
        result = _build_access_lines(store)
        assert '■ 店舗アクセス' in result
        assert '東口' not in result
        assert '地図:' in result

    def test_no_map_url(self):
        store = self._make_store(access_info='徒歩3分')
        result = _build_access_lines(store)
        assert '徒歩3分' in result
        assert '地図:' not in result

    def test_no_nearest_station(self):
        store = self._make_store(nearest_station='')
        result = _build_access_lines(store)
        assert '最寄り駅' not in result

    def test_minimal_info(self):
        store = self._make_store(nearest_station='')
        result = _build_access_lines(store)
        assert '■ 店舗アクセス' in result
        assert 'テスト店舗' in result
        assert '東京都新宿区1-2-3' in result


# ==============================
# process_payment アクセス情報テスト
# ==============================

@pytest.fixture
def store_with_access(db):
    return Store.objects.create(
        name="新宿店",
        address="東京都新宿区1-1-1",
        nearest_station="新宿駅",
        access_info="西口を出て右折、徒歩3分",
        map_url="https://maps.google.com/?q=shinjuku",
    )


@pytest.fixture
def staff_member(db, store_with_access):
    user = User.objects.create_user(
        username="payment_test_staff",
        password="pass123",
        is_staff=True,
    )
    return Staff.objects.create(
        name="支払テスト占い師",
        store=store_with_access,
        user=user,
        line_id="staff_line_id",
    )


@pytest.fixture
def schedule_line(db, staff_member):
    """LINE 予約のスケジュール."""
    now = timezone.now()
    schedule = Schedule.objects.create(
        staff=staff_member,
        start=now + timedelta(days=1),
        end=now + timedelta(days=1, hours=1),
        customer_name="テスト顧客",
        reservation_number="PAY-TEST-001",
        is_temporary=True,
        booking_channel='line',
    )
    schedule.set_line_user_id('U_customer_line_id')
    schedule.save()
    return schedule


@pytest.fixture
def schedule_email(db, staff_member):
    """メール予約のスケジュール."""
    now = timezone.now()
    return Schedule.objects.create(
        staff=staff_member,
        start=now + timedelta(days=2),
        end=now + timedelta(days=2, hours=1),
        customer_name="メール顧客",
        customer_email="customer@example.com",
        reservation_number="PAY-TEST-002",
        is_temporary=True,
        booking_channel='email',
    )


class TestProcessPaymentAccessInfo:
    """process_payment で LINE / メール通知にアクセス情報が含まれるか."""

    @patch('booking.views.LineBotApi')
    def test_line_message_includes_access_info(
        self, mock_linebot_cls, schedule_line, store_with_access
    ):
        mock_api = MagicMock()
        mock_linebot_cls.return_value = mock_api

        from booking.views import process_payment
        factory = RequestFactory()
        request = factory.post('/webhook/')

        payment_response = {'type': 'payment.succeeded'}
        process_payment(payment_response, request, 'PAY-TEST-001')

        # LINE push_message が呼ばれたか
        assert mock_api.push_message.called
        calls = mock_api.push_message.call_args_list

        # 顧客向けメッセージ（2番目の呼び出し）にアクセス情報が含まれる
        customer_call = calls[-1]
        msg_text = customer_call[0][1].text
        assert '■ 店舗アクセス' in msg_text
        assert '新宿店' in msg_text
        assert '西口を出て右折、徒歩3分' in msg_text
        assert 'https://maps.google.com/?q=shinjuku' in msg_text

    @patch('booking.views.send_mail')
    @patch('booking.views.LineBotApi')
    def test_email_includes_access_info(
        self, mock_linebot_cls, mock_send_mail, schedule_email, store_with_access
    ):
        mock_linebot_cls.return_value = MagicMock()

        from booking.views import process_payment
        factory = RequestFactory()
        request = factory.post('/webhook/')

        payment_response = {'type': 'payment.succeeded'}
        process_payment(payment_response, request, 'PAY-TEST-002')

        # send_mail が呼ばれたか
        assert mock_send_mail.called
        call_kwargs = mock_send_mail.call_args
        email_body = call_kwargs[1].get('message') or call_kwargs[0][1]
        assert '■ 店舗アクセス' in email_body
        assert '新宿店' in email_body
        assert '西口を出て右折、徒歩3分' in email_body

    @patch('booking.views.LineBotApi')
    def test_payment_not_succeeded_ignored(self, mock_linebot_cls):
        mock_linebot_cls.return_value = MagicMock()

        from booking.views import process_payment
        factory = RequestFactory()
        request = factory.post('/webhook/')

        payment_response = {'type': 'payment.failed'}
        resp = process_payment(payment_response, request, 'NONEXISTENT')
        assert resp.status_code == 200
