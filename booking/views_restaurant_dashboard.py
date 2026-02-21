# booking/views_restaurant_dashboard.py
import logging
from datetime import timedelta

from django.db.models import Count, Sum, Q, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Schedule, Order, OrderItem, Staff

logger = logging.getLogger(__name__)


def _get_store_scope(request):
    """Return store filter kwargs based on user role."""
    if request.user.is_superuser:
        return {}
    try:
        staff = request.user.staff
        return {'store': staff.store}
    except Exception:
        return {'pk': -1}  # No results


class RestaurantDashboardView(TemplateView):
    """Restaurant activity dashboard (admin)."""
    template_name = 'admin/booking/restaurant_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = '飲食店ダッシュボード'
        ctx['has_permission'] = True
        return ctx


class ReservationStatsAPIView(APIView):
    """GET /api/dashboard/reservations/ — reservation statistics."""
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        since = now - timedelta(days=90)

        scope = {}
        if not request.user.is_superuser:
            try:
                staff = request.user.staff
                scope = {'staff__store': staff.store}
            except Exception:
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        # Daily counts (last 90 days)
        daily = (
            Schedule.objects
            .filter(start__gte=since, **scope)
            .annotate(date=TruncDate('start'))
            .values('date')
            .annotate(
                count=Count('id'),
                cancelled=Count('id', filter=Q(is_cancelled=True)),
            )
            .order_by('date')
        )

        daily_list = [{'date': d['date'].isoformat(), 'count': d['count'], 'cancelled': d['cancelled']} for d in daily]

        # Future reservations
        future_count = Schedule.objects.filter(
            start__gte=now, is_cancelled=False, is_temporary=False, **scope
        ).count()

        # Overall cancel rate
        total = Schedule.objects.filter(start__gte=since, **scope).count()
        cancelled = Schedule.objects.filter(start__gte=since, is_cancelled=True, **scope).count()
        cancel_rate = round(cancelled / total, 4) if total > 0 else 0

        return Response({
            'daily': daily_list,
            'future_count': future_count,
            'cancel_rate': cancel_rate,
        })


class SalesStatsAPIView(APIView):
    """GET /api/dashboard/sales/?period=daily — sales statistics."""
    authentication_classes = []
    permission_classes = []

    TRUNC_MAP = {
        'daily': TruncDate,
        'weekly': TruncWeek,
        'monthly': TruncMonth,
    }

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        period = request.GET.get('period', 'daily')
        trunc_fn = self.TRUNC_MAP.get(period, TruncDate)

        scope = {}
        if not request.user.is_superuser:
            try:
                staff = request.user.staff
                scope = {'order__store': staff.store}
            except Exception:
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        since = timezone.now() - timedelta(days=90)

        # Sales trend
        trend = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope)
            .annotate(date=trunc_fn('order__created_at'))
            .values('date')
            .annotate(total=Sum(F('qty') * F('unit_price')))
            .order_by('date')
        )
        trend_list = [{'date': t['date'].isoformat(), 'total': t['total'] or 0} for t in trend]

        # Top 10 products
        top_products = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope)
            .values('product__name')
            .annotate(total=Sum('qty'))
            .order_by('-total')[:10]
        )
        products_list = [{'name': p['product__name'], 'total': p['total']} for p in top_products]

        return Response({'trend': trend_list, 'top_products': products_list})


class StaffPerformanceAPIView(APIView):
    """GET /api/dashboard/staff-performance/ — staff metrics."""
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        since = timezone.now() - timedelta(days=30)

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'store': s.store}
            except Exception:
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        staffs = Staff.objects.filter(**scope)
        result = []
        for s in staffs:
            reservations = Schedule.objects.filter(
                staff=s, start__gte=since, is_cancelled=False, is_temporary=False,
            ).count()
            sales = (
                OrderItem.objects
                .filter(order__schedule__staff=s, order__created_at__gte=since)
                .aggregate(total=Sum(F('qty') * F('unit_price')))
            )['total'] or 0
            result.append({'name': s.name, 'reservations': reservations, 'sales': sales})

        return Response({'staff': result})
