"""
tests/test_cancel_flow.py
Tests for:
  - Schedule.cancel_token auto-generation
  - Public customer cancel flow (CustomerCancelView, CustomerCancelConfirmView)
  - LINE non-friend fallback (LineCallbackView)
  - bot_prompt=aggressive in LINE OAuth URL
"""
import re
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, PropertyMock

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from booking.models import Schedule, Store, Staff


def _make_line_bot_api_error(status_code=404):
    """Create an ApiException (v3) with the given status code."""
    from linebot.v3.messaging import ApiException
    return ApiException(status=status_code, reason='not found')


# ==============================================================
# Fixtures
# ==============================================================

@pytest.fixture
def schedule(db, staff):
    """Create a confirmed (non-temporary) schedule."""
    now = timezone.now()
    return Schedule.objects.create(
        start=now + timedelta(hours=24),
        end=now + timedelta(hours=25),
        staff=staff,
        customer_name='テスト顧客',
        price=5000,
        is_temporary=False,
    )


@pytest.fixture
def free_schedule(db, staff):
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


# ==============================================================
# cancel_token model tests
# ==============================================================

@pytest.mark.django_db
class TestCancelToken:
    def test_cancel_token_auto_generated_on_save(self, schedule):
        """cancel_token は Schedule 保存時に自動生成される。"""
        assert schedule.cancel_token is not None
        assert len(schedule.cancel_token) == 8

    def test_cancel_token_is_uppercase_alphanumeric(self, schedule):
        """cancel_token は英大文字+数字のみ。"""
        assert re.match(r'^[A-Z0-9]{8}$', schedule.cancel_token)

    def test_cancel_token_is_unique(self, staff):
        """異なるScheduleには異なるcancel_tokenが付与される。"""
        now = timezone.now()
        schedules = []
        for i in range(10):
            s = Schedule.objects.create(
                start=now + timedelta(hours=i + 1),
                end=now + timedelta(hours=i + 2),
                staff=staff,
                customer_name=f'顧客{i}',
                price=0,
                is_temporary=False,
            )
            schedules.append(s)
        tokens = [s.cancel_token for s in schedules]
        assert len(tokens) == len(set(tokens)), "cancel_token に重複がある"

    def test_cancel_token_not_overwritten_on_update(self, schedule):
        """既存の cancel_token は save() で上書きされない。"""
        original_token = schedule.cancel_token
        schedule.customer_name = '変更後名前'
        schedule.save()
        schedule.refresh_from_db()
        assert schedule.cancel_token == original_token


# ==============================================================
# CustomerCancelView tests
# ==============================================================

@pytest.mark.django_db
class TestCustomerCancelView:
    def test_get_shows_form(self, api_client, schedule):
        url = reverse('booking:customer_cancel', args=[schedule.reservation_number])
        resp = api_client.get(url)
        assert resp.status_code == 200
        template_names = [t.name for t in resp.templates]
        assert any('customer_cancel_form' in n for n in template_names)

    def test_get_cancelled_schedule_shows_error(self, api_client, schedule):
        Schedule.objects.filter(pk=schedule.pk).update(is_cancelled=True)
        url = reverse('booking:customer_cancel', args=[schedule.reservation_number])
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert 'キャンセル済み' in resp.content.decode()

    def test_post_wrong_token_shows_error(self, api_client, schedule):
        url = reverse('booking:customer_cancel', args=[schedule.reservation_number])
        resp = api_client.post(url, {'cancel_token': 'WRONGTKN'})
        assert resp.status_code == 200
        assert '正しくありません' in resp.content.decode()

    def test_post_correct_token_shows_confirm(self, api_client, schedule):
        url = reverse('booking:customer_cancel', args=[schedule.reservation_number])
        resp = api_client.post(url, {'cancel_token': schedule.cancel_token})
        assert resp.status_code == 200
        template_names = [t.name for t in resp.templates]
        assert any('customer_cancel_confirm' in n for n in template_names)

    def test_post_case_insensitive_token(self, api_client, schedule):
        """小文字で入力しても大文字に正規化されてマッチする。"""
        url = reverse('booking:customer_cancel', args=[schedule.reservation_number])
        resp = api_client.post(url, {'cancel_token': schedule.cancel_token.lower()})
        assert resp.status_code == 200
        template_names = [t.name for t in resp.templates]
        assert any('customer_cancel_confirm' in n for n in template_names)


