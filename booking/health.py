"""
Health check views for deployment monitoring.

Provides /healthz endpoint for AWS production deployment tracking.
- Basic: GET /healthz → {"status": "ok"}
- Detailed: GET /healthz?detail=1 → DB, Celery, Redis checks (staff only)
"""
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone

logger = logging.getLogger(__name__)


def _check_database() -> str:
    """Check database connectivity. Returns 'ok' or 'error'."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return "ok"
    except Exception as exc:
        logger.warning("Health check: database failed: %s", exc)
        return "error"


def _check_celery() -> str:
    """Check Celery broker connectivity. Returns 'ok' or 'unavailable'."""
    try:
        from django.conf import settings
        broker_url = getattr(settings, "CELERY_BROKER_URL", "")
        if not broker_url:
            return "not_configured"
        import redis as redis_lib
        r = redis_lib.Redis.from_url(broker_url, socket_timeout=2)
        r.ping()
        return "ok"
    except Exception as exc:
        logger.info("Health check: celery broker unavailable: %s", exc)
        return "unavailable"


def _check_redis() -> str:
    """Check Redis cache connectivity. Returns 'ok' or 'unavailable'."""
    try:
        from django.conf import settings
        cache_config = getattr(settings, "CACHES", {}).get("default", {})
        location = cache_config.get("LOCATION", "")
        backend = str(cache_config.get("BACKEND", ""))
        if location and "redis" in backend:
            import redis as redis_lib
            r = redis_lib.Redis.from_url(location, socket_timeout=2)
            r.ping()
            return "ok"
        # Fall back to celery broker URL as redis check
        broker = getattr(settings, "CELERY_BROKER_URL", "")
        if broker and "redis" in broker:
            import redis as redis_lib
            r = redis_lib.Redis.from_url(broker, socket_timeout=2)
            r.ping()
            return "ok"
        return "not_configured"
    except Exception as exc:
        logger.info("Health check: redis unavailable: %s", exc)
        return "unavailable"


@require_http_methods(["GET"])
def healthz(request):
    """
    Health check endpoint for deployment monitoring.

    GET /healthz → minimal {"status": "ok"}
    GET /healthz?detail=1 → detailed checks (staff auth required)

    No authentication required for basic check.
    """
    detail = request.GET.get("detail")

    if not detail:
        return JsonResponse({"status": "ok"})

    # Detailed checks require staff authentication
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({"error": "authentication required"}, status=403)

    db_status = _check_database()
    celery_status = _check_celery()
    redis_status = _check_redis()

    checks = {
        "database": db_status,
        "celery": celery_status,
        "redis": redis_status,
    }

    # Determine overall status
    if db_status == "error":
        overall = "degraded"
        http_status = 503
    elif celery_status == "unavailable" or redis_status == "unavailable":
        overall = "warning"
        http_status = 200
    else:
        overall = "ok"
        http_status = 200

    return JsonResponse(
        {
            "status": overall,
            "checks": checks,
            "timestamp": timezone.now().isoformat(),
        },
        status=http_status,
    )
