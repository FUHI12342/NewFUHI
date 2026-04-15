"""
Tests for LINE booking flow: friend/not-friend/blocked scenarios.

Covers:
- LineCallbackView: friend + paid, friend + free, not-friend + paid, not-friend + free
- Blocked user behavior (same as not-friend via 404)
- LINE API error handling (500 from get_profile)
"""
import json
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from booking.models import Store, Staff, Schedule

pytestmark = pytest.mark.django_db

# ==============================
# Constants
# ==============================

FAKE_LINE_USER_ID = 'U1234567890abcdef1234567890abcdef'
FAKE_LINE_USER_NAME = 'テストユーザー'
FAKE_STATE = 'test-state-123'
FAKE_AUTH_CODE = 'fake-auth-code-xyz'
FAKE_ID_TOKEN = 'fake.id.token'
FAKE_PAYMENT_URL = 'https://payge.co/pay/test-payment-url'

LINE_SETTINGS = {
    'LINE_CHANNEL_ID': 'test-channel-id',
    'LINE_CHANNEL_SECRET': 'test-channel-secret',
    'LINE_REDIRECT_URL': 'http://testserver/callback',
    'LINE_ACCESS_TOKEN': 'test-access-token',
    'PAYMENT_API_URL': 'https://example.com/api/payge',
    'PAYMENT_API_KEY': 'test-api-key',
    'COINEY_WEBHOOK_TOKEN': 'test-webhook-token',
    'WEBHOOK_URL_BASE': 'http://testserver/webhook/',
    'CANCEL_URL': 'http://testserver/cancel',
    'SITE_BASE_URL': 'http://testserver',
    'LINE_BOT_ID': 'test-bot-id',
}

CALLBACK_URL_NAME = 'booking:line_success'

# Patch targets for local imports used inside LineCallbackView.get()
PATCH_GEN_QR = 'booking.services.checkin_token.generate_signed_checkin_qr'
PATCH_GEN_BACKUP = 'booking.services.checkin_token.generate_backup_code'
PATCH_NOTIFY_STAFF = 'booking.services.staff_notifications.notify_booking_to_staff'


# ==============================
# Fixtures
# ==============================

@pytest.fixture(autouse=True)
def _apply_line_settings(settings):
    """Apply all LINE-related settings for every test in this module."""
    for key, value in LINE_SETTINGS.items():
        setattr(settings, key, value)


@pytest.fixture(autouse=True)
def _reset_lazy_line_settings():
    """Reset _LazyLineSetting caches so override_settings values are used."""
    from booking.views_booking import (
        _lazy_line_channel_id,
        _lazy_line_channel_secret,
        _lazy_line_redirect_url,
    )
    _lazy_line_channel_id._resolved = False
    _lazy_line_channel_id._value = None
    _lazy_line_channel_secret._resolved = False
    _lazy_line_channel_secret._value = None
    _lazy_line_redirect_url._resolved = False
    _lazy_line_redirect_url._value = None
    yield
    _lazy_line_channel_id._resolved = False
    _lazy_line_channel_id._value = None
    _lazy_line_channel_secret._resolved = False
    _lazy_line_channel_secret._value = None
    _lazy_line_redirect_url._resolved = False
    _lazy_line_redirect_url._value = None


@pytest.fixture
def line_store(db):
    """Create a store for LINE booking tests."""
    return Store.objects.create(
        name="LINEテスト店舗",
        address="東京都新宿区1-1-1",
        business_hours="10:00-22:00",
        nearest_station="新宿駅",
        map_url="https://maps.google.com/test",
    )


