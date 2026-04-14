"""booking.views -- Core helpers, small views, and backward-compatible
re-exports from split view modules.

Split modules:
  views_iot_api.py     -- IoT API views
  views_menu.py        -- Menu / Order / Inbound views
  views_shop.py        -- EC shop views
  views_table.py       -- Table order views
  views_booking.py     -- LINE auth, booking flow, payment
  views_mypage.py      -- MyPage views
  views_shift_submit.py -- Staff shift submission views
"""
from __future__ import absolute_import, unicode_literals

import datetime
import logging
from datetime import timedelta

import pytz

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import generic, View

from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.models import (
    Store,
    Staff,
    Schedule,
    Timer,
    UserSerializer,
    SiteSettings,
    HeroBanner,
    HomepageCustomBlock,
    Notice,
    StoreScheduleConfig,
    ShiftPeriod,
)

logger = logging.getLogger(__name__)

User = get_user_model()


# ===== Store Schedule Config Helpers =====

def get_time_slots(store):
    """店舗のスケジュール設定に基づいてタイムスロットを生成"""
    try:
        config = store.schedule_config
    except StoreScheduleConfig.DoesNotExist:
        config = None

    open_h = config.open_hour if config else 9
    close_h = config.close_hour if config else 21
    duration = config.slot_duration if config else 60

    slots = []
    current = open_h * 60  # 分に変換
    while current + duration <= close_h * 60:
        slots.append({
            'hour': current // 60,
            'minute': current % 60,
            'total_minutes': current,
            'label': f"{current // 60}:{current % 60:02d}",
        })
        current += duration
    return slots, open_h, close_h, duration


def get_hour_range(store):
    """店舗の営業時間範囲を(start_hour, end_hour)で返す（既存コードとの互換用）"""
    try:
        config = store.schedule_config
    except StoreScheduleConfig.DoesNotExist:
        config = None
    open_h = config.open_hour if config else 9
    close_h = config.close_hour if config else 21
    return open_h, close_h


def get_or_create_shift_period(store, year, month, staff=None):
    """月指定で ShiftPeriod を自動取得/作成する（自由入力モード用）"""
    ym = datetime.date(year, month, 1)
    period, _ = ShiftPeriod.objects.get_or_create(
        store=store, year_month=ym,
        defaults={'status': 'open', 'created_by': staff},
    )
    return period


# ===== Small core views =====


class LoginRedirectView(View):
    """ログイン後のスマートリダイレクト: is_staff -> /admin/, それ以外 -> store_list"""
    def get(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect(reverse('admin:index'))
        return redirect(reverse('booking:store_list'))


class Index(generic.RedirectView):
    pattern_name = 'booking:booking_top'


class HelpView(generic.TemplateView):
    template_name = 'booking/help.html'


def LINETimerView(request, user_id):
    timer, created = Timer.objects.get_or_create(
        user_id=user_id,
        defaults={'start_time': timezone.now()}
    )
    if not created:
        timer.start_time = timezone.now()
        timer.save()

    timer.end_time = timer.start_time + timedelta(minutes=60)
    timer.save()

    context = {'end_time': timer.end_time}
    return render(request, 'booking/timer.html', context)


def get_end_time(request):
    end_time = timezone.now() + timedelta(hours=1)
    return JsonResponse({'time': end_time.isoformat()})


def get_current_time(request):
    return JsonResponse({'time': timezone.now().isoformat()})


def get_reservation_times(request, pk):
    schedule = get_object_or_404(Schedule, pk=pk)
    return JsonResponse({'startTime': schedule.start.isoformat(), 'endTime': schedule.end.isoformat()})


def get_reservation(request, pk):
    """Alias for get_reservation_times (kept for URL compatibility)."""
    return get_reservation_times(request, pk)


# ===== Booking top / listing views =====

class BookingTopPage(generic.TemplateView):
    """トップページ: 3つの入口 (店舗/占い師/日付)"""
    template_name = 'booking/booking_top.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stores'] = Store.objects.all().order_by('name')

        # SiteSettings
        site_settings = SiteSettings.load()
        context['site_settings'] = site_settings

        # ヒーローバナー
        if site_settings.show_hero_banner:
            context['hero_banners'] = HeroBanner.objects.filter(is_active=True).order_by('sort_order')

        # カスタムブロック (HomepageCustomBlock)
        active_blocks = HomepageCustomBlock.objects.filter(is_active=True)
        context['custom_blocks_above'] = active_blocks.filter(position='above_cards')
        context['custom_blocks_below'] = active_blocks.filter(position='below_cards')

        # 予約ランキング（直近30日の予約数上位）
        if site_settings.show_ranking:
            from django.db.models import Count
            since = timezone.now() - timedelta(days=30)
            context['ranking'] = (
                Staff.objects.filter(
                    schedule__start__gte=since,
                    schedule__is_cancelled=False,
                    schedule__is_temporary=False,
                    staff_type='fortune_teller',
                )
                .annotate(reservation_count=Count('schedule'))
                .order_by('-reservation_count')
                [:site_settings.ranking_limit]
            )

            # 人気店舗ランキング（直近30日の予約数でStore集計）
            context['store_ranking'] = (
                Store.objects.filter(
                    staff__schedule__start__gte=since,
                    staff__schedule__is_cancelled=False,
                    staff__schedule__is_temporary=False,
                )
                .annotate(reservation_count=Count('staff__schedule'))
                .order_by('-reservation_count')
                [:site_settings.ranking_limit]
            )

            # おすすめ（is_recommended=True の占い師+店舗）
            context['recommended_staff'] = Staff.objects.filter(
                is_recommended=True, staff_type='fortune_teller',
            ).select_related('store')[:site_settings.ranking_limit]

            context['recommended_stores'] = Store.objects.filter(
                is_recommended=True,
            )[:site_settings.ranking_limit]

        # セクションベースレイアウト
        from booking.services.page_layout_service import get_page_sections
        store = Store.objects.first()
        context['page_sections'] = get_page_sections(store, 'home')

        return context


