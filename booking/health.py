"""
Health check views for deployment monitoring.

Provides /healthz endpoint for AWS production deployment tracking.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@require_http_methods(["GET"])
def healthz(request):
    """
    Health check endpoint for deployment monitoring.

    Returns minimal JSON to avoid information leakage.
    No authentication required for monitoring purposes.
    """
    return JsonResponse({"status": "ok"})