@pytest.fixture
def line_staff(line_store):
    """Create a staff member with associated user for LINE booking tests."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.create_user(
        username="line_test_staff",
        password="pass123",
    )
    return Staff.objects.create(
        name="LINEテストスタッフ",
        store=line_store,
        user=user,
    )


@pytest.fixture
def line_client():
    """Return a fresh Django test client."""
    return Client()


# ==============================
# Helpers
# ==============================

def _make_session_data(staff, price=5000):
    """Build session data dict with state and temporary_booking."""
    now = timezone.now()
    return {
        'state': FAKE_STATE,
        'temporary_booking': {
            'reservation_number': 'RES-TEST-001',
            'start': (now + timedelta(hours=24)).replace(tzinfo=None).isoformat(),
            'end': (now + timedelta(hours=25)).replace(tzinfo=None).isoformat(),
            'price': price,
            'staff_id': staff.pk,
            'store_id': staff.store_id,
        },
    }


def _inject_session(client, session_data):
    """Inject session data into the test client's session store."""
    session = client.session
    for key, value in session_data.items():
        session[key] = value
    session.save()


def _make_line_token_response():
    """Create a mock requests.Response for LINE token exchange (200 OK)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps({'id_token': FAKE_ID_TOKEN})
    return mock_resp


def _make_payment_response():
    """Create a mock requests.Response for Coiney payment API (201 Created)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {'links': {'paymentUrl': FAKE_PAYMENT_URL}}
    return mock_resp


def _make_get_profile_friend():
    """Return a MagicMock simulating a successful get_profile call (friend)."""
    profile = MagicMock()
    profile.user_id = FAKE_LINE_USER_ID
    return profile


def _make_line_bot_api_error(status_code, message='Error'):
    """Create an ApiException (v3) with the given status code."""
    from linebot.v3.messaging import ApiException
    return ApiException(status=status_code, reason=message)


def _build_callback_url():
    """Build the GET URL for the LINE callback with code and state params."""
    base = reverse(CALLBACK_URL_NAME)
    return f'{base}?code={FAKE_AUTH_CODE}&state={FAKE_STATE}'


def _make_qr_file():
    """Return a ContentFile that acts like the QR generation output."""
    from django.core.files.base import ContentFile
    # 1x1 white PNG (minimal valid PNG for ImageField)
    minimal_png = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    return ContentFile(minimal_png, name='qr_RES-TEST-001.png')


# ==============================
# Shared mock context manager
# ==============================

def _common_patches(get_profile_side_effect):
    """Return a dict of patch context managers and the mock bot API instance.

    get_profile_side_effect:
        - A callable for friend (lambda uid: profile_mock)
        - A LineBotApiError instance for not-friend/blocked/error
    """
    patches = {}

    # 1. requests.post: LINE token exchange + Coiney payment
    def requests_post_side_effect(url, **kwargs):
        if 'line.me' in url or 'api.line.me' in url:
            return _make_line_token_response()
        return _make_payment_response()

    patches['requests_post'] = patch(
        'booking.views_booking.requests.post',
        side_effect=requests_post_side_effect,
    )

    # 2. jwt.decode
    patches['jwt_decode'] = patch(
        'booking.views_booking.jwt.decode',
        return_value={
            'sub': FAKE_LINE_USER_ID,
            'name': FAKE_LINE_USER_NAME,
        },
    )

    # 3. _make_messaging_api (returns (mock_messaging_api, mock_api_client))
    mock_bot_api = MagicMock()
    mock_bot_api.get_profile.side_effect = get_profile_side_effect
    mock_bot_api.push_message.return_value = None
    mock_api_client = MagicMock()
    patches['line_bot_api_cls'] = patch(
        'booking.views_booking._make_messaging_api',
        return_value=(mock_bot_api, mock_api_client),
    )
    patches['_mock_bot_api'] = mock_bot_api

    return patches


def _free_booking_patches(backup_code='123456'):
    """Return patch context managers for QR generation and staff notification
    that are needed for free (price=0) booking tests."""
    patches = {}

    patches['gen_qr'] = patch(PATCH_GEN_QR, side_effect=lambda *a, **kw: _make_qr_file())
    patches['gen_backup'] = patch(PATCH_GEN_BACKUP, return_value=backup_code)
    patches['notify_staff'] = patch(PATCH_NOTIFY_STAFF)

    return patches


# ==============================
# Test 1: Friend + Paid booking
# ==============================

