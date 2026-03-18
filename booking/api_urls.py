# booking/api_urls.py
# API endpoints separated from i18n_patterns (no language prefix needed)
from django.urls import path, include

from . import views
from .views import IRSendAPIView, StaffShiftBulkRequestAPIView, StaffShiftCopyWeekAPIView
from .views_debug import AdminDebugPanelAPIView, LogLevelControlAPIView
from .views_dashboard import SensorDataAPIView, PIREventsAPIView, PIRStatusAPIView
from .views_restaurant_dashboard import (
    DashboardLayoutAPIView,
    ReservationStatsAPIView,
    SalesStatsAPIView,
    StaffPerformanceAPIView,
    ShiftSummaryAPIView,
    LowStockAlertAPIView,
    MenuEngineeringAPIView,
    ABCAnalysisAPIView,
    SalesForecastAPIView,
    SalesHeatmapAPIView,
    AOVTrendAPIView,
    CohortAnalysisAPIView,
    RFMAnalysisAPIView,
    BasketAnalysisAPIView,
    InsightsAPIView,
    KPIScoreCardAPIView,
    CustomerFeedbackAPIView,
    NPSStatsAPIView,
    VisitorForecastAPIView,
    CLVAnalysisAPIView,
    AutoOrderRecommendationAPIView,
    ExternalDataAPIView,
)
from .views_property import PropertyStatusAPIView, PropertyAlertResolveAPIView
from .views import CheckinAPIView, CartAddAPIView, CartUpdateAPIView, CartRemoveAPIView
from .views import TableCartAddAPI, TableCartUpdateAPI, TableCartRemoveAPI, TableOrderCreateAPI, TableOrderStatusAPI
# from .views_chat import AdminChatAPIView  # AI Chat一時無効化
from .views_attendance import (
    AttendanceStampAPIView, AttendanceTOTPRefreshAPI, AttendanceDayStatusAPI,
    AttendanceDayStatusHTMLView,
    AttendancePINStampAPIView, QRStampAPIView, ManualStampAPIView,
)
from .views_pos import POSOrderAPIView, POSOrderItemAPIView, POSCheckoutAPIView, KitchenOrderStatusAPI, KitchenOrdersHTMLView, KitchenOrderCompleteAPI, KitchenOrderUncompleteAPI
from .views_performance_dashboard import AttendancePerformanceAPIView
from .views_analytics import VisitorCountAPIView, VisitorHeatmapAPIView, ConversionAnalyticsAPIView
from .views_ai_recommend import AIRecommendationAPIView, AITrainModelAPIView, AIModelStatusAPIView
from .views_ec_dashboard import ECOrderAPIView, ECOrderShippingAPIView

app_name = 'booking_api'

