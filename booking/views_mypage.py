"""MyPage views: MyPage, MyPageWithPk, MyPageProfile, MyPageCalendar,
MyPageDayDetail, MyPageSchedule, MyPageScheduleDelete, and related helpers."""
import datetime
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import generic
from django.views.decorators.http import require_POST

from django import forms

from booking.models import Schedule, Staff, Store, StoreScheduleConfig
from .forms import StaffForm

logger = logging.getLogger(__name__)

User = get_user_model()


# ===== Permission mixins (used by MyPage views) =====

class OnlyStaffMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        return staff.user == self.request.user or self.request.user.is_superuser


class OnlyScheduleMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        schedule = get_object_or_404(Schedule, pk=self.kwargs['pk'])
        return schedule.staff.user == self.request.user or self.request.user.is_superuser


class OnlyUserMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return self.kwargs['pk'] == self.request.user.pk or self.request.user.is_superuser


# ===== MyPage views =====

class MyPage(LoginRequiredMixin, generic.TemplateView):
    template_name = 'booking/my_page.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        staff_list = Staff.objects.filter(user=self.request.user).select_related('store').order_by('name')
        context['staff_list'] = staff_list
        context['schedule_list'] = Schedule.objects.filter(
            staff__user=self.request.user,
            start__gte=timezone.now()
        ).order_by('start')
        # キャストのみ予約表示（店舗スタッフは予約を受けない）
        context['has_cast_role'] = staff_list.filter(staff_type='fortune_teller').exists()
        return context


class MyPageWithPk(OnlyUserMixin, generic.TemplateView):
    template_name = 'booking/my_page.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = get_object_or_404(User, pk=self.kwargs['pk'])
        context['staff_list'] = Staff.objects.filter(user__pk=self.kwargs['pk']).order_by('name')
        context['schedule_list'] = Schedule.objects.filter(
            staff__user__pk=self.kwargs['pk'],
            start__gte=timezone.now()
        ).order_by('start')
        return context


class MyPageProfileForm(forms.ModelForm):
    """プロフィール編集フォーム（staff_type に応じてフィールドを制御）"""
    class Meta:
        model = Staff
        fields = ['name', 'thumbnail', 'introduction', 'line_id', 'price']
        widgets = {
            'introduction': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        staff_type = kwargs.pop('staff_type', 'fortune_teller')
        super().__init__(*args, **kwargs)
        # 店舗スタッフは price と introduction を非表示（顧客向け表示なし）
        if staff_type == 'store_staff':
            self.fields.pop('price', None)
            self.fields.pop('introduction', None)


class MyPageProfile(OnlyStaffMixin, generic.UpdateView):
    """マイページ: プロフィール編集"""
    model = Staff
    template_name = 'booking/my_page_profile.html'
    form_class = MyPageProfileForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['staff_type'] = self.object.staff_type
        return kwargs

    def get_success_url(self):
        return reverse('booking:my_page_profile', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff'] = self.object
        context['profile_saved'] = self.request.GET.get('saved') == '1'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        return redirect(f"{self.get_success_url()}?saved=1")


class MyPageCalendar(OnlyStaffMixin, generic.TemplateView):
    """MyPage calendar (delegates to StaffCalendar logic)."""
    template_name = 'booking/my_page_calendar.html'

    def get_context_data(self, **kwargs):
        # Import here to avoid circular import
        from .views import get_time_slots
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

        from django.conf import settings as django_settings
        time_slots, open_h, close_h, duration = get_time_slots(staff.store)

        calendar = {}
        for slot in time_slots:
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
        context['calendar'] = calendar
        context['days'] = days
        context['start_day'] = start_day
        context['end_day'] = end_day
        context['before'] = days[0] - datetime.timedelta(days=7)
        context['next'] = days[-1] + datetime.timedelta(days=1)
        context['today'] = today
        context['public_holidays'] = django_settings.PUBLIC_HOLIDAYS
        context['time_slots'] = time_slots
        context['slot_duration'] = duration
        return context


class MyPageDayDetail(OnlyStaffMixin, generic.TemplateView):
    template_name = 'booking/my_page_day_detail.html'

    def get_context_data(self, **kwargs):
        from .views import get_time_slots
        context = super().get_context_data(**kwargs)
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])

        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')
        date = datetime.date(year=year, month=month, day=day)

        # 動的タイムスロット
        time_slots, open_h, close_h, duration = get_time_slots(staff.store)

        calendar = {}
        for slot in time_slots:
            calendar[slot['label']] = []

        start_time = datetime.datetime.combine(date, datetime.time(hour=open_h, minute=0, second=0))
        end_time = datetime.datetime.combine(date, datetime.time(hour=close_h, minute=0, second=0))

        for schedule in Schedule.objects.filter(staff=staff).exclude(
            Q(start__gt=end_time) | Q(end__lt=start_time)
        ):
            local_dt = timezone.localtime(schedule.start)
            booking_label = f"{local_dt.hour}:{local_dt.minute:02d}"
            if booking_label in calendar:
                calendar[booking_label].append(schedule)

        has_any_schedule = any(schedules for schedules in calendar.values())
        context['calendar'] = calendar
        context['staff'] = staff
        context['has_any_schedule'] = has_any_schedule
        context['time_slots'] = time_slots
        return context