class TestFriendPaidBooking:
    """When the user is a LINE friend and price >= 100,
    the view sends the payment URL via LINE push_message."""

    def test_push_message_with_payment_url(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        ctx = _common_patches(
            get_profile_side_effect=lambda uid: _make_get_profile_friend(),
        )

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            mock_bot = ctx['_mock_bot_api']
            resp = line_client.get(_build_callback_url())

        assert resp.status_code == 200
        assert 'line_success.html' in resp.templates[0].name

        mock_bot.push_message.assert_called_once()
        call_args = mock_bot.push_message.call_args
        req = call_args[0][0]
        assert req.to == FAKE_LINE_USER_ID
        message_text = req.messages[0].text
        assert FAKE_PAYMENT_URL in message_text
        assert '決済' in message_text

    def test_schedule_created_as_temporary(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        ctx = _common_patches(
            get_profile_side_effect=lambda uid: _make_get_profile_friend(),
        )

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            line_client.get(_build_callback_url())

        schedule = Schedule.objects.get(reservation_number='RES-TEST-001')
        assert schedule.is_temporary is True
        assert schedule.price == 5000
        assert schedule.customer_name == FAKE_LINE_USER_NAME

    def test_session_temporary_booking_cleared(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        ctx = _common_patches(
            get_profile_side_effect=lambda uid: _make_get_profile_friend(),
        )

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            line_client.get(_build_callback_url())

        assert 'temporary_booking' not in line_client.session


# ==============================
# Test 2: Friend + Free booking
# ==============================

class TestFriendFreeBooking:
    """When the user is a LINE friend and price=0,
    the view confirms the schedule and sends reservation info via push_message."""

    def test_push_message_with_reservation_info(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=0)
        _inject_session(line_client, session_data)

        ctx = _common_patches(
            get_profile_side_effect=lambda uid: _make_get_profile_friend(),
        )
        free_ctx = _free_booking_patches()

        with (ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls'],
              free_ctx['gen_qr'], free_ctx['gen_backup'], free_ctx['notify_staff']):
            mock_bot = ctx['_mock_bot_api']
            resp = line_client.get(_build_callback_url())

        assert resp.status_code == 200
        assert 'line_success.html' in resp.templates[0].name

        mock_bot.push_message.assert_called_once()
        call_args = mock_bot.push_message.call_args
        req = call_args[0][0]
        assert req.to == FAKE_LINE_USER_ID
        message_text = req.messages[0].text
        assert '予約確定' in message_text
        assert 'RES-TEST-001' in message_text
        assert '123456' in message_text

    def test_schedule_confirmed_not_temporary(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=0)
        _inject_session(line_client, session_data)

        ctx = _common_patches(
            get_profile_side_effect=lambda uid: _make_get_profile_friend(),
        )
        free_ctx = _free_booking_patches()

        with (ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls'],
              free_ctx['gen_qr'], free_ctx['gen_backup'], free_ctx['notify_staff']):
            line_client.get(_build_callback_url())

        schedule = Schedule.objects.get(reservation_number='RES-TEST-001')
        assert schedule.is_temporary is False
        assert schedule.price == 0

    def test_staff_notification_called(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=0)
        _inject_session(line_client, session_data)

        ctx = _common_patches(
            get_profile_side_effect=lambda uid: _make_get_profile_friend(),
        )
        free_ctx = _free_booking_patches()

        with (ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls'],
              free_ctx['gen_qr'], free_ctx['gen_backup'],
              free_ctx['notify_staff'] as mock_notify):
            line_client.get(_build_callback_url())

        mock_notify.assert_called_once()


# ==============================
# Test 3: Not-friend + Paid booking
# ==============================

class TestNotFriendPaidBooking:
    """When get_profile returns 404 and price >= 100,
    the view renders line_not_friend.html with payment_url."""

    def test_renders_not_friend_page_with_payment_url(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        error_404 = _make_line_bot_api_error(404, 'Not found')
        ctx = _common_patches(get_profile_side_effect=error_404)

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            resp = line_client.get(_build_callback_url())

        assert resp.status_code == 200
        assert 'line_not_friend.html' in resp.templates[0].name
        assert resp.context['payment_url'] == FAKE_PAYMENT_URL

    def test_push_message_not_called(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        error_404 = _make_line_bot_api_error(404, 'Not found')
        ctx = _common_patches(get_profile_side_effect=error_404)

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            mock_bot = ctx['_mock_bot_api']
            line_client.get(_build_callback_url())

        mock_bot.push_message.assert_not_called()

    def test_context_contains_friend_add_url(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        error_404 = _make_line_bot_api_error(404, 'Not found')
        ctx = _common_patches(get_profile_side_effect=error_404)

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            resp = line_client.get(_build_callback_url())

        assert resp.context['friend_add_url'] == 'https://line.me/R/ti/p/@test-bot-id'

    def test_context_contains_reservation_info(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        error_404 = _make_line_bot_api_error(404, 'Not found')
        ctx = _common_patches(get_profile_side_effect=error_404)

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            resp = line_client.get(_build_callback_url())

        assert resp.context['reservation_number'] == 'RES-TEST-001'
        assert resp.context['staff_name'] == 'LINEテストスタッフ'
        assert resp.context['price'] == 5000


# ==============================
# Test 4: Not-friend + Free booking
# ==============================

class TestNotFriendFreeBooking:
    """When get_profile returns 404 and price=0,
    the view renders line_not_friend.html with QR page URL and backup code."""

    def test_renders_not_friend_page_with_qr_and_backup(
        self, line_client, line_staff,
    ):
        session_data = _make_session_data(line_staff, price=0)
        _inject_session(line_client, session_data)

        error_404 = _make_line_bot_api_error(404, 'Not found')
        ctx = _common_patches(get_profile_side_effect=error_404)
        free_ctx = _free_booking_patches()

        with (ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls'],
              free_ctx['gen_qr'], free_ctx['gen_backup'], free_ctx['notify_staff']):
            resp = line_client.get(_build_callback_url())

        assert resp.status_code == 200
        assert 'line_not_friend.html' in resp.templates[0].name
        assert resp.context['backup_code'] == '123456'
        assert resp.context['qr_page_url'] is not None
        assert 'RES-TEST-001' in resp.context['qr_page_url']

    def test_no_payment_url_in_context(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=0)
        _inject_session(line_client, session_data)

        error_404 = _make_line_bot_api_error(404, 'Not found')
        ctx = _common_patches(get_profile_side_effect=error_404)
        free_ctx = _free_booking_patches()

        with (ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls'],
              free_ctx['gen_qr'], free_ctx['gen_backup'], free_ctx['notify_staff']):
            resp = line_client.get(_build_callback_url())

        assert resp.context['payment_url'] is None

    def test_push_message_not_called(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=0)
        _inject_session(line_client, session_data)

        error_404 = _make_line_bot_api_error(404, 'Not found')
        ctx = _common_patches(get_profile_side_effect=error_404)
        free_ctx = _free_booking_patches()

        with (ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls'],
              free_ctx['gen_qr'], free_ctx['gen_backup'], free_ctx['notify_staff']):
            mock_bot = ctx['_mock_bot_api']
            line_client.get(_build_callback_url())

        mock_bot.push_message.assert_not_called()

    def test_schedule_confirmed_not_temporary(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=0)
        _inject_session(line_client, session_data)

        error_404 = _make_line_bot_api_error(404, 'Not found')
        ctx = _common_patches(get_profile_side_effect=error_404)
        free_ctx = _free_booking_patches()

        with (ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls'],
              free_ctx['gen_qr'], free_ctx['gen_backup'], free_ctx['notify_staff']):
            line_client.get(_build_callback_url())

        schedule = Schedule.objects.get(reservation_number='RES-TEST-001')
        assert schedule.is_temporary is False

    def test_cancel_token_in_context(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=0)
        _inject_session(line_client, session_data)

        error_404 = _make_line_bot_api_error(404, 'Not found')
        ctx = _common_patches(get_profile_side_effect=error_404)
        free_ctx = _free_booking_patches()

        with (ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls'],
              free_ctx['gen_qr'], free_ctx['gen_backup'], free_ctx['notify_staff']):
            resp = line_client.get(_build_callback_url())

        assert resp.context['cancel_token'] is not None


# ==============================
# Test 5: Blocked user (same as not-friend, 404 from get_profile)
# ==============================

class TestBlockedUserBooking:
    """Blocked users produce the same 404 from get_profile as unfollowed users.
    Verify behavior is identical to not-friend for both paid and free."""

    def test_blocked_paid_renders_not_friend_page(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=3000)
        _inject_session(line_client, session_data)

        error_404 = _make_line_bot_api_error(404, 'Not found')
        ctx = _common_patches(get_profile_side_effect=error_404)

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            mock_bot = ctx['_mock_bot_api']
            resp = line_client.get(_build_callback_url())

        assert resp.status_code == 200
        assert 'line_not_friend.html' in resp.templates[0].name
        assert resp.context['payment_url'] == FAKE_PAYMENT_URL
        mock_bot.push_message.assert_not_called()

    def test_blocked_free_renders_not_friend_page(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=0)
        _inject_session(line_client, session_data)

        error_404 = _make_line_bot_api_error(404, 'Not found')
        ctx = _common_patches(get_profile_side_effect=error_404)
        free_ctx = _free_booking_patches()

        with (ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls'],
              free_ctx['gen_qr'], free_ctx['gen_backup'], free_ctx['notify_staff']):
            mock_bot = ctx['_mock_bot_api']
            resp = line_client.get(_build_callback_url())

        assert resp.status_code == 200
        assert 'line_not_friend.html' in resp.templates[0].name
        assert resp.context['backup_code'] == '123456'
        mock_bot.push_message.assert_not_called()


# ==============================
# Test 6: get_profile returns 500
# ==============================

class TestGetProfileServerError:
    """When get_profile raises LineBotApiError with status_code != 404,
    the view returns HttpResponseBadRequest."""

    def test_returns_400_on_server_error(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        error_500 = _make_line_bot_api_error(500, 'Internal Server Error')
        ctx = _common_patches(get_profile_side_effect=error_500)

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            resp = line_client.get(_build_callback_url())

        assert resp.status_code == 400

    def test_no_schedule_created_on_error(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        error_500 = _make_line_bot_api_error(500, 'Internal Server Error')
        ctx = _common_patches(get_profile_side_effect=error_500)

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            line_client.get(_build_callback_url())

        assert not Schedule.objects.filter(reservation_number='RES-TEST-001').exists()

    def test_push_message_not_called_on_error(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        error_500 = _make_line_bot_api_error(500, 'Internal Server Error')
        ctx = _common_patches(get_profile_side_effect=error_500)

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            mock_bot = ctx['_mock_bot_api']
            line_client.get(_build_callback_url())

        mock_bot.push_message.assert_not_called()


# ==============================
# Edge case: state mismatch
# ==============================

class TestStateValidation:
    """Verify that mismatched or missing state returns 400."""

    def test_state_mismatch_returns_400(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        url = reverse(CALLBACK_URL_NAME) + '?code=fake-code&state=wrong-state'
        resp = line_client.get(url)
        assert resp.status_code == 400

    def test_missing_code_returns_error(self, line_client, line_staff):
        session_data = _make_session_data(line_staff, price=5000)
        _inject_session(line_client, session_data)

        url = reverse(CALLBACK_URL_NAME) + f'?state={FAKE_STATE}'
        resp = line_client.get(url)
        assert resp.status_code == 200
        assert 'トークンの取得に失敗しました' in resp.content.decode()


# ==============================
# Edge case: missing temporary_booking
# ==============================

class TestMissingTemporaryBooking:
    """Verify that missing temporary_booking in session returns an error."""

    def test_no_temporary_booking_returns_error(self, line_client):
        _inject_session(line_client, {'state': FAKE_STATE})

        ctx = _common_patches(
            get_profile_side_effect=lambda uid: _make_get_profile_friend(),
        )

        with ctx['requests_post'], ctx['jwt_decode'], ctx['line_bot_api_cls']:
            resp = line_client.get(_build_callback_url())

        assert resp.status_code == 200
        assert '仮予約情報がありません' in resp.content.decode()
