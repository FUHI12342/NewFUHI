# booking/api_urls.py
# API endpoints separated from i18n_patterns (no language prefix needed)
from django.urls import path

from . import views
from .views import IRSendAPIView
from .views_debug import AdminDebugPanelAPIView, LogLevelControlAPIView
from .views_dashboard import SensorDataAPIView, PIREventsAPIView, PIRStatusAPIView
from .views_restaurant_dashboard import (
    DashboardLayoutAPIView,
    ReservationStatsAPIView,
    SalesStatsAPIView,
    StaffPerformanceAPIView,
    ShiftSummaryAPIView,
)
from .views_property import PropertyStatusAPIView, PropertyAlertResolveAPIView
from .views import CheckinAPIView, CartAddAPIView, CartUpdateAPIView, CartRemoveAPIView
from .views import TableCartAddAPI, TableCartUpdateAPI, TableCartRemoveAPI, TableOrderCreateAPI, TableOrderStatusAPI
from .views_chat import AdminChatAPIView, GuideChatAPIView

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

    # Property APIs
    path('properties/<int:pk>/status/', PropertyStatusAPIView.as_view(), name='property_status_api'),
    path('alerts/<int:pk>/resolve/', PropertyAlertResolveAPIView.as_view(), name='alert_resolve_api'),

    # Round3: QR Checkin API
    path('checkin/', CheckinAPIView.as_view(), name='checkin_api'),

    # Round3: EC Cart APIs
    path('shop/cart/add/', CartAddAPIView.as_view(), name='cart_add_api'),
    path('shop/cart/update/', CartUpdateAPIView.as_view(), name='cart_update_api'),
    path('shop/cart/remove/', CartRemoveAPIView.as_view(), name='cart_remove_api'),

    # AI Chat APIs
    path('chat/admin/', AdminChatAPIView.as_view(), name='api_admin_chat'),
    path('chat/guide/', GuideChatAPIView.as_view(), name='api_guide_chat'),

    # Table ordering APIs
    path('table/<uuid:table_id>/cart/add/', TableCartAddAPI.as_view(), name='table_cart_add'),
    path('table/<uuid:table_id>/cart/update/', TableCartUpdateAPI.as_view(), name='table_cart_update'),
    path('table/<uuid:table_id>/cart/remove/', TableCartRemoveAPI.as_view(), name='table_cart_remove'),
    path('table/<uuid:table_id>/order/create/', TableOrderCreateAPI.as_view(), name='table_order_create'),
    path('table/<uuid:table_id>/orders/status/', TableOrderStatusAPI.as_view(), name='table_order_status'),
]