class MyPageSchedule(OnlyScheduleMixin, generic.UpdateView):
    model = Schedule
    fields = ('start', 'end', 'customer_name', 'memo', 'price', 'is_temporary', 'is_cancelled')
    success_url = reverse_lazy('booking:my_page')


class MyPageScheduleDelete(OnlyScheduleMixin, generic.DeleteView):
    model = Schedule
    success_url = reverse_lazy('booking:my_page')


@login_required
@require_POST
def my_page_holiday_add(request, pk, year, month, day, hour):
    staff = get_object_or_404(Staff, pk=pk)
    if staff.user == request.user or request.user.is_superuser:
        start = datetime.datetime(year=year, month=month, day=day, hour=hour)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, is_temporary=False, price=0)
        return redirect('booking:my_page_day_detail', pk=pk, year=year, month=month, day=day)
    raise PermissionDenied


@login_required
@require_POST
def my_page_day_add(request, pk, year, month, day):
    staff = get_object_or_404(Staff, pk=pk)
    if staff.user == request.user or request.user.is_superuser:
        config = getattr(staff.store, 'schedule_config', None)
        open_h = config.open_hour if config else 9
        close_h = config.close_hour if config else 17
        for num in range(close_h - open_h):
            start = datetime.datetime(year=year, month=month, day=day, hour=open_h + num)
            end = datetime.datetime(year=year, month=month, day=day, hour=open_h + num + 1)
            Schedule.objects.create(staff=staff, start=start, end=end, is_temporary=False, price=0)
        return redirect('booking:my_page_day_detail', pk=pk, year=year, month=month, day=day)
    raise PermissionDenied


@login_required
@require_POST
def my_page_day_delete(request, pk, year, month, day):
    staff = get_object_or_404(Staff, pk=pk)
    if staff.user == request.user or request.user.is_superuser:
        config = getattr(staff.store, 'schedule_config', None)
        open_h = config.open_hour if config else 9
        close_h = config.close_hour if config else 17
        start = datetime.datetime(year=year, month=month, day=day, hour=open_h)
        end = datetime.datetime(year=year, month=month, day=day, hour=close_h)
        # 顧客予約を保護: customer_nameが空のスタッフ作成ブロックのみ削除
        Schedule.objects.filter(
            staff=staff, start__gte=start, end__lte=end,
            customer_name__isnull=True, price=0
        ).delete()
        return redirect('booking:my_page_day_detail', pk=pk, year=year, month=month, day=day)
    raise PermissionDenied


@login_required
def upload_file(request):
    if not request.user.is_staff:
        raise PermissionDenied
    if request.method == 'POST':
        form = StaffForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect('/success/url/')
    else:
        form = StaffForm()
    return render(request, 'upload.html', {'form': form})
