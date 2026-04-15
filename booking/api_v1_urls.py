# booking/api_v1_urls.py
# /api/v1/ 用 URLconf — booking/api_urls.py の全パターンを api_v1 名前空間で公開する。
# 既存の /api/ (app_name='booking_api') とは別の名前空間を持つため、
# reverse('booking_api:...') の解決には影響しない。
from booking.api_urls import urlpatterns  # noqa: F401

app_name = 'api_v1'
