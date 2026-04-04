"""
tests/test_line_bot_service.py
Tests for booking/services/line_bot_service.py:
  - push_text (success, retry on failure)
  - reply_text (success)
  - push_flex (success)
  - get_customer_or_create (new / existing)
  - _log_message (LineMessageLog record creation)
"""
import pytest
from unittest.mock import patch, MagicMock

from booking.models import Schedule, Store
from booking.models.line_customer import LineCustomer, LineMessageLog


# ==============================================================
# Helpers
# ==============================================================

def _make_encrypted_user(store=None, line_user_id='U_test_user_001', display_name=''):
    """Create a LineCustomer with properly encrypted fields."""
    from booking.services.line_bot_service import get_customer_or_create
    customer, _ = get_customer_or_create(line_user_id, display_name=display_name, store=store)
    return customer


# ==============================================================
# push_text
# ==============================================================

@pytest.mark.django_db
class TestPushText:
    @patch('booking.services.line_bot_service._get_bot_api')
    def test_push_text_success(self, mock_get_bot, store):
        """push_text sends message and creates a sent log."""
        mock_bot = MagicMock()
        mock_get_bot.return_value = mock_bot

        customer = _make_encrypted_user(store)
        from booking.services.line_bot_service import push_text

        result = push_text(
            customer.line_user_enc, 'Hello',
            message_type='system', customer=customer,
        )

        assert result is True
        mock_bot.push_message.assert_called_once()
        log = LineMessageLog.objects.filter(customer=customer).first()
        assert log is not None
        assert log.status == 'sent'
        assert log.message_type == 'system'

    @patch('booking.services.line_bot_service.time.sleep')
    @patch('booking.services.line_bot_service._get_bot_api')
    def test_push_text_failure_retry(self, mock_get_bot, mock_sleep, store):
        """push_text retries on failure and logs status='failed'."""
        mock_bot = MagicMock()
        mock_bot.push_message.side_effect = Exception('API error')
        mock_get_bot.return_value = mock_bot

        customer = _make_encrypted_user(store)
        from booking.services.line_bot_service import push_text

        result = push_text(
            customer.line_user_enc, 'Hello',
            message_type='system', customer=customer, max_retries=3,
        )

        assert result is False
        assert mock_bot.push_message.call_count == 3
        log = LineMessageLog.objects.filter(customer=customer, status='failed').first()
        assert log is not None
        assert 'Max retries' in log.error_detail


# ==============================================================
# reply_text
# ==============================================================

@pytest.mark.django_db
class TestReplyText:
    @patch('booking.services.line_bot_service._get_bot_api')
    def test_reply_text_success(self, mock_get_bot):
        """reply_text calls reply_message and returns True."""
        mock_bot = MagicMock()
        mock_get_bot.return_value = mock_bot

        from booking.services.line_bot_service import reply_text

        result = reply_text('reply-token-abc', 'Thank you')

        assert result is True
        mock_bot.reply_message.assert_called_once()
        args = mock_bot.reply_message.call_args
        assert args[0][0] == 'reply-token-abc'


# ==============================================================
# push_flex
# ==============================================================

@pytest.mark.django_db
class TestPushFlex:
    @patch('booking.services.line_bot_service._get_bot_api')
    def test_push_flex_success(self, mock_get_bot, store):
        """push_flex sends FlexSendMessage and creates a log."""
        mock_bot = MagicMock()
        mock_get_bot.return_value = mock_bot

        customer = _make_encrypted_user(store)
        flex_container = {'type': 'bubble', 'body': {'type': 'box'}}
        from booking.services.line_bot_service import push_flex

        result = push_flex(
            customer.line_user_enc, 'Flex alt text', flex_container,
            message_type='system', customer=customer,
        )

        assert result is True
        mock_bot.push_message.assert_called_once()
        log = LineMessageLog.objects.filter(customer=customer).first()
        assert log is not None
        assert log.status == 'sent'


# ==============================================================
# get_customer_or_create
# ==============================================================

@pytest.mark.django_db
class TestGetCustomerOrCreate:
    def test_creates_new_customer(self, store):
        """Creates a new LineCustomer when none exists."""
        from booking.services.line_bot_service import get_customer_or_create

        customer, created = get_customer_or_create(
            'U_brand_new_user', display_name='New User', store=store,
        )

        assert created is True
        assert customer.display_name == 'New User'
        assert customer.line_user_hash
        assert customer.line_user_enc
        assert customer.store == store

    def test_returns_existing_and_updates_display_name(self, store):
        """Returns existing LineCustomer and updates display_name."""
        from booking.services.line_bot_service import get_customer_or_create

        customer1, created1 = get_customer_or_create(
            'U_existing_user', display_name='Old Name', store=store,
        )
        assert created1 is True

        customer2, created2 = get_customer_or_create(
            'U_existing_user', display_name='New Name', store=store,
        )
        assert created2 is False
        assert customer2.pk == customer1.pk
        assert customer2.display_name == 'New Name'


# ==============================================================
# _log_message
# ==============================================================

@pytest.mark.django_db
class TestLogMessage:
    def test_log_message_created(self, store):
        """_log_message creates a LineMessageLog record."""
        from booking.services.line_bot_service import _log_message

        customer = _make_encrypted_user(store, display_name='Logger')
        _log_message(customer, 'reminder', 'Test content preview')

        log = LineMessageLog.objects.filter(customer=customer).first()
        assert log is not None
        assert log.message_type == 'reminder'
        assert log.content_preview == 'Test content preview'
        assert log.status == 'sent'
