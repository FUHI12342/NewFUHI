from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path, include
from . import views
from .views import LineEnterView, LineCallbackView,CancelReservationView,UserList,analyze_customers,LineWebhookView
from .admin import custom_site

app_name = 'booking'

urlpatterns = [
    path('', views.StoreList.as_view(), name='store_list'),
    path('index/', views.Index.as_view(), name='index'),
    path('login/', LoginView.as_view(template_name='admin/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('store/<int:pk>/staffs/', views.StaffList.as_view(), name='staff_list'),
    path('staff/<int:pk>/calendar/', views.StaffCalendar.as_view(), name='staff_calendar'),
    path('staff/<int:pk>/calendar/<int:year>/<int:month>/<int:day>/', views.StaffCalendar.as_view(), name='calendar'),
    path('staff/<int:pk>/prebooking/<int:year>/<int:month>/<int:day>/<int:hour>/', views.PreBooking.as_view(), name='prebooking'),

    path('line_enter/', LineEnterView.as_view(), name='line_enter'),
    path('booking/login/line/success/', LineCallbackView.as_view(), name='line_success'),  
    #path('paying_success/<str:reservation_number>/', views.PayingSuccessView.as_view(), name='paying_success'),
    path('line_timer/<str:user_id>/', views.LINETimerView, name='LINETimerView'),
    path('api/endTime', views.get_end_time),
    path('api/currentTime', views.get_current_time),
    path('api/reservation/<int:pk>/', views.get_reservation, name='get_reservation'),
    path('coiney_webhook/<str:orderId>/', views.coiney_webhook, name='coiney_webhook'),
    path('users/', UserList.as_view()),
    
    path('custom_admin/', custom_site.urls),
    path('cancel_reservation/<int:schedule_id>/', CancelReservationView.as_view(), name='cancel_reservation'),
    path('upload/', views.upload_file, name='upload_file'),
    path('mypage/', views.MyPage.as_view(), name='my_page'),
    path('mypage/<int:pk>/', views.MyPageWithPk.as_view(), name='my_page_with_pk'),
    path('mypage/<int:pk>/calendar/', views.MyPageCalendar.as_view(), name='my_page_calendar'),
    path('mypage/<int:pk>/calendar/<int:year>/<int:month>/<int:day>/', views.MyPageCalendar.as_view(), name='my_page_calendar'),
    path('mypage/<int:pk>/config/<int:year>/<int:month>/<int:day>/', views.MyPageDayDetail.as_view(), name='my_page_day_detail'),
    path('mypage/schedule/<int:pk>/', views.MyPageSchedule.as_view(), name='my_page_schedule'),
    path('mypage/schedule/<int:pk>/delete/', views.MyPageScheduleDelete.as_view(), name='my_page_schedule_delete'),
    path('mypage/holiday/add/<int:pk>/<int:year>/<int:month>/<int:day>/<int:hour>/', views.my_page_holiday_add, name='my_page_holiday_add'),
    path('mypage/holiday/add/<int:pk>/<int:year>/<int:month>/<int:day>/', views.my_page_day_add, name='my_page_day_add'),
    path('customer/<int:customer_id>/booking_history/', views.customer_booking_history, name='customer_booking_history'),
    path('analyze_customers/', views.analyze_customers, name='analyze_customers'),
    path('line/webhook/', LineWebhookView.as_view(), name='line-webhook'),
    
]