# ==============================================================
# CustomerCancelConfirmView tests
# ==============================================================

@pytest.mark.django_db
class TestCustomerCancelConfirmView:
    @patch('booking.views_booking._make_messaging_api')
    @patch('booking.views_booking.send_mail')
    def test_cancel_success(self, mock_mail, mock_line_cls, api_client, schedule, settings):
        settings.SITE_BASE_URL = 'http://testserver'
        settings.LINE_ACCESS_TOKEN = 'test-token'
        settings.DEFAULT_FROM_EMAIL = 'test@example.com'
        mock_line_cls.return_value = (MagicMock(), MagicMock())

        url = reverse('booking:customer_cancel_confirm', args=[schedule.reservation_number])
        resp = api_client.post(url, {'cancel_token': schedule.cancel_token})
        assert resp.status_code == 200
        template_names = [t.name for t in resp.templates]
        assert any('customer_cancel_done' in n for n in template_names)

        schedule.refresh_from_db()
        assert schedule.is_cancelled is True

    @patch('booking.views_booking._make_messaging_api')
    @patch('booking.views_booking.send_mail')
    def test_cancel_wrong_token_rejected(self, mock_mail, mock_line_cls, api_client, schedule, settings):
        settings.LINE_ACCESS_TOKEN = 'test-token'
        mock_line_cls.return_value = (MagicMock(), MagicMock())
        url = reverse('booking:customer_cancel_confirm', args=[schedule.reservation_number])
        resp = api_client.post(url, {'cancel_token': 'WRONGTKN'})
        assert resp.status_code == 200
        assert '正しくありません' in resp.content.decode()

        schedule.refresh_from_db()
        assert schedule.is_cancelled is False

    @patch('booking.views_booking._make_messaging_api')
    @patch('booking.views_booking.send_mail')
    def test_cancel_already_cancelled(self, mock_mail, mock_line_cls, api_client, schedule, settings):
        settings.LINE_ACCESS_TOKEN = 'test-token'
        mock_line_cls.return_value = (MagicMock(), MagicMock())
        Schedule.objects.filter(pk=schedule.pk).update(is_cancelled=True)
        url = reverse('booking:customer_cancel_confirm', args=[schedule.reservation_number])
        resp = api_client.post(url, {'cancel_token': schedule.cancel_token})
        assert resp.status_code == 200
        template_names = [t.name for t in resp.templates]
        assert any('customer_cancel_done' in n for n in template_names)

    @patch('booking.views_booking._make_messaging_api')
    @patch('booking.views_booking.send_mail')
    def test_cancel_sends_line_notification(self, mock_mail, mock_line_cls, api_client, schedule, settings):
        settings.LINE_ACCESS_TOKEN = 'test-token'
        settings.DEFAULT_FROM_EMAIL = 'test@example.com'
        settings.SITE_BASE_URL = 'http://testserver'
        mock_api = MagicMock()
        mock_line_cls.return_value = (mock_api, MagicMock())

        # Store LINE user id for customer notification
        schedule.set_line_user_id('U1234567890abcdef')
        schedule.save(update_fields=['line_user_hash', 'line_user_enc'])
        # Set staff LINE id for staff notification
        schedule.staff.line_id = 'staff_line_id'
        schedule.staff.save()

        url = reverse('booking:customer_cancel_confirm', args=[schedule.reservation_number])
        api_client.post(url, {'cancel_token': schedule.cancel_token})

        # LINE push called (customer + staff)
        assert mock_api.push_message.call_count >= 1

    @patch('booking.views_booking._make_messaging_api')
    @patch('booking.views_booking.send_mail')
    def test_cancel_sends_admin_email(self, mock_mail, mock_line_cls, api_client, schedule, settings):
        settings.LINE_ACCESS_TOKEN = 'test-token'
        settings.DEFAULT_FROM_EMAIL = 'admin@test.com'
        settings.NOTIFICATION_EMAILS = ['admin@test.com']
        settings.SITE_BASE_URL = 'http://testserver'
        mock_line_cls.return_value = (MagicMock(), MagicMock())

        url = reverse('booking:customer_cancel_confirm', args=[schedule.reservation_number])
        api_client.post(url, {'cancel_token': schedule.cancel_token})

        assert mock_mail.called
        call_args = mock_mail.call_args
        subject = call_args[1].get('subject', '') if call_args[1] else (call_args[0][0] if call_args[0] else '')
        assert '要対応' in subject


