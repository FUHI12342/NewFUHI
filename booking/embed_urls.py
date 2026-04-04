"""Embed URL patterns — iframe埋め込み用（i18n_patterns の外に配置）"""
from django.urls import path
from .views_embed import (
    EmbedBookingView, EmbedShiftView, EmbedDemoView,
    EmbedStaffCalendarView, EmbedPreBookingView,
    EmbedChannelChoiceView, EmbedEmailBookingView,
    EmbedEmailVerifyView, EmbedLineRedirectView,
)

app_name = 'embed'

urlpatterns = [
    path('demo/', EmbedDemoView.as_view(), name='embed_demo'),
    path('booking/<int:store_id>/', EmbedBookingView.as_view(), name='embed_booking'),
    path('shift/<int:store_id>/', EmbedShiftView.as_view(), name='embed_shift'),

    # iframe内予約フロー
    path('calendar/<int:store_id>/<int:pk>/',
         EmbedStaffCalendarView.as_view(), name='embed_calendar'),
    path('calendar/<int:store_id>/<int:pk>/<int:year>/<int:month>/<int:day>/',
         EmbedStaffCalendarView.as_view(), name='embed_calendar_date'),
    path('prebooking/<int:store_id>/<int:pk>/<int:year>/<int:month>/<int:day>/<int:hour>/',
         EmbedPreBookingView.as_view(), name='embed_prebooking'),
    path('prebooking/<int:store_id>/<int:pk>/<int:year>/<int:month>/<int:day>/<int:hour>/<int:minute>/',
         EmbedPreBookingView.as_view(), name='embed_prebooking_minute'),
    path('channel-choice/<str:embed_token>/',
         EmbedChannelChoiceView.as_view(), name='embed_channel_choice'),
    path('email/<str:embed_token>/',
         EmbedEmailBookingView.as_view(), name='embed_email'),
    path('email/<str:embed_token>/verify/',
         EmbedEmailVerifyView.as_view(), name='embed_email_verify'),
    path('line/<str:embed_token>/',
         EmbedLineRedirectView.as_view(), name='embed_line'),
]
