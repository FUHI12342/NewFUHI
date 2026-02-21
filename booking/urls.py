from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views
from .views import (
    LineEnterView,
    LineCallbackView,
    CancelReservationView,
    UserList,
    IoTMQ9GraphView,
    IoTEventAPIView,
    IoTConfigAPIView,
    LoginRedirectView,
    BookingTopPage,
    AllFortuneTellerList,
    DateFirstCalendar,
    BookingChannelChoice,
    EmailBookingView,
    EmailVerifyView,
    PrivacyPolicyView,
    TokushohoView,
    StaffShiftCalendarView,
    StaffShiftSubmitView,
)


app_name = 'booking'

urlpatterns = [
    # Top / Auth
    path('', BookingTopPage.as_view(), name='booking_top'),
    path('stores/', views.StoreList.as_view(), name='store_list'),
    path('fortune-tellers/', AllFortuneTellerList.as_view(), name='all_fortune_tellers'),
    path('date-calendar/', DateFirstCalendar.as_view(), name='date_first_calendar'),
    path('date-calendar/<int:year>/<int:month>/<int:day>/', DateFirstCalendar.as_view(), name='date_first_calendar_day'),
    path('index/', views.Index.as_view(), name='index'),
    path('help/', views.HelpView.as_view(), name='help'),
    path('login/', LoginView.as_view(template_name='admin/login.html'), name='login'),
    path('login/redirect/', LoginRedirectView.as_view(), name='login_redirect'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # Store / Staff / Booking
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
    path(
        'staff/<int:pk>/prebooking/<int:year>/<int:month>/<int:day>/<int:hour>/<int:minute>/',
        views.PreBooking.as_view(),
        name='prebooking_minute'
    ),

    # Booking channel choice & email flow
    path('booking/channel-choice/', BookingChannelChoice.as_view(), name='channel_choice'),
    path('booking/email/', EmailBookingView.as_view(), name='email_booking'),
    path('booking/email/verify/', EmailVerifyView.as_view(), name='email_verify'),

    # LINE login & payment
    path('line_enter/', LineEnterView.as_view(), name='line_enter'),
    path('booking/login/line/success/', LineCallbackView.as_view(), name='line_success'),
    path('line_timer/<str:user_id>/', views.LINETimerView, name='LINETimerView'),

    # Cancel
    path(
        'cancel_reservation/<int:schedule_id>/',
        CancelReservationView.as_view(),
        name='cancel_reservation'
    ),

    # Users
    path('users/', UserList.as_view(), name='user_list'),

    # File upload
    path('upload/', views.upload_file, name='upload_file'),

    # My Page
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

    # Shift management
    path('shift/', StaffShiftCalendarView.as_view(), name='staff_shift_calendar'),
    path('shift/<int:period_id>/submit/', StaffShiftSubmitView.as_view(), name='staff_shift_submit'),

    # Static pages
    path('privacy/', PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('tokushoho/', TokushohoView.as_view(), name='tokushoho'),

    # Menu page (user-facing HTML)
    path('menu/<int:store_id>/', views.CustomerMenuView.as_view(), name='customer_menu'),

    # Stock inbound (user-facing HTML)
    path('stock/inbound/', views.InboundQRView.as_view(), name='inbound_qr'),

    # Sensor dashboard
    path('dashboard/sensors/', views.IoTSensorDashboardView.as_view(), name='iot_sensor_dashboard'),

    # Property monitoring
    path('properties/', views.PropertyListView.as_view(), name='property_list'),
    path('properties/<int:pk>/', views.PropertyDetailView.as_view(), name='property_detail'),
]
