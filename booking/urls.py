from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views
from .views import (
    LineEnterView,
    LineCallbackView,
    CancelReservationView,
    UserList,
    IoTMQ9GraphView,
)


app_name = 'booking'

urlpatterns = [
    # トップ・認証
    path('', views.StoreList.as_view(), name='store_list'),
    path('index/', views.Index.as_view(), name='index'),
    path('login/', LoginView.as_view(template_name='admin/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # 店舗・スタッフ・予約
    path('store/<int:pk>/staffs/', views.StaffList.as_view(), name='staff_list'),
    path('staff/<int:pk>/calendar/', views.StaffCalendar.as_view(), name='staff_calendar'),
    path(
        'staff/<int:pk>/calendar/<int:year>/<int:month>/<int:day>/',
        views.StaffCalendar.as_view(),
        name='calendar'
    ),
    path(
        'staff/<int:pk>/prebooking/<int:year>/<int:month>/<int:day>/<int:hour>/',
        views.PreBooking.as_view(),
        name='prebooking'
    ),

    # LINE ログイン & 決済フロー
    path('line_enter/', LineEnterView.as_view(), name='line_enter'),
    path('booking/login/line/success/', LineCallbackView.as_view(), name='line_success'),
    path('line_timer/<str:user_id>/', views.LINETimerView, name='LINETimerView'),

    # 時刻・予約関連API
    path('api/endTime', views.get_end_time),
    path('api/currentTime', views.get_current_time),
    path('api/reservation/<int:pk>/', views.get_reservation, name='get_reservation'),
    path('api/reservation_times/<int:pk>/', views.get_reservation_times, name='get_reservation_times'),

    # 決済Webhook
    path('coiney_webhook/<str:orderId>/', views.coiney_webhook, name='coiney_webhook'),

    # ユーザーAPI（サンプル）
    path('users/', UserList.as_view(), name='user_list'),

    
    

    # 予約キャンセル
    path(
        'cancel_reservation/<int:schedule_id>/',
        CancelReservationView.as_view(),
        name='cancel_reservation'
    ),

    # ファイルアップロード（スタッフ画像など）
    path('upload/', views.upload_file, name='upload_file'),

    # マイページ系
    path('mypage/', views.MyPage.as_view(), name='my_page'),
    path('mypage/<int:pk>/', views.MyPageWithPk.as_view(), name='my_page_with_pk'),
    path('mypage/<int:pk>/calendar/', views.MyPageCalendar.as_view(), name='my_page_calendar'),
    path(
        'mypage/<int:pk>/calendar/<int:year>/<int:month>/<int:day>/',
        views.MyPageCalendar.as_view(),
        name='my_page_calendar'
    ),
    path(
        'mypage/<int:pk>/config/<int:year>/<int:month>/<int:day>/',
        views.MyPageDayDetail.as_view(),
        name='my_page_day_detail'
    ),
    path('mypage/schedule/<int:pk>/', views.MyPageSchedule.as_view(), name='my_page_schedule'),
    path(
        'mypage/schedule/<int:pk>/delete/',
        views.MyPageScheduleDelete.as_view(),
        name='my_page_schedule_delete'
    ),
    path(
        'mypage/holiday/add/<int:pk>/<int:year>/<int:month>/<int:day>/<int:hour>/',
        views.my_page_holiday_add,
        name='my_page_holiday_add'
    ),
    path(
        'mypage/holiday/add/<int:pk>/<int:year>/<int:month>/<int:day>/',
        views.my_page_day_add,
        name='my_page_day_add'
    ),

    # ===== IoT 関連 API =====
    path('api/iot/events/', views.IoTEventAPIView.as_view(), name='iot_events'),
    path('api/iot/config/', views.IoTConfigAPIView.as_view(), name='iot_config'),

    # ===== IoT 管理画面（MQ-9 グラフ） =====
    path('admin/iot/mq9/', IoTMQ9GraphView.as_view(), name='admin_iot_mq9'),

    # ===== 在庫・注文・入庫QR・多言語メニュー =====
    path('menu/<int:store_id>/', views.CustomerMenuView.as_view(), name='customer_menu'),
    path('api/menu', views.CustomerMenuJsonAPIView.as_view(), name='customer_menu_json'),

    path('api/products/alternatives/', views.ProductAlternativesAPIView.as_view(), name='product_alternatives_api'),

    path('api/orders/create/', views.OrderCreateAPIView.as_view(), name='order_create_api'),
    path('api/orders/status/', views.OrderStatusAPIView.as_view(), name='order_status_api'),
    path('api/staff/orders/served/', views.StaffMarkServedAPIView.as_view(), name='staff_mark_served_api'),
    path('api/staff/orders/items/<int:item_id>/status/', views.OrderItemStatusUpdateAPIView.as_view(), name='order_item_status_update_api'),

    path('stock/inbound/', views.InboundQRView.as_view(), name='inbound_qr'),
    path('api/stock/inbound/apply/', views.InboundApplyAPIView.as_view(), name='inbound_apply_api'),
]