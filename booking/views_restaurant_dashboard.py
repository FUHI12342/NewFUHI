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

from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator

from .models import (
    Schedule, Order, OrderItem, Staff, DashboardLayout, DEFAULT_DASHBOARD_LAYOUT,
    ShiftPeriod, ShiftAssignment, ShiftRequest,
)

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
        ctx['title'] = '売上分析'
        ctx['has_permission'] = True
        return ctx


class DashboardLayoutAPIView(APIView):
    """GET/PUT /api/dashboard/layout/ — ダッシュボードレイアウト保存/読込."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)
        try:
            layout = DashboardLayout.objects.get(user=request.user)
            return Response({
                'layout': layout.layout_json,
            })
        except DashboardLayout.DoesNotExist:
            return Response({
                'layout': DEFAULT_DASHBOARD_LAYOUT,
            })

    def put(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)
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


class ReservationStatsAPIView(APIView):
    """GET /api/dashboard/reservations/ — reservation statistics."""

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


class ShiftSummaryAPIView(APIView):
    """GET /api/dashboard/shift-summary/ — shift statistics for dashboard."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        current_month_start = now.replace(day=1).date()

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'period__store': s.store}
            except Exception:
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        # Total assignments for current month
        assignments = ShiftAssignment.objects.filter(
            date__gte=current_month_start,
            **scope,
        )
        total_assignments = assignments.count()
        synced_assignments = assignments.filter(is_synced=True).count()

        # Open periods
        store_scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                store_scope = {'store': s.store}
            except Exception:
                store_scope = {'pk': -1}

        open_periods = ShiftPeriod.objects.filter(
            status='open', **store_scope,
        ).count()

        # Per-staff breakdown
        staff_shifts = (
            assignments
            .values('staff__name')
            .annotate(
                total=Count('id'),
                synced=Count('id', filter=Q(is_synced=True)),
            )
            .order_by('-total')
        )
        staff_list = [
            {'name': s['staff__name'], 'total': s['total'], 'synced': s['synced']}
            for s in staff_shifts
        ]

        return Response({
            'total_assignments': total_assignments,
            'synced_assignments': synced_assignments,
            'open_periods': open_periods,
            'staff_shifts': staff_list,
        })


class DashboardSummaryAPIView(APIView):
    """GET /api/dashboard/summary/ — summary cards for admin dashboard."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        today = now.date()
        month_start = today.replace(day=1)

        scope = _get_store_scope(request)

        # Today's reservations
        today_reservations = Schedule.objects.filter(
            start__date=today, is_cancelled=False, **scope
        ).count()

        # Reservation trend (vs same day last week)
        last_week = today - timedelta(days=7)
        last_week_reservations = Schedule.objects.filter(
            start__date=last_week, is_cancelled=False, **scope
        ).count()
        reservation_trend = today_reservations - last_week_reservations

        # Monthly sales
        order_scope = {}
        if not request.user.is_superuser:
            try:
                staff = request.user.staff
                order_scope = {'order__store': staff.store}
            except Exception:
                order_scope = {}
        monthly_sales = (
            OrderItem.objects
            .filter(order__created_at__date__gte=month_start, **order_scope)
            .aggregate(total=Sum(F('qty') * F('unit_price')))
        )['total'] or 0

        # Today's staff on shift
        shift_scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                shift_scope = {'period__store': s.store}
            except Exception:
                shift_scope = {}
        today_staff = ShiftAssignment.objects.filter(
            date=today, **shift_scope
        ).values('staff').distinct().count()

        # Pending shifts (open periods)
        store_scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                store_scope = {'store': s.store}
            except Exception:
                store_scope = {}
        pending_shifts = ShiftPeriod.objects.filter(
            status='open', **store_scope
        ).count()

        return Response({
            'today_reservations': today_reservations,
            'reservation_trend': reservation_trend,
            'monthly_sales': monthly_sales,
            'today_staff': today_staff,
            'pending_shifts': pending_shifts,
        })


@method_decorator(staff_member_required, name='dispatch')
class CalendarView(TemplateView):
    """FullCalendar-based reservation calendar."""
    template_name = 'admin/booking/calendar.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'カレンダー'
        ctx['has_permission'] = True
        return ctx


class CalendarEventsAPIView(APIView):
    """GET /api/calendar/events/ — events for FullCalendar."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        start = request.GET.get('start')
        end = request.GET.get('end')

        filters = {'is_cancelled': False}
        if start:
            filters['start__gte'] = start
        if end:
            filters['start__lte'] = end

        scope = _get_store_scope(request)
        schedules = Schedule.objects.filter(
            **filters, **scope
        ).select_related('staff')

        events = []
        for s in schedules:
            events.append({
                'id': s.pk,
                'title': f'{s.customer_name or "予約"} - {s.staff.name}',
                'start': s.start.isoformat(),
                'end': s.end.isoformat(),
                'color': '#20AEE5' if not s.is_temporary else '#F79009',
                'url': f'/admin/booking/schedule/{s.pk}/change/',
            })

        return Response(events)