# ==============================================================
# bot_prompt=aggressive test
# ==============================================================

@pytest.mark.django_db
class TestLineEnterBotPrompt:
    def test_oauth_url_contains_bot_prompt(self, api_client, settings):
        settings.LINE_CHANNEL_ID = 'test-channel-id'
        settings.LINE_CHANNEL_SECRET = 'test-secret'
        settings.LINE_REDIRECT_URL = 'http://testserver/callback'

        url = reverse('booking:line_enter')
        resp = api_client.get(url)
        assert resp.status_code == 302
        redirect_url = resp.url
        assert 'bot_prompt=aggressive' in redirect_url


# ==============================================================
# LINE non-friend fallback tests
# ==============================================================

@pytest.mark.django_db
class TestLineNotFriendFallback:
    """LineCallbackView: 非友達ユーザーの予約フロー"""

    def _setup_session(self, client, staff, price=0):
        """仮予約セッションを設定。"""
        now = timezone.now()
        session = client.session
        session['state'] = 'test-state'
        session['temporary_booking'] = {
            'reservation_number': 'test-res-001',
            'start': (now + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S'),
            'end': (now + timedelta(hours=25)).strftime('%Y-%m-%dT%H:%M:%S'),
            'price': price,
            'staff_id': staff.pk,
        }
        session.save()

    def _mock_token_exchange(self, mock_requests_post, extra_posts=None):
        """requests.post のモック（LINE token exchange + optional extra calls）。"""
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.text = '{"id_token": "dummy"}'
        if extra_posts:
            mock_requests_post.side_effect = [token_resp] + extra_posts
        else:
            mock_requests_post.return_value = token_resp

    @patch('booking.views_booking.requests.post')
    @patch('booking.views_booking._make_messaging_api')
    @patch('booking.views_booking.jwt.decode')
    def test_non_friend_free_booking_renders_web_page(
        self, mock_jwt, mock_line_cls, mock_requests_post, api_client, staff, settings
    ):
        settings.LINE_CHANNEL_ID = 'test-channel-id'
        settings.LINE_CHANNEL_SECRET = 'test-secret'
        settings.LINE_REDIRECT_URL = 'http://testserver/callback'
        settings.LINE_ACCESS_TOKEN = 'test-token'
        settings.SITE_BASE_URL = 'http://testserver'
        settings.LINE_BOT_ID = 'test_bot'

        mock_jwt.return_value = {'sub': 'U_not_friend_001', 'name': 'テスト太郎'}
        mock_api = MagicMock()
        mock_line_cls.return_value = (mock_api, MagicMock())
        mock_api.get_profile.side_effect = _make_line_bot_api_error(404)

        self._mock_token_exchange(mock_requests_post)

        with patch('booking.services.checkin_token.generate_signed_checkin_qr') as mock_qr, \
             patch('booking.services.checkin_token.generate_backup_code', return_value='123456'), \
             patch('booking.services.staff_notifications.notify_booking_to_staff'):
            mock_qr.return_value = MagicMock(name='qr.png')

            self._setup_session(api_client, staff, price=0)

            url = reverse('booking:line_success') + '?code=test-code&state=test-state'
            resp = api_client.get(url)

            assert resp.status_code == 200
            template_names = [t.name for t in resp.templates]
            assert any('line_not_friend' in n for n in template_names)
            mock_api.push_message.assert_not_called()

    @patch('booking.views_booking.requests.post')
    @patch('booking.views_booking._make_messaging_api')
    @patch('booking.views_booking.jwt.decode')
    def test_non_friend_paid_booking_shows_payment_url(
        self, mock_jwt, mock_line_cls, mock_requests_post, api_client, staff, settings
    ):
        settings.LINE_CHANNEL_ID = 'test-channel-id'
        settings.LINE_CHANNEL_SECRET = 'test-secret'
        settings.LINE_REDIRECT_URL = 'http://testserver/callback'
        settings.LINE_ACCESS_TOKEN = 'test-token'
        settings.SITE_BASE_URL = 'http://testserver'
        settings.LINE_BOT_ID = 'test_bot'
        settings.PAYMENT_API_URL = 'https://api.coiney.example/v1/payges'
        settings.PAYMENT_API_KEY = 'test-key'
        settings.COINEY_WEBHOOK_TOKEN = 'test-webhook-token'
        settings.WEBHOOK_URL_BASE = 'http://testserver/webhook/'
        settings.CANCEL_URL = 'http://testserver/cancel'

        mock_jwt.return_value = {'sub': 'U_not_friend_002', 'name': 'テスト花子'}
        mock_api = MagicMock()
        mock_line_cls.return_value = (mock_api, MagicMock())
        mock_api.get_profile.side_effect = _make_line_bot_api_error(404)

        coiney_resp = MagicMock()
        coiney_resp.status_code = 201
        coiney_resp.json.return_value = {'links': {'paymentUrl': 'https://pay.example.com/abc'}}
        self._mock_token_exchange(mock_requests_post, extra_posts=[coiney_resp])

        self._setup_session(api_client, staff, price=5000)

        url = reverse('booking:line_success') + '?code=test-code&state=test-state'
        resp = api_client.get(url)

        assert resp.status_code == 200
        template_names = [t.name for t in resp.templates]
        assert any('line_not_friend' in n for n in template_names)
        content = resp.content.decode()
        assert 'https://pay.example.com/abc' in content

    @patch('booking.views_booking.requests.post')
    @patch('booking.views_booking._make_messaging_api')
    @patch('booking.views_booking.jwt.decode')
    def test_friend_booking_uses_push_message(
        self, mock_jwt, mock_line_cls, mock_requests_post, api_client, staff, settings
    ):
        settings.LINE_CHANNEL_ID = 'test-channel-id'
        settings.LINE_CHANNEL_SECRET = 'test-secret'
        settings.LINE_REDIRECT_URL = 'http://testserver/callback'
        settings.LINE_ACCESS_TOKEN = 'test-token'
        settings.SITE_BASE_URL = 'http://testserver'

        mock_jwt.return_value = {'sub': 'U_friend_001', 'name': 'テスト友達'}
        mock_api = MagicMock()
        mock_line_cls.return_value = (mock_api, MagicMock())
        mock_profile = MagicMock()
        mock_profile.user_id = 'U_friend_001'
        mock_api.get_profile.return_value = mock_profile

        self._mock_token_exchange(mock_requests_post)

        with patch('booking.services.checkin_token.generate_signed_checkin_qr') as mock_qr, \
             patch('booking.services.checkin_token.generate_backup_code', return_value='654321'), \
             patch('booking.services.staff_notifications.notify_booking_to_staff'):
            mock_qr.return_value = MagicMock(name='qr.png')

            self._setup_session(api_client, staff, price=0)

            url = reverse('booking:line_success') + '?code=test-code&state=test-state'
            resp = api_client.get(url)

            assert resp.status_code == 200
            template_names = [t.name for t in resp.templates]
            assert any('line_success' in n for n in template_names)
            mock_api.push_message.assert_called()
