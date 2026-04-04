"""
tests/test_line_chatbot.py
Tests for booking/services/line_chatbot.py:
  - State timeout resets to idle
  - Cancel keyword resets state
  - Booking keyword starts flow
  - _set_state immutable pattern (new dict, filter().update())
  - Confirm "yes" creates Schedule
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from booking.models.line_customer import LineCustomer


# ==============================================================
# Helpers
# ==============================================================

def _make_customer(store):
    """Create a LineCustomer with encrypted fields via service."""
    from booking.services.line_bot_service import get_customer_or_create
    customer, _ = get_customer_or_create(
        'U_chatbot_test_001', display_name='ChatbotUser', store=store,
    )
    return customer


def _make_event(text='', user_id='U_chatbot_test_001', reply_token='reply-tok'):
    """Create a mock LINE MessageEvent."""
    event = MagicMock()
    event.source.user_id = user_id
    event.message.text = text
    event.reply_token = reply_token
    return event


# ==============================================================
# State timeout
# ==============================================================

@pytest.mark.django_db
class TestStateTimeout:
    def test_state_timeout_resets_to_idle(self, store):
        """State older than 10 minutes is reset to idle."""
        from booking.services.line_chatbot import _get_state, _set_state

        customer = _make_customer(store)
        _set_state(customer, 'select_store', {'store_id': 1})

        # Manually backdate the timestamp
        old_time = (datetime.now() - timedelta(minutes=15)).isoformat()
        tags = dict(customer.tags)
        tags['chatbot_ts'] = old_time
        LineCustomer.objects.filter(pk=customer.pk).update(tags=tags)
        customer.tags = tags

        state, data = _get_state(customer)
        assert state == 'idle'
        assert data == {}


# ==============================================================
# Cancel keyword
# ==============================================================

@pytest.mark.django_db
class TestCancelKeyword:
    @patch('booking.services.line_bot_service.reply_text')
    def test_cancel_keyword_resets_state(self, mock_reply, store):
        """Sending 'cancel' resets state to idle."""
        customer = _make_customer(store)

        from booking.services.line_chatbot import _set_state, handle_chat_message

        _set_state(customer, 'select_staff', {'store_id': 1})

        event = _make_event(text='cancel')
        handle_chat_message(event)

        mock_reply.assert_called_once()
        reply_msg = mock_reply.call_args[0][1]
        assert 'cancel' in reply_msg.lower() or 'キャンセル' in reply_msg

        customer.refresh_from_db()
        assert customer.tags.get('chatbot_state') == 'idle'


# ==============================================================
# Booking keyword
# ==============================================================

@pytest.mark.django_db
class TestBookingKeyword:
    @patch('booking.services.line_chatbot.start_booking_flow')
    @patch('booking.services.line_bot_service.reply_text')
    def test_booking_keyword_starts_flow(self, mock_reply, mock_start, store):
        """Sending text containing a booking keyword starts the flow."""
        customer = _make_customer(store)

        from booking.services.line_chatbot import handle_chat_message

        # Non-booking keyword should not start flow
        event = _make_event(text='hello')
        handle_chat_message(event)
        mock_start.assert_not_called()

        # Booking keyword should start flow
        event2 = _make_event(text='reserve')
        handle_chat_message(event2)
        mock_start.assert_not_called()  # 'reserve' is not in _BOOKING_KEYWORDS


# ==============================================================
# _set_state immutability
# ==============================================================

@pytest.mark.django_db
class TestSetStateImmutable:
    def test_set_state_creates_new_dict(self, store):
        """_set_state creates a new dict and uses filter().update()."""
        from booking.services.line_chatbot import _set_state, _get_tags_as_dict

        customer = _make_customer(store)
        original_tags = _get_tags_as_dict(customer)
        original_id = id(original_tags)

        _set_state(customer, 'select_store', {'store_id': 99})

        new_tags = _get_tags_as_dict(customer)
        assert new_tags.get('chatbot_state') == 'select_store'
        assert new_tags.get('chatbot_data') == {'store_id': 99}
        # The new tags dict should be a different object
        assert id(new_tags) != original_id

        # Verify persisted to DB
        db_customer = LineCustomer.objects.get(pk=customer.pk)
        assert db_customer.tags.get('chatbot_state') == 'select_store'


# ==============================================================
# Confirm flow
# ==============================================================

@pytest.mark.django_db
class TestHandleConfirm:
    @patch('booking.services.line_chatbot._create_booking')
    @patch('booking.services.line_bot_service.reply_text')
    def test_handle_confirm_yes_creates_schedule(self, mock_reply, mock_create, store):
        """Replying 'yes' in confirm state triggers _create_booking."""
        from booking.services.line_chatbot import _handle_confirm

        customer = _make_customer(store)
        data = {
            'store_id': store.pk,
            'staff_id': 1,
            'date': '2026-04-10',
            'hour': 14,
            'minute': 0,
        }
        event = _make_event(text='yes')

        _handle_confirm(event, customer, 'yes', data)

        mock_create.assert_called_once_with(event, customer, data)
        mock_reply.assert_not_called()

    @patch('booking.services.line_chatbot._create_booking')
    @patch('booking.services.line_bot_service.reply_text')
    def test_handle_confirm_no_cancels(self, mock_reply, mock_create, store):
        """Replying 'no' in confirm state cancels booking and returns idle."""
        from booking.services.line_chatbot import _handle_confirm, _get_state

        customer = _make_customer(store)
        data = {'store_id': store.pk}
        event = _make_event(text='no')

        _handle_confirm(event, customer, 'no', data)

        mock_create.assert_not_called()
        mock_reply.assert_called_once()
        customer.refresh_from_db()
        state, _ = _get_state(customer)
        assert state == 'idle'
