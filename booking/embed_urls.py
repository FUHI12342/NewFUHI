"""Embed URL patterns — iframe埋め込み用（i18n_patterns の外に配置）"""
from django.urls import path
from .views_embed import EmbedBookingView, EmbedShiftView, EmbedDemoView

app_name = 'embed'

urlpatterns = [
    path('demo/', EmbedDemoView.as_view(), name='embed_demo'),
    path('booking/<int:store_id>/', EmbedBookingView.as_view(), name='embed_booking'),
    path('shift/<int:store_id>/', EmbedShiftView.as_view(), name='embed_shift'),
]
