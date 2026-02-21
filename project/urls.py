"""project URL Configuration"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

from booking import views as booking_views
from booking.admin_site import custom_site
from booking.health import healthz
from booking.views_debug import AdminDebugPanelView, IoTDeviceDebugView
from booking.views_restaurant_dashboard import RestaurantDashboardView
import booking.admin

# Non-i18n URLs (APIs, health check)
urlpatterns = [
    # Health check endpoint (no auth required)
    path("healthz", healthz, name="healthz"),

    # API endpoints (no language prefix)
    path("api/", include("booking.api_urls")),

    # Payment webhook
    path("coiney_webhook/<str:orderId>/", booking_views.coiney_webhook, name="coiney_webhook"),

    # Language switching
    path("i18n/", include("django.conf.urls.i18n")),
]

# i18n-wrapped URLs (user-facing pages)
urlpatterns += i18n_patterns(
    # Admin custom views (before admin/ catch-all)
    path(
        "admin/iot/mq9/",
        custom_site.admin_view(booking_views.IoTMQ9GraphView.as_view()),
        name="admin_iot_mq9",
    ),
    path(
        "admin/debug/",
        custom_site.admin_view(AdminDebugPanelView.as_view()),
        name="admin_debug_panel",
    ),
    path(
        "admin/debug/device/<int:device_id>/",
        custom_site.admin_view(IoTDeviceDebugView.as_view()),
        name="admin_iot_device_debug",
    ),
    path(
        "admin/dashboard/restaurant/",
        custom_site.admin_view(RestaurantDashboardView.as_view()),
        name="admin_restaurant_dashboard",
    ),

    # Admin site
    path("admin/", custom_site.urls),

    # Booking app (user-facing)
    path("", include("booking.urls")),

    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
