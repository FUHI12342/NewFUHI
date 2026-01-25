"""
Health check views for deployment monitoring.

Provides /healthz endpoint for AWS production deployment tracking.
"""
import os
import django
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@require_http_methods(["GET"])
def healthz(request):
    """
    Health check endpoint for deployment monitoring.
    
    Returns JSON with deployment information:
    - status: "ok" if system is healthy
    - git_sha: Current deployment git commit SHA
    - django: Django version
    - settings: Current settings module
    - env: Environment name (staging/production/local)
    
    No authentication required for monitoring purposes.
    """
    # Get git SHA from environment variable, fallback to "unknown"
    git_sha = os.getenv("APP_GIT_SHA", "unknown")
    
    # Determine environment from settings module
    settings_module = os.getenv("DJANGO_SETTINGS_MODULE", "unknown")
    if "staging" in settings_module:
        env = "staging"
    elif "production" in settings_module:
        env = "production"
    elif "local" in settings_module:
        env = "local"
    else:
        env = "unknown"
    
    health_data = {
        "status": "ok",
        "git_sha": git_sha,
        "django": django.get_version(),
        "settings": settings_module,
        "env": env
    }
    
    return JsonResponse(health_data)