"""
Tests for booking.services.staff_notifications — 個別LINE通知サービス.
"""
import datetime as dt
import pytest
from unittest.mock import patch, MagicMock

from django.utils import timezone

from booking.models import Schedule, ShiftPeriod, ShiftAssignment, Staff


# ==============================
# send_staff_line
# ==============================

@pytest.mark.django_db
class TestSendStaffLine:
    """send_staff_line: 個別スタッフLINE通知"""

    def test_sends_when_enabled_and_line_id_set(self, staff):
        """通知ON + LINE ID設定済み → 送信される"""
        from booking.services.staff_notifications import send_staff_line

        staff.line_id = 'U1234567890'
        staff.notify_business = True
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            result = send_staff_line(staff, 'テストメッセージ', notification_type='business')
            assert result is True
            mock_push.assert_called_once_with('U1234567890', 'テストメッセージ')

    def test_skips_when_notification_disabled(self, staff):
        """通知OFF → 送信されない"""
        from booking.services.staff_notifications import send_staff_line

        staff.line_id = 'U1234567890'
        staff.notify_business = False
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message') as mock_push:
            result = send_staff_line(staff, 'テスト', notification_type='business')
            assert result is False
            mock_push.assert_not_called()

    def test_skips_when_no_line_id(self, staff):
        """LINE ID未設定 → 送信されない"""
        from booking.services.staff_notifications import send_staff_line

        staff.line_id = ''
        staff.notify_business = True
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message') as mock_push:
            result = send_staff_line(staff, 'テスト', notification_type='business')
            assert result is False
            mock_push.assert_not_called()

    def test_booking_notification_type(self, staff):
        """notification_type='booking' → notify_booking を参照"""
        from booking.services.staff_notifications import send_staff_line

        staff.line_id = 'U1234567890'
        staff.notify_booking = False
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message') as mock_push:
            result = send_staff_line(staff, 'テスト', notification_type='booking')
            assert result is False
            mock_push.assert_not_called()

    def test_shift_notification_type(self, staff):
        """notification_type='shift' → notify_shift を参照"""
        from booking.services.staff_notifications import send_staff_line

        staff.line_id = 'U1234567890'
        staff.notify_shift = True
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            result = send_staff_line(staff, 'テスト', notification_type='shift')
            assert result is True
            mock_push.assert_called_once()

    def test_unknown_notification_type_returns_false(self, staff):
        """不明な通知タイプ → False"""
        from booking.services.staff_notifications import send_staff_line

        staff.line_id = 'U1234567890'
        staff.save()

        result = send_staff_line(staff, 'テスト', notification_type='unknown')
        assert result is False


# ==============================
# notify_booking_to_staff
# ==============================

@pytest.mark.django_db
class TestNotifyBookingToStaff:
    """notify_booking_to_staff: 予約確定通知"""

    def test_sends_booking_details(self, staff):
        """Schedule の日時・顧客名・料金がメッセージに含まれる"""
        from booking.services.staff_notifications import notify_booking_to_staff

        staff.line_id = 'U1234567890'
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
            result = notify_booking_to_staff(schedule)
            assert result is True
            message = mock_push.call_args[0][1]
            assert '予約確定' in message
            assert '山田太郎' in message
            assert '5000' in message

    def test_skips_when_booking_notification_disabled(self, staff):
        """notify_booking=False → 送信されない"""
        from booking.services.staff_notifications import notify_booking_to_staff

        staff.line_id = 'U1234567890'
        staff.notify_booking = False
        staff.save()

        start_dt = timezone.make_aware(dt.datetime(2025, 4, 10, 14, 0))
        end_dt = start_dt + dt.timedelta(hours=1)
        schedule = Schedule.objects.create(
            staff=staff,
            start=start_dt,
            end=end_dt,
            customer_name='テスト',
            price=1000,
        )

        with patch('booking.services.staff_notifications._push_line_message') as mock_push:
            result = notify_booking_to_staff(schedule)
            assert result is False
            mock_push.assert_not_called()

    def test_customer_name_none_shows_default(self, staff):
        """customer_name=None → '未設定' 表示"""
        from booking.services.staff_notifications import notify_booking_to_staff

        staff.line_id = 'U1234567890'
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
            notify_booking_to_staff(schedule)
            message = mock_push.call_args[0][1]
            assert '未設定' in message