class AllFortuneTellerList(generic.ListView):
    """全店舗横断の占い師一覧 (staff_type='fortune_teller' のみ)"""
    model = Staff
    template_name = 'booking/all_fortune_tellers.html'
    context_object_name = 'fortune_tellers'
    ordering = 'name'

    def get_queryset(self):
        return super().get_queryset().filter(
            staff_type='fortune_teller'
        ).select_related('store', 'store__schedule_config')


class DateFirstCalendar(generic.TemplateView):
    """日付優先カレンダー: 日付を選ぶ -> その日空きのある占い師一覧 (全店舗横断)"""
    template_name = 'booking/date_first_calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.date.today()

        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')

        if year and month and day:
            selected_date = datetime.date(year=year, month=month, day=day)
        else:
            selected_date = None

        # 14日分のカレンダー
        calendar_days = [today + datetime.timedelta(days=d) for d in range(14)]
        context['calendar_days'] = calendar_days
        context['selected_date'] = selected_date
        context['today'] = today

        if selected_date:
            # 全占い師のスケジュールをバルク取得して N+1 回避
            fortune_tellers = Staff.objects.filter(
                staff_type='fortune_teller'
            ).select_related('store')

            # 選択日の既存予約を一括取得
            booked = Schedule.objects.filter(
                staff__staff_type='fortune_teller',
                start__date=selected_date,
                is_cancelled=False,
            ).values_list('staff_id', 'start')

            booked_set = set()
            for staff_id, start in booked:
                local_dt = timezone.localtime(start) if timezone.is_aware(start) else start
                booked_set.add((staff_id, local_dt.hour, local_dt.minute))

            available_tellers = []
            for teller in fortune_tellers:
                time_slots_list, open_h, close_h, duration = get_time_slots(teller.store)
                free_slots = []
                for slot in time_slots_list:
                    if (teller.id, slot['hour'], slot['minute']) not in booked_set:
                        free_slots.append(slot)
                if free_slots:
                    available_tellers.append({
                        'staff': teller,
                        'free_slots': free_slots,
                    })

            context['available_tellers'] = available_tellers

            # 祝日コンテキスト
            context['public_holidays'] = settings.PUBLIC_HOLIDAYS

        return context


class StoreList(generic.ListView):
    model = Store
    ordering = 'name'


class StoreAccessView(generic.DetailView):
    model = Store
    template_name = 'booking/store_access.html'
    context_object_name = 'store'