urlpatterns = [
    # IoT APIs
    path('iot/events/', views.IoTEventAPIView.as_view(), name='iot_events'),
    path('iot/config/', views.IoTConfigAPIView.as_view(), name='iot_config'),

    # Timing APIs
    path('endTime', views.get_end_time, name='get_end_time'),
    path('currentTime', views.get_current_time, name='get_current_time'),
    path('reservation/<int:pk>/', views.get_reservation, name='get_reservation'),
    path('reservation_times/<int:pk>/', views.get_reservation_times, name='get_reservation_times'),

    # Menu / Order APIs
    path('menu', views.CustomerMenuJsonAPIView.as_view(), name='customer_menu_json'),
    path('products/alternatives/', views.ProductAlternativesAPIView.as_view(), name='product_alternatives_api'),
    path('orders/create/', views.OrderCreateAPIView.as_view(), name='order_create_api'),
    path('orders/status/', views.OrderStatusAPIView.as_view(), name='order_status_api'),
    path('staff/orders/served/', views.StaffMarkServedAPIView.as_view(), name='staff_mark_served_api'),
    path('staff/orders/items/<int:item_id>/status/', views.OrderItemStatusUpdateAPIView.as_view(), name='order_item_status_update_api'),

    # Stock API
    path('stock/inbound/apply/', views.InboundApplyAPIView.as_view(), name='inbound_apply_api'),

    # Debug APIs
    path('debug/panel/', AdminDebugPanelAPIView.as_view(), name='debug_panel_api'),
    path('debug/log-level/', LogLevelControlAPIView.as_view(), name='log_level_api'),

    # Sensor Dashboard APIs
    path('iot/sensors/data/', SensorDataAPIView.as_view(), name='sensor_data_api'),
    path('iot/sensors/pir-events/', PIREventsAPIView.as_view(), name='pir_events_api'),
    path('iot/sensors/pir-status/', PIRStatusAPIView.as_view(), name='pir_status_api'),

    # IR Smart Hub APIs
    path('iot/ir/send/', IRSendAPIView.as_view(), name='ir_send_api'),

    # Restaurant Dashboard APIs
    path('dashboard/layout/', DashboardLayoutAPIView.as_view(), name='dashboard_layout_api'),
    path('dashboard/reservations/', ReservationStatsAPIView.as_view(), name='reservation_stats_api'),
    path('dashboard/sales/', SalesStatsAPIView.as_view(), name='sales_stats_api'),
    path('dashboard/staff-performance/', StaffPerformanceAPIView.as_view(), name='staff_performance_api'),
    path('dashboard/shift-summary/', ShiftSummaryAPIView.as_view(), name='shift_summary_api'),
    path('dashboard/low-stock/', LowStockAlertAPIView.as_view(), name='low_stock_api'),
    path('dashboard/menu-engineering/', MenuEngineeringAPIView.as_view(), name='menu_engineering_api'),
    path('dashboard/abc-analysis/', ABCAnalysisAPIView.as_view(), name='abc_analysis_api'),
    path('dashboard/forecast/', SalesForecastAPIView.as_view(), name='sales_forecast_api'),
    path('dashboard/sales-heatmap/', SalesHeatmapAPIView.as_view(), name='sales_heatmap_api'),
    path('dashboard/aov-trend/', AOVTrendAPIView.as_view(), name='aov_trend_api'),
    path('dashboard/cohort/', CohortAnalysisAPIView.as_view(), name='cohort_analysis_api'),
    path('dashboard/rfm/', RFMAnalysisAPIView.as_view(), name='rfm_analysis_api'),
    path('dashboard/basket/', BasketAnalysisAPIView.as_view(), name='basket_analysis_api'),
    path('dashboard/insights/', InsightsAPIView.as_view(), name='insights_api'),
    path('dashboard/kpi-scorecard/', KPIScoreCardAPIView.as_view(), name='kpi_scorecard_api'),
    path('dashboard/feedback/', CustomerFeedbackAPIView.as_view(), name='customer_feedback_api'),
    path('dashboard/nps/', NPSStatsAPIView.as_view(), name='nps_stats_api'),
    path('dashboard/visitor-forecast/', VisitorForecastAPIView.as_view(), name='visitor_forecast_api'),
    path('dashboard/clv/', CLVAnalysisAPIView.as_view(), name='clv_analysis_api'),
    path('dashboard/auto-order/', AutoOrderRecommendationAPIView.as_view(), name='auto_order_api'),
    path('dashboard/external-data/', ExternalDataAPIView.as_view(), name='external_data_api'),

    # Property APIs
    path('properties/<int:pk>/status/', PropertyStatusAPIView.as_view(), name='property_status_api'),
    path('alerts/<int:pk>/resolve/', PropertyAlertResolveAPIView.as_view(), name='alert_resolve_api'),

    # Round3: QR Checkin API
    path('checkin/', CheckinAPIView.as_view(), name='checkin_api'),

    # Round3: EC Cart APIs
    path('shop/cart/add/', CartAddAPIView.as_view(), name='cart_add_api'),
    path('shop/cart/update/', CartUpdateAPIView.as_view(), name='cart_update_api'),
    path('shop/cart/remove/', CartRemoveAPIView.as_view(), name='cart_remove_api'),

    # AI Chat APIs (全チャット機能一時無効化 — Gemini APIキー再発行まで)
    # path('chat/admin/', AdminChatAPIView.as_view(), name='api_admin_chat'),
    # GuideChatAPIView removed (公開チャット廃止 — Gemini APIコストリスク対策)

    # Table ordering APIs
    path('table/<uuid:table_id>/cart/add/', TableCartAddAPI.as_view(), name='table_cart_add'),
    path('table/<uuid:table_id>/cart/update/', TableCartUpdateAPI.as_view(), name='table_cart_update'),
    path('table/<uuid:table_id>/cart/remove/', TableCartRemoveAPI.as_view(), name='table_cart_remove'),
    path('table/<uuid:table_id>/order/create/', TableOrderCreateAPI.as_view(), name='table_order_create'),
    path('table/<uuid:table_id>/orders/status/', TableOrderStatusAPI.as_view(), name='table_order_status'),

    # Air統合: シフトAPI
    path('shift/', include('booking.shift_api_urls')),
    path('shift/requests/<int:period_id>/bulk/', StaffShiftBulkRequestAPIView.as_view(), name='shift_requests_bulk'),
    path('shift/requests/<int:period_id>/copy-week/', StaffShiftCopyWeekAPIView.as_view(), name='shift_copy_week'),

    # Air統合: 勤怠API
    path('attendance/stamp/', AttendanceStampAPIView.as_view(), name='attendance_stamp'),
    path('attendance/totp/refresh/', AttendanceTOTPRefreshAPI.as_view(), name='attendance_totp_refresh'),
    path('attendance/day-status/', AttendanceDayStatusAPI.as_view(), name='attendance_day_status'),
    path('attendance/day-status-html/', AttendanceDayStatusHTMLView.as_view(), name='attendance_day_status_html'),

    # PIN打刻API
    path('attendance/pin-stamp/', AttendancePINStampAPIView.as_view(), name='attendance_pin_stamp'),

    # QRスキャン打刻API（ログイン不要、TOTP+PIN認証）
    path('attendance/qr-stamp/', QRStampAPIView.as_view(), name='attendance_qr_stamp'),

    # マニュアル打刻API（管理者用、端末忘れ時）
    path('attendance/manual-stamp/', ManualStampAPIView.as_view(), name='attendance_manual_stamp'),

    # 勤務実績API
    path('attendance/performance/', AttendancePerformanceAPIView.as_view(), name='attendance_performance_api'),

    # Air統合: POS API
    path('pos/orders/', POSOrderAPIView.as_view(), name='pos_orders'),
    path('pos/order-items/', POSOrderItemAPIView.as_view(), name='pos_order_items'),
    path('pos/order-items/<int:pk>/', POSOrderItemAPIView.as_view(), name='pos_order_item_detail'),
    path('pos/checkout/', POSCheckoutAPIView.as_view(), name='pos_checkout'),
    path('pos/order-item/<int:pk>/status/', KitchenOrderStatusAPI.as_view(), name='pos_order_item_status'),
    path('pos/kitchen-orders/', KitchenOrdersHTMLView.as_view(), name='pos_kitchen_orders_html'),
    path('pos/order/<int:pk>/complete/', KitchenOrderCompleteAPI.as_view(), name='pos_order_complete'),
    path('pos/order/<int:pk>/uncomplete/', KitchenOrderUncompleteAPI.as_view(), name='pos_order_uncomplete'),

    # Air統合: 分析API
    path('analytics/visitors/', VisitorCountAPIView.as_view(), name='analytics_visitors'),
    path('analytics/heatmap/', VisitorHeatmapAPIView.as_view(), name='analytics_heatmap'),
    path('analytics/conversion/', ConversionAnalyticsAPIView.as_view(), name='analytics_conversion'),

    # EC注文管理API
    path('ec/orders/', ECOrderAPIView.as_view(), name='ec_orders_api'),
    path('ec/orders/<int:pk>/shipping/', ECOrderShippingAPIView.as_view(), name='ec_order_shipping_api'),

    # Air統合: AI推薦API
    path('ai/recommendations/', AIRecommendationAPIView.as_view(), name='ai_recommendations'),
    path('ai/train/', AITrainModelAPIView.as_view(), name='ai_train'),
    path('ai/model-status/', AIModelStatusAPIView.as_view(), name='ai_model_status'),
]
