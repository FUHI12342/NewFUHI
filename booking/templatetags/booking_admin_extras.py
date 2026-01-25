# booking/templatetags/booking_admin_extras.py
from django import template

from booking.models import Schedule, IoTEvent

register = template.Library()


@register.simple_tag
def latest_bookings(limit=5):
    """
    予約（Schedule）を開始時間の新しい順に limit 件返す
    """
    return Schedule.objects.order_by("-start")[:limit]


@register.simple_tag
def latest_iot_events(limit=5):
    """
    IoTEvent を作成日時の新しい順に limit 件返す
    """
    return IoTEvent.objects.order_by("-created_at")[:limit]