class StaffList(generic.ListView):
    model = Staff
    ordering = 'name'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['store'] = self.store
        # OGメタタグ用: サムネイル付きスタッフの最初の画像URL
        staff_list = context.get('staff_list') or self.object_list
        for staff in staff_list:
            if staff.thumbnail:
                context['first_staff_thumb'] = staff.thumbnail.url
                break
        return context

    def get_queryset(self):
        from booking.models.shifts import ShiftAssignment
        self.store = get_object_or_404(Store, pk=self.kwargs['pk'])
        today = datetime.date.today()

        # 1. 主店舗がこの店舗のキャスト
        primary_staff_ids = set(
            Staff.objects.filter(store=self.store, staff_type='fortune_teller')
            .values_list('id', flat=True)
        )

        # 2. 今日のシフトがこの店舗に入っているキャスト
        shift_staff_ids = set(
            ShiftAssignment.objects.filter(
                store=self.store, date=today,
            ).values_list('staff_id', flat=True)
        )

        # 3. 主店舗がここだが、今日は他店舗にシフトが入っている → 除外
        away_staff_ids = set(
            ShiftAssignment.objects.filter(
                staff__store=self.store, date=today,
            ).exclude(store=self.store).exclude(store__isnull=True)
            .values_list('staff_id', flat=True)
        )

        # (主店舗 - 他店舗出勤) + シフト出勤
        visible_ids = (primary_staff_ids - away_staff_ids) | shift_staff_ids

        return Staff.objects.filter(
            id__in=visible_ids, staff_type='fortune_teller'
        ).select_related('store')


class StaffCalendar(generic.TemplateView):
    template_name = 'booking/calendar.html'

    def get_context_data(self, **kwargs):
        from django.db.models import Q
        context = super().get_context_data(**kwargs)
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        today = datetime.date.today()

        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')
        base_date = datetime.date(year=year, month=month, day=day) if (year and month and day) else today

        days = [base_date + datetime.timedelta(days=d) for d in range(7)]
        start_day = days[0]
        end_day = days[-1]

        # 表示元店舗（store_idクエリパラメータがある場合はその店舗の設定を使用）
        display_store_id = self.request.GET.get('store_id')
        if display_store_id:
            display_store = Store.objects.filter(pk=display_store_id).first() or staff.store
        else:
            display_store = staff.store

        # 動的タイムスロット（表示元店舗の設定を使用）
        time_slots_list, open_h, close_h, duration = get_time_slots(display_store)

        calendar = {}
        for slot in time_slots_list:
            slot_key = slot['label']
            calendar[slot_key] = {d: True for d in days}

        start_time = datetime.datetime.combine(start_day, datetime.time(hour=open_h, minute=0, second=0))
        end_time = datetime.datetime.combine(end_day, datetime.time(hour=close_h, minute=0, second=0))

        for schedule in (
            Schedule.objects.filter(staff=staff, is_cancelled=False)
            .exclude(Q(start__gt=end_time) | Q(end__lt=start_time))
        ):
            local_dt = timezone.localtime(schedule.start)
            booking_date = local_dt.date()
            booking_label = f"{local_dt.hour}:{local_dt.minute:02d}"
            if booking_label in calendar and booking_date in calendar[booking_label]:
                calendar[booking_label][booking_date] = 'Temp' if schedule.is_temporary else 'Booked'

        context['staff'] = staff
        context['display_store'] = display_store
        context['calendar'] = calendar
        context['days'] = days
        context['start_day'] = start_day
        context['end_day'] = end_day
        context['before'] = days[0] - datetime.timedelta(days=7)
        context['next'] = days[-1] + datetime.timedelta(days=1)
        context['today'] = today
        context['public_holidays'] = settings.PUBLIC_HOLIDAYS
        context['time_slots'] = time_slots_list
        context['slot_duration'] = duration
        return context


# ===== Booking form =====

from django import forms  # noqa: E402

class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = []


class PreBooking(generic.CreateView):
    model = Schedule
    form_class = ScheduleForm
    template_name = 'booking/booking.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff'] = get_object_or_404(Staff, pk=self.kwargs['pk'])
        return context

    def form_valid(self, form):
        from django.contrib import messages as _messages
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        price = staff.price

        year = int(self.kwargs.get('year'))
        month = int(self.kwargs.get('month'))
        day = int(self.kwargs.get('day'))
        hour = int(self.kwargs.get('hour'))
        minute = int(self.kwargs.get('minute', 0))

        tz = pytz.timezone(settings.TIME_ZONE)
        start = datetime.datetime(year=year, month=month, day=day, hour=hour, minute=minute)

        # 動的コマ長
        _, _, _, duration = get_time_slots(staff.store)
        end = start + datetime.timedelta(minutes=duration)

        if Schedule.objects.filter(staff=staff, start=start, is_cancelled=False).exists():
            _messages.error(self.request, 'すみません、入れ違いで予約がありました。別の日時はどうですか。')
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(reverse('booking:staff_calendar', args=[staff.id]))

        schedule = form.save(commit=False)
        schedule.staff = staff
        schedule.start = start
        schedule.end = end
        schedule.is_temporary = True
        schedule.price = price
        schedule.temporary_booked_at = datetime.datetime.now(tz)

        # 予約店舗を設定（store_idクエリパラメータがあればその店舗、なければ主店舗）
        store_id = self.request.GET.get('store_id')
        if store_id:
            booking_store = Store.objects.filter(pk=store_id).first()
            schedule.store = booking_store or staff.store
        else:
            schedule.store = staff.store

        tz_jst = pytz.timezone('Asia/Tokyo')
        self.request.session['temporary_booking'] = {
            'reservation_number': str(schedule.reservation_number),
            'start': start.isoformat(),
            'start_display': start.astimezone(tz_jst).strftime('%Y年%m月%d日 %H:%M'),
            'end': end.isoformat(),
            'price': price,
            'is_temporary': schedule.is_temporary,
            'staff_id': staff.id,
            'staff_name': staff.name,
            'store_id': schedule.store_id,
        }

        return redirect('booking:channel_choice')


