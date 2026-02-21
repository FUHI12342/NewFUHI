"""
IoT Integration Tests — pytest-django

Validates:
  - IoTEventAPIView (POST /api/iot/events/)
  - IoTConfigAPIView (GET /api/iot/config/)
  - SensorDataAPIView (GET /api/iot/sensors/data/)
  - PIREventsAPIView (GET /api/iot/sensors/pir-events/)
"""
import pytest
import hashlib
import json
from django.test import Client
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

@pytest.mark.django_db
def test_iot_event_post_success():
    """POST sensor data with valid API key returns 201."""
    client = Client()
    store = _create_store()
    _create_device(store)

    response = client.post(
        "/api/iot/events/",
        data=json.dumps(_sensor_payload()),
        content_type="application/json",
        HTTP_X_API_KEY=RAW_API_KEY,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["device"] == DEVICE_EXTERNAL_ID
    assert body["event_type"] == "sensor_reading"
    assert "id" in body


@pytest.mark.django_db
def test_iot_event_invalid_api_key():
    """POST with wrong API key returns 404 (device not found by hash mismatch)."""
    client = Client()
    store = _create_store()
    _create_device(store)

    response = client.post(
        "/api/iot/events/",
        data=json.dumps(_sensor_payload()),
        content_type="application/json",
        HTTP_X_API_KEY="wrong-api-key-999",
    )
    # IoTEventAPIView returns 404 when device lookup by api_key_hash fails
    assert response.status_code == 404


@pytest.mark.django_db
def test_sensor_data_saved():
    """POST sensor data persists correct mq9/light/sound/pir values in IoTEvent."""
    client = Client()
    store = _create_store()
    _create_device(store)

    payload = _sensor_payload(mq9=200.5, light=300.0, sound=45.2, pir=False)
    response = client.post(
        "/api/iot/events/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_API_KEY=RAW_API_KEY,
    )
    assert response.status_code == 201

    event = IoTEvent.objects.latest("id")
    assert event.mq9_value == pytest.approx(200.5)
    assert event.light_value == pytest.approx(300.0)
    assert event.sound_value == pytest.approx(45.2)
    assert event.pir_triggered is False
    assert event.event_type == "sensor_reading"


@pytest.mark.django_db
def test_iot_config_get():
    """GET config endpoint returns device configuration with valid API key."""
    client = Client()
    store = _create_store()
    device = _create_device(store)

    response = client.get(
        f"/api/iot/config/?device={DEVICE_EXTERNAL_ID}",
        HTTP_X_API_KEY=RAW_API_KEY,
    )
    assert response.status_code == 200

    body = response.json()
    assert body["device"] == DEVICE_EXTERNAL_ID
    assert body["mq9_threshold"] == 500
    assert body["alert_enabled"] is False
    assert "wifi" in body


@pytest.mark.django_db
def test_last_seen_at_updated():
    """POST event updates IoTDevice.last_seen_at."""
    client = Client()
    store = _create_store()
    device = _create_device(store)
    assert device.last_seen_at is None

    response = client.post(
        "/api/iot/events/",
        data=json.dumps(_sensor_payload()),
        content_type="application/json",
        HTTP_X_API_KEY=RAW_API_KEY,
    )
    assert response.status_code == 201

    device.refresh_from_db()
    assert device.last_seen_at is not None


@pytest.mark.django_db
def test_sensor_dashboard_api():
    """GET /api/iot/sensors/data/ returns time-series sensor data."""
    client = Client()
    store = _create_store()
    device = _create_device(store)

    # Create some IoTEvents directly
    for i in range(5):
        IoTEvent.objects.create(
            device=device,
            event_type="sensor_reading",
            mq9_value=100.0 + i * 10,
            light_value=200.0 + i,
            sound_value=50.0 + i,
            pir_triggered=False,
        )

    response = client.get(
        f"/api/iot/sensors/data/?device_id={device.id}&range=1h&sensor=mq9",
    )
    assert response.status_code == 200

    body = response.json()
    assert "labels" in body
    assert "values" in body
    assert len(body["labels"]) == 5
    assert len(body["values"]) == 5


@pytest.mark.django_db
def test_pir_events_api():
    """GET /api/iot/sensors/pir-events/ returns PIR motion event counts."""
    client = Client()
    store = _create_store()
    device = _create_device(store)

    # Create IoTEvents with pir_triggered=True
    for _ in range(3):
        IoTEvent.objects.create(
            device=device,
            event_type="sensor_reading",
            pir_triggered=True,
        )

    # Create one with pir_triggered=False (should not be counted)
    IoTEvent.objects.create(
        device=device,
        event_type="sensor_reading",
        pir_triggered=False,
    )

    response = client.get(
        f"/api/iot/sensors/pir-events/?device_id={device.id}&range=1h",
    )
    assert response.status_code == 200

    body = response.json()
    assert "labels" in body
    assert "counts" in body
    # 3 PIR events in the same hour bucket => single label with count 3
    assert sum(body["counts"]) == 3
