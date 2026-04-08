"""project URL Configuration"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

from booking import views as booking_views
from booking.admin_site import custom_site
from booking.views_line_webhook import line_webhook as line_webhook_view
from booking.health import healthz
from booking.views_debug import AdminDebugPanelView, IoTDeviceDebugView
from booking.views_restaurant_dashboard import RestaurantDashboardView
from booking.views_shift_manager import ManagerShiftCalendarView, TodayShiftTimelineView, StaffingRequirementView
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
from booking.views_theme import ThemePreviewView, ThemePresetsAPIView, ThemeCustomizerView
from booking.views_page_layout import PageLayoutEditorView
from booking.views_page_builder import (
    PageBuilderListView, PageBuilderCreateView,
    PageBuilderEditView, PageBuilderPublishView,
    PageBuilderDuplicateView, PageBuilderUploadView,
    SavedBlockListView, SavedBlockCreateView, SavedBlockDeleteView,
    CustomPageView,
)
from booking.views_site_wizard import SiteSetupWizardView
from booking.views_line_admin import (
    LineSegmentView, LineSegmentSendView,
    LinePendingView, LineReservationConfirmView, LineReservationRejectView,
)
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

    # Custom pages (public, no i18n prefix)
    path(
        "p/<int:store_id>/<slug:slug>/",
        CustomPageView.as_view(),
        name="custom_page_public",
    ),

    # Health check endpoint (no auth required)
    path("healthz", healthz, name="healthz"),

    # API endpoints (no language prefix)
    path("api/", include("booking.api_urls")),

    # Payment webhook
    path("coiney_webhook/<str:orderId>/", booking_views.coiney_webhook, name="coiney_webhook"),

    # Language switching
    path("i18n/", include("django.conf.urls.i18n")),

    # LINE Webhook
    path("line/webhook/", line_webhook_view, name="line_webhook"),

    # LINE予約確認/却下API
    path("api/line/reservations/<int:pk>/confirm/", LineReservationConfirmView.as_view(), name="line_reservation_confirm"),
    path("api/line/reservations/<int:pk>/reject/", LineReservationRejectView.as_view(), name="line_reservation_reject"),

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

    # 必要人数設定（統合ページ）
    path(
        "admin/shift/staffing/",
        custom_site.admin_view(StaffingRequirementView.as_view()),
        name="admin_staffing_requirement",
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

    # Site setup wizard
    path(
        "admin/site-wizard/<int:store_id>/",
        custom_site.admin_view(SiteSetupWizardView.as_view()),
        name="admin_site_wizard",
    ),

    # Page layout editor
    path(
        "admin/page-layout/<int:store_id>/",
        custom_site.admin_view(PageLayoutEditorView.as_view()),
        name="admin_page_layout_editor",
    ),

    # Page builder (GrapesJS)
    path(
        "admin/pages/<int:store_id>/",
        custom_site.admin_view(PageBuilderListView.as_view()),
        name="admin_page_builder_list",
    ),
    path(
        "admin/pages/<int:store_id>/new/",
        custom_site.admin_view(PageBuilderCreateView.as_view()),
        name="admin_page_builder_create",
    ),
    path(
        "admin/pages/<int:store_id>/<int:page_id>/edit/",
        custom_site.admin_view(PageBuilderEditView.as_view()),
        name="admin_page_builder_edit",
    ),
    path(
        "admin/pages/<int:store_id>/<int:page_id>/publish/",
        custom_site.admin_view(PageBuilderPublishView.as_view()),
        name="admin_page_builder_publish",
    ),
    path(
        "admin/pages/<int:store_id>/<int:page_id>/duplicate/",
        custom_site.admin_view(PageBuilderDuplicateView.as_view()),
        name="admin_page_builder_duplicate",
    ),
    path(
        "admin/pages/<int:store_id>/upload/",
        custom_site.admin_view(PageBuilderUploadView.as_view()),
        name="admin_page_builder_upload",
    ),
    # Saved blocks API
    path(
        "admin/pages/<int:store_id>/blocks/",
        custom_site.admin_view(SavedBlockListView.as_view()),
        name="admin_saved_block_list",
    ),
    path(
        "admin/pages/<int:store_id>/blocks/create/",
        custom_site.admin_view(SavedBlockCreateView.as_view()),
        name="admin_saved_block_create",
    ),
    path(
        "admin/pages/<int:store_id>/blocks/<int:block_id>/delete/",
        custom_site.admin_view(SavedBlockDeleteView.as_view()),
        name="admin_saved_block_delete",
    ),

    # Theme preview, customizer & API
    path(
        "admin/theme/preview/<int:store_id>/",
        custom_site.admin_view(ThemePreviewView.as_view()),
        name="admin_theme_preview",
    ),
    path(
        "admin/theme/customizer/<int:store_id>/",
        custom_site.admin_view(ThemeCustomizerView.as_view()),
        name="admin_theme_customizer",
    ),
    path(
        "admin/theme/presets/",
        custom_site.admin_view(ThemePresetsAPIView.as_view()),
        name="admin_theme_presets_api",
    ),

    # LINE管理: セグメント配信
    path(
        "admin/line/segment/",
        custom_site.admin_view(LineSegmentView.as_view()),
        name="admin_line_segment",
    ),
    path(
        "admin/line/segment/send/",
        custom_site.admin_view(LineSegmentSendView.as_view()),
        name="admin_line_segment_send",
    ),

    # LINE管理: 仮予約確認
    path(
        "admin/line/pending/",
        custom_site.admin_view(LinePendingView.as_view()),
        name="admin_line_pending",
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