# ==============================
# notify_shift_published
# ==============================

@pytest.mark.django_db
class TestNotifyShiftPublished:
    """notify_shift_published: シフト公開時の個別通知"""

    def test_sends_to_each_assigned_staff(self, shift_period, staff):
        """ShiftAssignment のスタッフ全員に通知"""
        from booking.services.staff_notifications import notify_shift_published

        staff.line_id = 'U1234567890'
        staff.notify_shift = True
        staff.save()

        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=dt.date(2025, 4, 10), start_hour=9, end_hour=17,
        )

        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            results = notify_shift_published(shift_period)
            assert results['sent'] == 1
            assert results['skipped'] == 0
            message = mock_push.call_args[0][1]
            assert 'シフト確定' in message

    def test_skips_staff_with_shift_notification_off(self, shift_period, staff):
        """notify_shift=False のスタッフはスキップ"""
        from booking.services.staff_notifications import notify_shift_published

        staff.line_id = 'U1234567890'
        staff.notify_shift = False
        staff.save()

        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=dt.date(2025, 4, 10), start_hour=9, end_hour=17,
        )

        with patch('booking.services.staff_notifications._push_line_message') as mock_push:
            results = notify_shift_published(shift_period)
            assert results['skipped'] == 1
            assert results['sent'] == 0
            mock_push.assert_not_called()

    def test_deduplicates_staff_with_multiple_assignments(self, shift_period, staff):
        """同一スタッフが複数日アサインされても通知は1回"""
        from booking.services.staff_notifications import notify_shift_published

        staff.line_id = 'U1234567890'
        staff.notify_shift = True
        staff.save()

        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=dt.date(2025, 4, 10), start_hour=9, end_hour=17,
        )
        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=dt.date(2025, 4, 11), start_hour=10, end_hour=18,
        )

        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            results = notify_shift_published(shift_period)
            assert results['sent'] == 1
            assert mock_push.call_count == 1


# ==============================
# send_business_message
# ==============================

@pytest.mark.django_db
class TestSendBusinessMessage:
    """send_business_message: 業務連絡一斉送信"""

    def test_sends_to_enabled_staff(self, staff):
        """notify_business=True + LINE ID あり → 送信される"""
        from booking.services.staff_notifications import send_business_message

        staff.line_id = 'U1234567890'
        staff.notify_business = True
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            results = send_business_message(Staff.objects.filter(id=staff.id), '本日休業です')
            assert results['sent'] == 1
            message = mock_push.call_args[0][1]
            assert '業務連絡' in message
            assert '本日休業です' in message

    def test_includes_sender_name(self, staff):
        """sender_name が指定された場合メッセージに含まれる"""
        from booking.services.staff_notifications import send_business_message

        staff.line_id = 'U1234567890'
        staff.notify_business = True
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            send_business_message(Staff.objects.filter(id=staff.id), 'テスト', sender_name='管理者')
            message = mock_push.call_args[0][1]
            assert '管理者' in message

    def test_skips_disabled_and_counts(self, store):
        """通知OFF/LINE ID なし → スキップとしてカウント"""
        from django.contrib.auth import get_user_model
        from booking.services.staff_notifications import send_business_message
        User = get_user_model()

        # notify_business=False
        user1 = User.objects.create_user(username='s1', password='pass')
        staff1 = Staff.objects.create(
            name='スタッフ1', store=store, user=user1,
            line_id='U111', notify_business=False,
        )
        # line_id なし
        user2 = User.objects.create_user(username='s2', password='pass')
        staff2 = Staff.objects.create(
            name='スタッフ2', store=store, user=user2,
            line_id='', notify_business=True,
        )

        with patch('booking.services.staff_notifications._push_line_message') as mock_push:
            results = send_business_message(
                Staff.objects.filter(id__in=[staff1.id, staff2.id]), 'テスト',
            )
            assert results['skipped'] == 2
            assert results['sent'] == 0
            mock_push.assert_not_called()

    def test_counts_failures(self, staff):
        """push失敗 → failed としてカウント"""
        from booking.services.staff_notifications import send_business_message

        staff.line_id = 'U1234567890'
        staff.notify_business = True
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message', return_value=False):
            results = send_business_message(Staff.objects.filter(id=staff.id), 'テスト')
            assert results['failed'] == 1
            assert results['sent'] == 0


