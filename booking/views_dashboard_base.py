# booking/views_dashboard_base.py
"""Dashboard shared utilities: auth mixin, helpers, base view."""
import logging
from datetime import timedelta

from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, TruncYear
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import (
    Staff, DashboardLayout, DEFAULT_DASHBOARD_LAYOUT, SiteSettings,
)

logger = logging.getLogger(__name__)

PERIOD_TRUNC_MAP = {
    'daily': TruncDate,
    'weekly': TruncWeek,
    'monthly': TruncMonth,
    'yearly': TruncYear,
}


def _get_since_for_period(period, default_days=90, days_override=None):
    """Return appropriate 'since' datetime based on period type.

    If *days_override* is provided (and is not None), it takes precedence
    over the period-based default so callers can pass an explicit window.
    """
    if days_override is not None:
        return timezone.now() - timedelta(days=days_override)
    if period == 'yearly':
        return timezone.now() - timedelta(days=1095)  # 3 years
    return timezone.now() - timedelta(days=default_days)


def _parse_channel_filter(request, prefix='order__'):
    """Parse channel query param and return filter kwargs."""
    ch = request.GET.get('channel', '')
    if ch:
        channels = [c.strip() for c in ch.split(',') if c.strip()]
        if channels:
            return {f'{prefix}channel__in': channels}
    return {}


def _clamp_int(value, default, lo=1, hi=365):
    """Parse and clamp an integer query parameter."""
    try:
        return max(lo, min(int(value), hi))
    except (TypeError, ValueError):
        return default


class AdminSidebarMixin:
    """Jazzminサイドバー表示に必要なコンテキストを注入"""
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from booking.admin_site import custom_site
        ctx['available_apps'] = custom_site.get_app_list(self.request)
        ctx['has_permission'] = True
        return ctx


class DashboardAuthMixin:
    """Common authentication and store scoping for dashboard API views.

    Usage in subclass .get() methods:
        store, err = self.get_user_store(request)
        if err:
            return err
        scope = {'order__store': store} if store else {}
    """

    def get_user_store(self, request):
        """Return (store_or_None, error_response_or_None).

        - Superuser: (None, None) meaning no store filter
        - Staff with store: (store, None)
        - Not authenticated / no store: (None, error_response)
        """
        if not request.user.is_authenticated:
            return None, Response(
                {'detail': 'login required'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if request.user.is_superuser:
            return None, None
        try:
            staff = request.user.staff
            return staff.store, None
        except (Staff.DoesNotExist, AttributeError):
            return None, Response(
                {'detail': 'no store access'},
                status=status.HTTP_403_FORBIDDEN,
            )

    def build_scope(self, store, prefix='store'):
        """Build scope dict from store.  Returns {} for superusers (store=None)."""
        if store is None:
            return {}
        return {prefix: store}


class RestaurantDashboardView(AdminSidebarMixin, TemplateView):
    """Restaurant activity dashboard (admin)."""
    template_name = 'admin/booking/restaurant_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = '売上分析'
        ctx['has_permission'] = True
        settings = SiteSettings.load()
        ctx['show_ec'] = settings.show_admin_ec_shop
        ctx['show_pos'] = settings.show_admin_pos
        ctx['show_reservation'] = settings.show_admin_reservation
        ctx['staff_label'] = settings.staff_label or 'スタッフ'
        return ctx


class DashboardLayoutAPIView(DashboardAuthMixin, APIView):
    """GET/PUT /api/dashboard/layout/ — ダッシュボードレイアウト保存/読込."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)
        if not request.user.is_staff:
            return Response({'detail': 'staff access required'}, status=status.HTTP_403_FORBIDDEN)
        try:
            layout = DashboardLayout.objects.get(user=request.user)
            return Response({'layout': layout.layout_json})
        except DashboardLayout.DoesNotExist:
            return Response({'layout': DEFAULT_DASHBOARD_LAYOUT})

    def put(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)
        if not request.user.is_staff:
            return Response({'detail': 'staff access required'}, status=status.HTTP_403_FORBIDDEN)
        layout_data = request.data.get('layout')
        obj, created = DashboardLayout.objects.get_or_create(
            user=request.user,
            defaults={
                'layout_json': layout_data if layout_data is not None else DEFAULT_DASHBOARD_LAYOUT,
            }
        )
        if not created:
            if layout_data is not None:
                obj.layout_json = layout_data
            obj.save()
        return Response({'ok': True})
