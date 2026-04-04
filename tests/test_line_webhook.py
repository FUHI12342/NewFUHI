"""
tests/test_line_webhook.py
Tests for booking/views_line_webhook.py:
  - Missing X-Line-Signature -> 403
  - Invalid signature -> 400
  - GET method -> 405
"""
import pytest
from unittest.mock import patch, MagicMock

from django.test import Client
from django.urls import reverse


# ==============================================================
# Webhook endpoint tests
# ==============================================================

@pytest.mark.django_db
class TestLineWebhook:
    def test_webhook_missing_signature(self, api_client, settings):
        """POST without X-Line-Signature returns 403."""
        settings.LINE_CHANNEL_SECRET = 'test-channel-secret'

        url = reverse('line_webhook')
        resp = api_client.post(
            url,
            data='{}',
            content_type='application/json',
        )

        assert resp.status_code == 403

    @patch('booking.views_line_webhook._get_webhook_handler')
    def test_webhook_invalid_signature(self, mock_handler, api_client, settings):
        """POST with wrong signature returns 400."""
        settings.LINE_CHANNEL_SECRET = 'test-channel-secret'

        handler = MagicMock()
        handler.handle.side_effect = Exception('Invalid signature')
        mock_handler.return_value = handler

        url = reverse('line_webhook')
        resp = api_client.post(
            url,
            data='{"events": []}',
            content_type='application/json',
            HTTP_X_LINE_SIGNATURE='invalid-signature',
        )

        assert resp.status_code == 400

    def test_webhook_get_method_not_allowed(self, api_client, settings):
        """GET request to webhook returns 405."""
        settings.LINE_CHANNEL_SECRET = 'test-channel-secret'

        url = reverse('line_webhook')
        resp = api_client.get(url)

        assert resp.status_code == 405
