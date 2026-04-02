"""Shifts admin: ShiftPeriod, ShiftRequest, ShiftAssignment, ShiftChangeLog,
ShiftVacancy, ShiftSwapRequest, ShiftTemplate, ShiftPublishHistory,
StoreClosedDate, ShiftStaffRequirement, ShiftStaffRequirementOverride."""
import logging

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

from ..admin_site import custom_site
from ..models import (
    Staff,
    ShiftPeriod, ShiftRequest, ShiftAssignment,
    ShiftTemplate, ShiftPublishHistory, ShiftChangeLog,
    StoreClosedDate, ShiftStaffRequirement, ShiftStaffRequirementOverride,
    ShiftVacancy, ShiftSwapRequest,
)
from .helpers import _is_owner_or_super


class ShiftRequestInline(admin.TabularInline):
    model = ShiftRequest
    extra = 0
    readonly_fields = ('staff', 'date', 'start_hour', 'end_hour', 'preference')


class ShiftAssignmentInline(admin.TabularInline):
    model = ShiftAssignment
    extra = 0
    fields = ('staff', 'date', 'start_hour', 'end_hour', 'start_time', 'end_time', 'store', 'color', 'note')


class ShiftPeriodAdmin(admin.ModelAdmin):
    list_display = ('store', 'year_month', 'deadline', 'status', 'request_count', 'assignment_count', 'created_by')
    actions = ['run_auto_schedule', 'approve_and_sync']

    def request_count(self, obj):
        return obj.requests.count()

    request_count.short_description = _('希望数')

    def assignment_count(self, obj):
        return obj.assignments.count()

    assignment_count.short_description = _('確定数')

    @admin.action(description=_('自動スケジューリング実行'))
    def run_auto_schedule(self, request, queryset):
        from booking.services.shift_scheduler import auto_schedule
        total = 0
        for period in queryset:
            count = auto_schedule(period)
            total += count
        self.message_user(request, f'{total} 件のシフトを自動割り当てしました。')

    @admin.action(description=_('承認してScheduleに同期'))
    def approve_and_sync(self, request, queryset):
        from booking.services.shift_scheduler import sync_assignments_to_schedule
        from booking.services.shift_notifications import notify_shift_approved
        total = 0
        for period in queryset:
            count = sync_assignments_to_schedule(period)
            total += count
            notify_shift_approved(period)
            # SNS自動投稿: シフト公開をトリガー
            try:
                from booking.tasks import task_post_shift_published
                task_post_shift_published.delay(period.id)
            except Exception as e:
                logger.warning("Failed to queue social posting: %s", e)
        self.message_user(request, f'{total} 件のScheduleを同期しました。')


class ShiftRequestAdmin(admin.ModelAdmin):
    list_display = ('period', 'staff', 'date', 'start_hour', 'end_hour', 'preference')

    search_fields = ('staff__name',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            if staff.is_store_manager:
                return qs.filter(period__store=staff.store)
            return qs.filter(staff=staff)
        except Staff.DoesNotExist:
            return qs.none()


class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ('period', 'staff', 'date', 'start_hour', 'end_hour', 'store', 'is_synced')
    list_filter = ('store',)

    search_fields = ('staff__name',)


class ShiftChangeLogAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'changed_by', 'changed_at', 'change_type', 'reason')
    list_filter = ('change_type',)
    readonly_fields = ('assignment', 'changed_by', 'changed_at', 'change_type', 'old_values', 'new_values', 'reason')
    search_fields = ('assignment__staff__name', 'reason')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        from ..admin_site import get_user_role, _get_allowed_models_for_role
        role = get_user_role(request)
        if role == 'none':
            return False
        allowed = _get_allowed_models_for_role(role)
        if allowed is None:
            return True
        return 'shiftchangelog' in allowed

    def has_module_permission(self, request):
        return self.has_view_permission(request)


class ShiftVacancyAdmin(admin.ModelAdmin):
    list_display = ('period', 'store', 'date', 'start_hour', 'end_hour', 'staff_type', 'required_count', 'assigned_count', 'status')
    list_filter = ('status', 'staff_type')
    search_fields = ('store__name',)


class ShiftSwapRequestAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'request_type', 'requested_by', 'cover_staff', 'status', 'reviewed_by', 'created_at')
    list_filter = ('status', 'request_type')
    search_fields = ('requested_by__name', 'reason')


class ShiftTemplateAdmin(admin.ModelAdmin):
    list_display = ('store', 'name', 'start_time', 'end_time', 'color', 'is_active', 'sort_order')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('name', 'store__name')
    list_filter = ('store', 'is_active')


class ShiftPublishHistoryAdmin(admin.ModelAdmin):
    list_display = ('period', 'published_by', 'published_at', 'assignment_count')
    readonly_fields = ('published_at',)
    search_fields = ('period__store__name',)


class StoreClosedDateAdmin(admin.ModelAdmin):
    list_display = ('store', 'date', 'reason', 'created_at')
    list_filter = ('store',)
    search_fields = ('reason',)
    ordering = ('-date',)


class ShiftStaffRequirementAdmin(admin.ModelAdmin):
    list_display = ('store', 'get_day_display', 'get_staff_type_display', 'required_count')
    list_filter = ('store', 'day_of_week', 'staff_type')
    list_editable = ('required_count',)

    @admin.display(description=_('曜日'), ordering='day_of_week')
    def get_day_display(self, obj):
        return obj.get_day_of_week_display()

    @admin.display(description=_('種別'), ordering='staff_type')
    def get_staff_type_display(self, obj):
        return obj.get_staff_type_display()

    actions = ['bulk_create_all_days']

    @admin.action(description=_('全曜日×全種別のデフォルト設定を一括作成'))
    def bulk_create_all_days(self, request, queryset):
        from ..models import STAFF_TYPE_CHOICES
        stores = set(queryset.values_list('store_id', flat=True))
        created = 0
        for store_id in stores:
            for day in range(7):
                for st_code, _label in STAFF_TYPE_CHOICES:
                    _, was_created = ShiftStaffRequirement.objects.get_or_create(
                        store_id=store_id,
                        day_of_week=day,
                        staff_type=st_code,
                        defaults={'required_count': 1},
                    )
                    if was_created:
                        created += 1
        self.message_user(request, f'{created}件の設定を作成しました', messages.SUCCESS)


class ShiftStaffRequirementOverrideAdmin(admin.ModelAdmin):
    list_display = ('store', 'date', 'get_staff_type_display', 'required_count', 'reason')
    list_filter = ('store', 'staff_type')
    list_editable = ('required_count',)
    date_hierarchy = 'date'

    @admin.display(description=_('種別'), ordering='staff_type')
    def get_staff_type_display(self, obj):
        return obj.get_staff_type_display()


# Registration
custom_site.register(ShiftPeriod, ShiftPeriodAdmin)
custom_site.register(ShiftRequest, ShiftRequestAdmin)
custom_site.register(ShiftAssignment, ShiftAssignmentAdmin)
custom_site.register(ShiftChangeLog, ShiftChangeLogAdmin)
custom_site.register(ShiftVacancy, ShiftVacancyAdmin)
custom_site.register(ShiftSwapRequest, ShiftSwapRequestAdmin)
custom_site.register(ShiftTemplate, ShiftTemplateAdmin)
custom_site.register(ShiftPublishHistory, ShiftPublishHistoryAdmin)
custom_site.register(StoreClosedDate, StoreClosedDateAdmin)
custom_site.register(ShiftStaffRequirement, ShiftStaffRequirementAdmin)
custom_site.register(ShiftStaffRequirementOverride, ShiftStaffRequirementOverrideAdmin)