@method_decorator(staff_member_required, name='dispatch')
class GanttView(TemplateView):
    """AirShift-style gantt chart for shift management."""
    template_name = 'admin/booking/gantt.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'シフト管理'
        ctx['has_permission'] = True
        return ctx


class GanttDataAPIView(APIView):
    """GET /api/gantt/data/ — staff x date matrix for gantt chart."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        import calendar as cal_module
        now = timezone.now()
        year = int(request.GET.get('year', now.year))
        month = int(request.GET.get('month', now.month))

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'store': s.store}
            except Exception:
                scope = {'pk': -1}

        staff_list = Staff.objects.filter(**scope).order_by('name')

        # Get assignments for this month
        assignment_scope = {}
        if scope.get('store'):
            assignment_scope = {'period__store': scope['store']}
        assignments = ShiftAssignment.objects.filter(
            date__year=year, date__month=month, **assignment_scope
        ).select_related('staff')

        # Get requests for this month
        request_scope = {}
        if scope.get('store'):
            request_scope = {'period__store': scope['store']}
        requests_qs = ShiftRequest.objects.filter(
            date__year=year, date__month=month, **request_scope
        ).select_related('staff')

        # Build lookup maps
        assignment_map = {}  # (staff_id, date) -> assignment
        for a in assignments:
            key = (a.staff_id, a.date.isoformat())
            assignment_map[key] = {
                'start_hour': a.start_hour,
                'end_hour': a.end_hour,
                'type': 'assignment',
            }

        request_map = {}  # (staff_id, date) -> request
        for r in requests_qs:
            key = (r.staff_id, r.date.isoformat())
            request_map[key] = {
                'start_hour': r.start_hour,
                'end_hour': r.end_hour,
                'preference': r.preference,
                'type': 'request',
            }

        # Build days list
        days_in_month = cal_module.monthrange(year, month)[1]
        days = []
        for d in range(1, days_in_month + 1):
            from datetime import date as date_cls
            dt = date_cls(year, month, d)
            days.append({
                'date': dt.isoformat(),
                'day': d,
                'weekday': dt.strftime('%a'),
                'weekday_num': dt.weekday(),  # 0=Mon, 6=Sun
            })

        # Build staff rows
        staff_rows = []
        for staff in staff_list:
            cells = []
            for day_info in days:
                date_str = day_info['date']
                key = (staff.pk, date_str)
                cell = {'date': date_str}
                if key in assignment_map:
                    cell.update(assignment_map[key])
                elif key in request_map:
                    cell.update(request_map[key])
                else:
                    cell['type'] = 'empty'
                cells.append(cell)
            staff_rows.append({
                'id': staff.pk,
                'name': staff.name,
                'cells': cells,
            })

        return Response({
            'year': year,
            'month': month,
            'days': days,
            'staff': staff_rows,
        })
