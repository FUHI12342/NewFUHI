"""
Tests for booking.services.shift_notifications — LINE / Email 通知サービス.

LINE通知は send_staff_line() → _push_line_message() による個別Push方式に移行済み。
"""
import datetime as dt
import pytest
from datetime import date
from unittest.mock import patch

from django.core import mail
from django.utils import timezone

from booking.models import Schedule, ShiftPeriod, Staff
from booking.services.shift_notifications import (
    notify_shift_period_open,
    notify_shift_approved,
    notify_booking_confirmed,
)


@pytest.mark.django_db
class TestNotifyShiftPeriodOpen:
    """notify_shift_period_open: シフト募集開始通知"""

    def test_sends_line_push(self, shift_period, staff):
        """LINE通知が send_staff_line 経由で個別Pushされる"""
        staff.line_id = 'U12345'
        staff.notify_shift = True
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            notify_shift_period_open(shift_period)
            assert mock_push.call_count >= 1
            message = mock_push.call_args[0][1]
            assert 'シフト募集開始' in message
            assert shift_period.store.name in message

    def test_sends_email_to_staff(self, shift_period, staff, mail_outbox):
        """store に紐づくスタッフのメールアドレスにメールが送信される"""
        with patch('booking.services.staff_notifications._push_line_message'):
            notify_shift_period_open(shift_period)
        assert len(mail_outbox) == 1
        assert 'シフト募集開始' in mail_outbox[0].subject
        assert staff.user.email in mail_outbox[0].recipients()

    def test_no_staff_emails_no_email_sent(self, shift_period, mail_outbox):
        """メールアドレスを持つスタッフがいない場合はメール送信されない"""
        creator = shift_period.created_by
        creator.user.email = ''
        creator.user.save()

        with patch('booking.services.staff_notifications._push_line_message'):
            notify_shift_period_open(shift_period)
        assert len(mail_outbox) == 0

    def test_handles_line_failure_gracefully(self, shift_period, mail_outbox, staff):
        """LINE通知が失敗してもメール送信は正常に行われる"""
        staff.line_id = 'U12345'
        staff.notify_shift = True
        staff.save()

        with patch(
            'booking.services.staff_notifications._push_line_message',
            return_value=False,
        ):
            notify_shift_period_open(shift_period)
        # メールは送信される
        assert len(mail_outbox) == 1


@pytest.mark.django_db
class TestNotifyShiftApproved:
    """notify_shift_approved: シフト承認完了通知"""

    def test_sends_line_push(self, shift_period, staff):
        """LINE通知でシフト確定メッセージが個別Pushされる"""
        staff.line_id = 'U12345'
        staff.notify_shift = True
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            notify_shift_approved(shift_period)
            assert mock_push.call_count >= 1
            message = mock_push.call_args[0][1]
            assert 'シフト確定' in message

    def test_sends_email_to_staff(self, shift_period, staff, mail_outbox):
        """store のスタッフにメールが送信される"""
        with patch('booking.services.staff_notifications._push_line_message'):
            notify_shift_approved(shift_period)
        assert len(mail_outbox) == 1
        assert 'シフト確定' in mail_outbox[0].subject


@pytest.mark.django_db
class TestNotifyBookingConfirmed:
    """notify_booking_confirmed: 予約確定通知"""

    def test_sends_line_with_schedule_details(self, staff):
        """Schedule の日時・顧客名・料金が LINE メッセージに含まれる"""
        staff.line_id = 'U12345'
        staff.notify_booking = True
        staff.save()

        start_dt = timezone.make_aware(dt.datetime(2025, 4, 10, 14, 0))
        end_dt = start_dt + dt.timedelta(hours=1)
        schedule = Schedule.objects.create(
            staff=staff,
            start=start_dt,
            end=end_dt,
            customer_name='山田太郎',
            price=5000,
        )
        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            notify_booking_confirmed(schedule)
            mock_push.assert_called_once()
            message = mock_push.call_args[0][1]
            assert '予約確定' in message
            assert '山田太郎' in message
            assert '5000' in message

    def test_customer_name_none_shows_default(self, staff):
        """customer_name が None の場合 '未設定' と表示される"""
        staff.line_id = 'U12345'
        staff.notify_booking = True
        staff.save()

        start_dt = timezone.make_aware(dt.datetime(2025, 4, 10, 14, 0))
        end_dt = start_dt + dt.timedelta(hours=1)
        schedule = Schedule.objects.create(
            staff=staff,
            start=start_dt,
            end=end_dt,
            customer_name=None,
            price=0,
        )
        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            notify_booking_confirmed(schedule)
            message = mock_push.call_args[0][1]
            assert '未設定' in message
