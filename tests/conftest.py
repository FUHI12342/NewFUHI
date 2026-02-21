"""
pytest conftest.py - Test environment setup for FUHI Django project.

Provides common fixtures for Store, Staff, IoTDevice, and API client.
"""
import os
import pytest
import hashlib

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings.local')

import django
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from booking.models import Store, Staff, IoTDevice

User = get_user_model()


@pytest.fixture
def store(db):
    """Create and return a test Store instance."""
    return Store.objects.create(
        name="テスト店舗",
        address="東京都新宿区",
        business_hours="9:00-17:00",
        nearest_station="新宿駅",
    )


@pytest.fixture
def staff(db, store):
    """Create and return a test Staff instance with an associated User."""
    user = User.objects.create_user(
        username="teststaff",
        password="testpass123",
    )
    return Staff.objects.create(
        name="テストスタッフ",
        store=store,
        user=user,
    )


@pytest.fixture
def iot_device(db, store):
    """Create and return a test IoTDevice with a known API key hash."""
    raw_api_key = "test-api-key-12345"
    api_key_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()
    return IoTDevice.objects.create(
        name="テストデバイス",
        store=store,
        device_type="multi",
        external_id="test-device-001",
        api_key_hash=api_key_hash,
        api_key_prefix=raw_api_key[:8],
    )


@pytest.fixture
def api_client():
    """Return a Django test Client instance."""
    return Client()
