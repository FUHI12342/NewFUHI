"""project URL Configuration"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

from booking import views as booking_views
from booking.admin_site import custom_site
from booking.health import healthz
from booking.views_debug import AdminDebugPanelView, IoTDeviceDebugView
from booking.views_restaurant_dashboard import RestaurantDashboardView
from booking.views_shift_manager import ManagerShiftCalendarView, TodayShiftTimelineView
from django.views.generic import RedirectView
from django.http import HttpResponsePermanentRedirect
from booking.views_attendance import AttendanceQRDisplayView, AttendanceBoardView, AttendancePINDisplayView
from booking.views_pos import POSView, POSReceiptView, KitchenDisplayView
from booking.views_analytics import VisitorAnalyticsDashboardView
from booking.views_ai_recommend import AIRecommendationView
from booking.views_menu_preview import MenuPreviewRedirectView
from booking.views_inventory import InventoryDashboardView, StockInFormView
from booking.views_performance_dashboard import StaffPerformanceDashboardView
from booking.views_ec_dashboard import ECOrderDashboardView
import booking.admin

# Non-i18n URLs (APIs, health check, legacy redirects, embed)
urlpatterns = [
    # Embed views (no i18n prefix, iframe-friendly)
    path("embed/", include("booking.embed_urls")),

    # Legacy URL redirects (crawlers hitting old .html paths)
    re_path(
        r"^staff/\d+/prebooking/\d+/\d+/\d+/\d+/list_\w+\.html$",
        lambda request: HttpResponsePermanentRedirect("/"),
    ),
    re_path(
        r"^booking/mq\d+/$",
        lambda request: HttpResponsePermanentRedirect("/"),
    ),

    # Health check endpoint (no auth required)
    path("healthz", healthz, name="healthz"),

    # API endpoints (no language prefix)
    path("api/", include("booking.api_urls")),

    # Payment webhook
    path("coiney_webhook/<str:orderId>/", booking_views.coiney_webhook, name="coiney_webhook"),

    # Language switching
    path("i18n/", include("django.conf.urls.i18n")),

    # Table ordering (QR entry - no i18n prefix)
    path("t/", include("booking.table_urls")),
]

# i18n-wrapped URLs (user-facing pages)
urlpatterns += i18n_patterns(
    # Admin custom views (before admin/ catch-all)
    path(
        "admin/iot/sensors/",
        custom_site.admin_view(booking_views.IoTMQ9GraphView.as_view()),
        name="admin_iot_sensors",
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
        "admin/dashboard/sales/",
        custom_site.admin_view(RestaurantDashboardView.as_view()),
        name="admin_sales_dashboard",
    ),
    # 旧パス維持（後方互換）
    path(
        "admin/dashboard/restaurant/",
        custom_site.admin_view(RestaurantDashboardView.as_view()),
        name="admin_restaurant_dashboard",
    ),

    # Air統合: シフトカレンダー
    path(
        "admin/shift/calendar/",
        custom_site.admin_view(ManagerShiftCalendarView.as_view()),
        name="admin_shift_calendar",
    ),

    # Air統合: 本日のシフト
    path(
        "admin/shift/today/",
        custom_site.admin_view(TodayShiftTimelineView.as_view()),
        name="admin_today_shift",
    ),

    # 旧マイシフト → シフトカレンダーへリダイレクト（後方互換）
    path(
        "admin/shift/my/",
        RedirectView.as_view(pattern_name='admin_shift_calendar', permanent=True),
        name="staff_my_shift",
    ),

    # Air統合: QR勤怠
    path(
        "admin/attendance/qr/",
        custom_site.admin_view(AttendanceQRDisplayView.as_view()),
        name="admin_attendance_qr",
    ),
    path(
        "admin/attendance/pin/",
        custom_site.admin_view(AttendancePINDisplayView.as_view()),
        name="admin_attendance_pin",
    ),
    path(
        "admin/attendance/board/",
        custom_site.admin_view(AttendanceBoardView.as_view()),
        name="admin_attendance_board",
    ),

    # 勤務実績ダッシュボード
    path(
        "admin/attendance/performance/",
        custom_site.admin_view(StaffPerformanceDashboardView.as_view()),
        name="admin_staff_performance",
    ),

    # Air統合: POS
    path(
        "admin/pos/",
        custom_site.admin_view(POSView.as_view()),
        name="admin_pos",
    ),
    path(
        "admin/pos/receipt/<str:receipt_number>/",
        custom_site.admin_view(POSReceiptView.as_view()),
        name="admin_pos_receipt",
    ),
    path(
        "admin/pos/kitchen/",
        custom_site.admin_view(KitchenDisplayView.as_view()),
        name="admin_kitchen_display",
    ),

    # Air統合: 来客分析
    path(
        "admin/analytics/visitors/",
        custom_site.admin_view(VisitorAnalyticsDashboardView.as_view()),
        name="admin_visitor_analytics",
    ),

    # メニュープレビュー（最初のテーブルの /t/{uuid}/ へリダイレクト）
    path(
        "admin/menu/preview/",
        custom_site.admin_view(MenuPreviewRedirectView.as_view()),
        name="admin_menu_preview",
    ),

    # Air統合: AI推薦
    path(
        "admin/ai/recommendation/",
        custom_site.admin_view(AIRecommendationView.as_view()),
        name="admin_ai_recommendation",
    ),

    # EC注文管理ダッシュボード
    path(
        "admin/ec/orders/",
        custom_site.admin_view(ECOrderDashboardView.as_view()),
        name="admin_ec_orders",
    ),

    # 在庫管理ダッシュボード
    path(
        "admin/inventory/",
        custom_site.admin_view(InventoryDashboardView.as_view()),
        name="admin_inventory_dashboard",
    ),
    path(
        "admin/inventory/stock-in/",
        custom_site.admin_view(StockInFormView.as_view()),
        name="admin_inventory_stock_in",
    ),

    # SNS OAuth
    path("admin/social/", include("booking.social_urls")),

    # Admin site
    path("admin/", custom_site.urls),

    # Booking app (user-facing)
    path("", include("booking.urls")),

    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
