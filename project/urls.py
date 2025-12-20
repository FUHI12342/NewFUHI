"""project URL Configuration"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from booking import views as booking_views
from booking.admin_site import custom_site
import booking.admin

urlpatterns = [
    # ★ 管理画面配下の MQ9 グラフ
    # 例: http://127.0.0.1:8000/admin/iot/mq9/?device=Ace1
    path(
        "admin/iot/mq9/",
        custom_site.admin_view(booking_views.IoTMQ9GraphView.as_view()),
        name="admin_iot_mq9",
    ),

    # 通常の管理画面
    path("admin/", custom_site.urls),

    # booking アプリ配下
    path("", include("booking.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)