"""
IoT Integration Tests — Django TestCase

Validates:
  - IoTEventAPIView (POST /api/iot/events/)
  - IoTConfigAPIView (GET /api/iot/config/)
  - SensorDataAPIView (GET /api/iot/sensors/data/)
  - PIREventsAPIView (GET /api/iot/sensors/pir-events/)
"""
import hashlib
import json

import pytest
from django.test import TestCase
from booking.models import Store, IoTDevice, IoTEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RAW_API_KEY = "test-api-key-123"
DEVICE_EXTERNAL_ID = "Ace1"


def _create_store():
    """Create a Store for test fixtures."""
    return Store.objects.create(
        name="Test Store",
        address="Tokyo, Koenji",
        business_hours="10:00-22:00",
        nearest_station="Koenji",
        regular_holiday="None",
    )


def _create_device(store, raw_key=RAW_API_KEY, external_id=DEVICE_EXTERNAL_ID):
    """Create an IoTDevice with hashed API key."""
    api_key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return IoTDevice.objects.create(
        name="Pico Sensor Node",
        store=store,
        external_id=external_id,
        api_key_hash=api_key_hash,
        api_key_prefix=raw_key[:8],
        is_active=True,
        mq9_threshold=500,
        alert_enabled=False,
    )


def _sensor_payload(mq9=123.4, light=456.7, sound=78.9, pir=True):
    """Standard sensor POST body matching the IoTEventAPIView expected format."""
    return {
        "device": DEVICE_EXTERNAL_ID,
        "event_type": "sensor_reading",
        "payload": {
            "mq9": mq9,
            "light": light,
            "sound": sound,
            "pir": pir,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIoTEventAPI(TestCase):

    def setUp(self):
        self.store = _create_store()
        self.device = _create_device(self.store)

    def test_iot_event_post_success(self):
        """POST sensor data with valid API key returns 201."""
        response = self.client.post(
            "/api/iot/events/",
            data=json.dumps(_sensor_payload()),
            content_type="application/json",
            HTTP_X_API_KEY=RAW_API_KEY,
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["device"], DEVICE_EXTERNAL_ID)
        self.assertEqual(body["event_type"], "sensor_reading")
        self.assertIn("id", body)

    def test_iot_event_invalid_api_key(self):
        """POST with wrong API key returns 404 (device not found by hash mismatch)."""
        response = self.client.post(
            "/api/iot/events/",
            data=json.dumps(_sensor_payload()),
            content_type="application/json",
            HTTP_X_API_KEY="wrong-api-key-999",
        )
        self.assertEqual(response.status_code, 404)

    def test_sensor_data_saved(self):
        """POST sensor data persists correct mq9/light/sound/pir values in IoTEvent."""
        payload = _sensor_payload(mq9=200.5, light=300.0, sound=45.2, pir=False)
        response = self.client.post(
            "/api/iot/events/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_API_KEY=RAW_API_KEY,
        )
        self.assertEqual(response.status_code, 201)

        event = IoTEvent.objects.latest("id")
        self.assertAlmostEqual(event.mq9_value, 200.5)
        self.assertAlmostEqual(event.light_value, 300.0)
        self.assertAlmostEqual(event.sound_value, 45.2)
        self.assertFalse(event.pir_triggered)
        self.assertEqual(event.event_type, "sensor_reading")

    def test_last_seen_at_updated(self):
        """POST event updates IoTDevice.last_seen_at."""
        self.assertIsNone(self.device.last_seen_at)

        response = self.client.post(
            "/api/iot/events/",
            data=json.dumps(_sensor_payload()),
            content_type="application/json",
            HTTP_X_API_KEY=RAW_API_KEY,
        )
        self.assertEqual(response.status_code, 201)

        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_seen_at)


class TestIoTConfigAPI(TestCase):

    def setUp(self):
        self.store = _create_store()
        self.device = _create_device(self.store)

    def test_iot_config_get(self):
        """GET config endpoint returns device configuration with valid API key."""
        response = self.client.get(
            f"/api/iot/config/?device={DEVICE_EXTERNAL_ID}",
            HTTP_X_API_KEY=RAW_API_KEY,
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["device"], DEVICE_EXTERNAL_ID)
        self.assertEqual(body["mq9_threshold"], 500)
        self.assertFalse(body["alert_enabled"])
        self.assertIn("wifi", body)


class TestSensorDashboardAPI(TestCase):

    def setUp(self):
        self.store = _create_store()
        self.device = _create_device(self.store)
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='dashtest', password='testpass123')
        self.client.login(username='dashtest', password='testpass123')

    def test_sensor_dashboard_api(self):
        """GET /api/iot/sensors/data/ returns time-series sensor data."""
        for i in range(5):
            IoTEvent.objects.create(
                device=self.device,
                event_type="sensor_reading",
                mq9_value=100.0 + i * 10,
                light_value=200.0 + i,
                sound_value=50.0 + i,
                pir_triggered=False,
            )

        response = self.client.get(
            f"/api/iot/sensors/data/?device_id={self.device.id}&range=1h&sensor=mq9",
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertIn("labels", body)
        self.assertIn("values", body)
        self.assertEqual(len(body["labels"]), 5)
        self.assertEqual(len(body["values"]), 5)

    def test_pir_events_api(self):
        """GET /api/iot/sensors/pir-events/ returns PIR motion event counts."""
        for _ in range(3):
            IoTEvent.objects.create(
                device=self.device,
                event_type="sensor_reading",
                pir_triggered=True,
            )

        IoTEvent.objects.create(
            device=self.device,
            event_type="sensor_reading",
            pir_triggered=False,
        )

        response = self.client.get(
            f"/api/iot/sensors/pir-events/?device_id={self.device.id}&range=1h",
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertIn("labels", body)
        self.assertIn("counts", body)
        self.assertEqual(sum(body["counts"]), 3)
