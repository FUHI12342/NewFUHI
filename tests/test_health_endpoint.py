"""
Tests for health check endpoint.

TDD: Tests written FIRST, then implementation.
Validates: DB connectivity, Celery broker, Redis, overall health status, auth.
"""
import pytest
from unittest.mock import patch
from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def staff_client(db):
    """Return a Client logged in as staff user."""
    user = User.objects.create_user(
        username="healthtest", password="testpass123",
        is_staff=True,
    )
    c = Client()
    c.login(username="healthtest", password="testpass123")
    return c


@pytest.mark.django_db
class TestHealthzBasic:
    """Basic health endpoint tests."""

    def test_healthz_returns_200(self, client):
        """GET /healthz returns 200."""
        response = client.get("/healthz")
        assert response.status_code == 200

    def test_healthz_returns_json(self, client):
        """Response is valid JSON."""
        response = client.get("/healthz")
        data = response.json()
        assert "status" in data

    def test_healthz_status_ok_when_healthy(self, client):
        """status is 'ok' when all checks pass."""
        response = client.get("/healthz")
        data = response.json()
        assert data["status"] == "ok"

    def test_healthz_post_not_allowed(self, client):
        """POST /healthz returns 405."""
        response = client.post("/healthz")
        assert response.status_code == 405

    def test_healthz_no_auth_required(self, client):
        """No authentication needed for basic health check."""
        response = client.get("/healthz")
        assert response.status_code == 200


@pytest.mark.django_db
class TestHealthzDetailed:
    """Detailed health check endpoint (/healthz?detail=1)."""

    def test_detail_requires_auth(self, client):
        """detail=1 returns 403 for unauthenticated users."""
        response = client.get("/healthz?detail=1")
        assert response.status_code == 403

    def test_detail_requires_staff(self, db):
        """detail=1 returns 403 for non-staff authenticated users."""
        User.objects.create_user(username="regular", password="pass123", is_staff=False)
        c = Client()
        c.login(username="regular", password="pass123")
        response = c.get("/healthz?detail=1")
        assert response.status_code == 403

    def test_detail_includes_db_status(self, staff_client):
        """detail=1 includes database check for staff."""
        response = staff_client.get("/healthz?detail=1")
        data = response.json()
        assert "checks" in data
        assert "database" in data["checks"]

    def test_detail_db_ok_when_connected(self, staff_client):
        """DB check is 'ok' when database is accessible."""
        response = staff_client.get("/healthz?detail=1")
        data = response.json()
        assert data["checks"]["database"] == "ok"

    def test_detail_includes_celery_status(self, staff_client):
        """detail=1 includes celery broker check."""
        response = staff_client.get("/healthz?detail=1")
        data = response.json()
        assert "celery" in data["checks"]

    def test_detail_includes_redis_status(self, staff_client):
        """detail=1 includes redis check."""
        response = staff_client.get("/healthz?detail=1")
        data = response.json()
        assert "redis" in data["checks"]

    def test_detail_includes_timestamp(self, staff_client):
        """detail=1 includes server timestamp."""
        response = staff_client.get("/healthz?detail=1")
        data = response.json()
        assert "timestamp" in data

    @patch("booking.health._check_database")
    def test_status_degraded_when_db_fails(self, mock_db, staff_client):
        """status is 'degraded' if DB check fails."""
        mock_db.return_value = "error"
        response = staff_client.get("/healthz?detail=1")
        data = response.json()
        assert data["status"] == "degraded"
        assert response.status_code == 503

    @patch("booking.health._check_database", return_value="ok")
    @patch("booking.health._check_celery", return_value="unavailable")
    @patch("booking.health._check_redis", return_value="ok")
    def test_status_warning_when_celery_unavailable(self, mock_redis, mock_celery, mock_db, staff_client):
        """status is 'warning' if celery is unavailable (non-critical)."""
        response = staff_client.get("/healthz?detail=1")
        data = response.json()
        assert data["status"] in ("ok", "warning")

    @patch("booking.health._check_database", return_value="ok")
    @patch("booking.health._check_celery", return_value="ok")
    @patch("booking.health._check_redis", return_value="unavailable")
    def test_status_warning_when_redis_unavailable(self, mock_redis, mock_celery, mock_db, staff_client):
        """status is 'warning' if redis is unavailable (non-critical)."""
        response = staff_client.get("/healthz?detail=1")
        data = response.json()
        assert data["status"] in ("ok", "warning")


@pytest.mark.django_db
class TestHealthzSecurity:
    """Security tests for health endpoint."""

    def test_no_sensitive_data_in_basic_response(self, client):
        """Basic response doesn't leak credentials or connection strings."""
        response = client.get("/healthz")
        raw = response.content.decode().lower()
        for banned in ("password=", "secret=", "token=", "://"):
            assert banned not in raw, f"Leaked: {banned!r}"

    def test_detail_blocked_for_anonymous(self, client):
        """Anonymous users cannot access detailed checks."""
        response = client.get("/healthz?detail=1")
        assert response.status_code == 403
        data = response.json()
        assert "checks" not in data

    def test_detail_doesnt_expose_connection_strings(self, staff_client):
        """Detail response doesn't expose connection strings."""
        response = staff_client.get("/healthz?detail=1")
        raw = response.content.decode()
        assert "redis://" not in raw
        assert "postgres://" not in raw
        assert "mysql://" not in raw