class BookingChannelChoice(generic.TemplateView):
    """LINE or メール選択画面"""
    template_name = 'booking/channel_choice.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['booking'] = self.request.session.get('temporary_booking')
        context['free_booking_mode'] = SiteSettings.load().free_booking_mode
        return context


# ===== Static pages =====

class PrivacyPolicyView(generic.TemplateView):
    template_name = 'booking/privacy_policy.html'


class TokushohoView(generic.TemplateView):
    template_name = 'booking/tokushoho.html'


# ===== Notice views =====

class NoticeListView(generic.ListView):
    """公開済みお知らせの一覧ページ"""
    model = Notice
    template_name = 'booking/notice_list.html'
    context_object_name = 'notices'
    paginate_by = 12

    def get_queryset(self):
        return Notice.objects.filter(is_published=True).order_by('-updated_at')


class NoticeDetailView(generic.DetailView):
    """お知らせ詳細ページ（slug ベース）"""
    model = Notice
    template_name = 'booking/notice_detail.html'
    context_object_name = 'notice'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Notice.objects.filter(is_published=True)


# =============================================================
# Re-exports for backward compatibility
# =============================================================

# views_iot_api.py
from .views_iot_api import (  # noqa: F401, E402
    IoTEventAPIView,
    IoTConfigAPIView,
    IRSendAPIView,
    IoTMQ9GraphView,
    IoTSensorDashboardView,
)

# views_menu.py
from .views_menu import (  # noqa: F401, E402
    CustomerMenuView,
    CustomerMenuJsonAPIView,
    ProductAlternativesAPIView,
    OrderCreateAPIView,
    OrderStatusAPIView,
    StaffMarkServedAPIView,
    InboundQRView,
    InboundApplyAPIView,
    OrderItemStatusUpdateAPIView,
)

# views_shop.py
from .views_shop import (  # noqa: F401, E402
    ShopView,
    CartView,
    CartAddAPIView,
    CartUpdateAPIView,
    CartRemoveAPIView,
    ShopCheckoutView,
    ShopConfirmView,
)

# views_table.py
from .views_table import (  # noqa: F401, E402
    TableMenuView,
    TableCartView,
    TableOrderView,
    TableOrderHistoryView,
    TableCheckoutView,
    TableCartAddAPI,
    TableCartUpdateAPI,
    TableCartRemoveAPI,
    TableOrderCreateAPI,
    TableOrderStatusAPI,
)

# views_booking.py
from .views_booking import (  # noqa: F401, E402
    LineEnterView,
    LineCallbackView,
    PayingSuccessView,
    EmailBookingForm,
    EmailBookingView,
    EmailVerifyView,
    CancelReservationView,
    CustomerCancelView,
    CustomerCancelConfirmView,
    ReservationQRView,
    CheckinScanView,
    CheckinAPIView,
    coiney_webhook,
    process_payment,
    _build_access_lines,
)

# views_mypage.py
from .views_mypage import (  # noqa: F401, E402
    MyPage,
    MyPageWithPk,
    MyPageProfileForm,
    MyPageProfile,
    MyPageCalendar,
    MyPageDayDetail,
    MyPageSchedule,
    MyPageScheduleDelete,
    my_page_holiday_add,
    my_page_day_add,
    my_page_day_delete,
    upload_file,
)

# views_shift_submit.py
from .views_shift_submit import (  # noqa: F401, E402
    StaffShiftCalendarView,
    StaffShiftSubmitView,
    StaffShiftSubmitByMonthView,
    StaffShiftBulkRequestAPIView,
    StaffShiftCopyWeekAPIView,
)

# views_property.py
from booking.views_property import PropertyListView, PropertyDetailView  # noqa: F401, E402