# ==============================
# _push_line_message
# ==============================

@pytest.mark.django_db
class TestPushLineMessage:
    """_push_line_message: LineBotApi Push送信"""

    def test_successful_push(self, settings):
        """正常送信"""
        from booking.services.staff_notifications import _push_line_message

        settings.LINE_ACCESS_TOKEN = 'test-token'

        with patch('linebot.LineBotApi') as MockBot:
            mock_api = MagicMock()
            MockBot.return_value = mock_api
            result = _push_line_message('U12345', 'テスト')
            assert result is True
            mock_api.push_message.assert_called_once()

    def test_returns_false_without_token(self, settings):
        """LINE_ACCESS_TOKEN 未設定 → False"""
        from booking.services.staff_notifications import _push_line_message

        settings.LINE_ACCESS_TOKEN = None

        result = _push_line_message('U12345', 'テスト')
        assert result is False

    def test_retries_on_failure(self, settings):
        """例外時にリトライする"""
        from booking.services.staff_notifications import _push_line_message

        settings.LINE_ACCESS_TOKEN = 'test-token'

        with patch('linebot.LineBotApi') as MockBot:
            mock_api = MagicMock()
            mock_api.push_message.side_effect = [Exception('fail'), None]
            MockBot.return_value = mock_api

            with patch('booking.services.staff_notifications.time.sleep'):
                result = _push_line_message('U12345', 'テスト', max_retries=2)
                assert result is True
                assert mock_api.push_message.call_count == 2


# ==============================
# shift_notifications 統合（既存テストとの互換性）
# ==============================

@pytest.mark.django_db
class TestShiftNotificationsIntegration:
    """shift_notifications: 個別Push移行後の動作確認"""

    def test_notify_shift_period_open_uses_individual_push(self, shift_period, staff):
        """notify_shift_period_open が send_staff_line を使う"""
        from booking.services.shift_notifications import notify_shift_period_open

        staff.line_id = 'U1234567890'
        staff.notify_shift = True
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            notify_shift_period_open(shift_period)
            assert mock_push.call_count >= 1
            message = mock_push.call_args[0][1]
            assert 'シフト募集開始' in message

    def test_notify_shift_approved_uses_individual_push(self, shift_period, staff):
        """notify_shift_approved が send_staff_line を使う"""
        from booking.services.shift_notifications import notify_shift_approved

        staff.line_id = 'U1234567890'
        staff.notify_shift = True
        staff.save()

        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            notify_shift_approved(shift_period)
            assert mock_push.call_count >= 1
            message = mock_push.call_args[0][1]
            assert 'シフト確定' in message

    def test_notify_booking_confirmed_delegates(self, staff):
        """notify_booking_confirmed が notify_booking_to_staff に委譲"""
        from booking.services.shift_notifications import notify_booking_confirmed

        staff.line_id = 'U1234567890'
        staff.notify_booking = True
        staff.save()

        start_dt = timezone.make_aware(dt.datetime(2025, 4, 10, 14, 0))
        end_dt = start_dt + dt.timedelta(hours=1)
        schedule = Schedule.objects.create(
            staff=staff, start=start_dt, end=end_dt,
            customer_name='テスト', price=3000,
        )

        with patch('booking.services.staff_notifications._push_line_message', return_value=True) as mock_push:
            notify_booking_confirmed(schedule)
            assert mock_push.call_count == 1
            message = mock_push.call_args[0][1]
            assert '予約確定' in message


# ==============================
# Staff モデル: 通知設定デフォルト値
# ==============================

@pytest.mark.django_db
class TestStaffNotificationDefaults:
    """Staff モデルの通知設定フィールドのデフォルト値"""

    def test_default_values_are_true(self, staff):
        """新規作成時は全通知ONがデフォルト"""
        staff.refresh_from_db()
        assert staff.notify_booking is True
        assert staff.notify_shift is True
        assert staff.notify_business is True
