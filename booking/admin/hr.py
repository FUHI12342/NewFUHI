"""HR admin: Employment, WorkAttendance, Payroll, Salary, TableSeat,
PaymentMethod, AttendanceTOTP, AttendanceStamp."""
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from ..admin_site import custom_site
from ..models import (
    Staff,
    EmploymentContract, WorkAttendance,
    PayrollPeriod, PayrollEntry, PayrollDeduction,
    SalaryStructure, TableSeat, PaymentMethod,
    AttendanceTOTPConfig, AttendanceStamp,
)
from .helpers import _is_owner_or_super


class EmploymentContractAdmin(admin.ModelAdmin):
    list_display = ('staff', 'employment_type', 'pay_type', 'hourly_rate', 'monthly_salary',
                    'standard_monthly_remuneration', 'is_active')
    list_per_page = 10
    ordering = ('staff',)

    search_fields = ('staff__name', 'staff__store__name')
    autocomplete_fields = ('staff',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            if staff.is_store_manager:
                return qs.filter(staff__store=staff.store)
            return qs.none()
        except Staff.DoesNotExist:
            return qs.none()


class WorkAttendanceAdmin(admin.ModelAdmin):
    list_display = ('staff', 'date', 'clock_in', 'clock_out', 'regular_minutes',
                    'overtime_minutes', 'late_night_minutes', 'holiday_minutes',
                    'break_minutes', 'source')
    list_per_page = 10
    ordering = ('-date', 'staff')

    search_fields = ('staff__name',)
    date_hierarchy = 'date'
    autocomplete_fields = ('staff',)

    actions = ['derive_from_shifts']

    @admin.action(description=_('確定シフトから勤怠データを自動生成'))
    def derive_from_shifts(self, request, queryset):
        from booking.services.attendance_service import derive_attendance_from_shifts
        if request.user.is_superuser:
            from booking.models import Store
            stores = Store.objects.all()
        else:
            try:
                stores = [request.user.staff.store]
            except Staff.DoesNotExist:
                self.message_user(request, 'スタッフ情報が見つかりません。', messages.ERROR)
                return

        from datetime import date, timedelta
        today = date.today()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        total = 0
        for store in stores:
            count = derive_attendance_from_shifts(store, month_start, month_end)
            total += count
        self.message_user(request, f'{total} 件の勤怠レコードを生成しました。')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            if staff.is_store_manager:
                return qs.filter(staff__store=staff.store)
            return qs.none()
        except Staff.DoesNotExist:
            return qs.none()


class PayrollDeductionInline(admin.TabularInline):
    model = PayrollDeduction
    extra = 0
    readonly_fields = ('deduction_type', 'amount', 'is_employer_only')


class PayrollEntryAdmin(admin.ModelAdmin):
    list_display = ('staff', 'period', 'total_work_days', 'gross_pay', 'total_deductions', 'net_pay')
    list_per_page = 10
    ordering = ('-period', 'staff')

    search_fields = ('staff__name',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [PayrollDeductionInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            if staff.is_store_manager:
                return qs.filter(period__store=staff.store)
            return qs.none()
        except Staff.DoesNotExist:
            return qs.none()


class PayrollEntryInline(admin.TabularInline):
    model = PayrollEntry
    extra = 0
    readonly_fields = ('staff', 'gross_pay', 'total_deductions', 'net_pay', 'total_work_days')
    fields = ('staff', 'total_work_days', 'gross_pay', 'total_deductions', 'net_pay')
    max_num = 0  # read-only inline


class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('store', 'year_month', 'period_start', 'period_end', 'status', 'payment_date')
    search_fields = ('store__name', 'year_month')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 10
    ordering = ('-year_month',)
    inlines = [PayrollEntryInline]

    actions = ['run_payroll_calculation', 'export_zengin_csv', 'mark_as_paid']

    @admin.action(description=_('給与計算を実行'))
    def run_payroll_calculation(self, request, queryset):
        from booking.services.payroll_calculator import calculate_payroll_for_period
        total = 0
        for period in queryset.filter(status__in=['draft', 'confirmed']):
            entries = calculate_payroll_for_period(period)
            total += len(entries)
        self.message_user(request, f'{total} 件の給与明細を計算しました。')

    @admin.action(description=_('全銀フォーマットCSVダウンロード'))
    def export_zengin_csv(self, request, queryset):
        from booking.services.zengin_export import generate_zengin_csv
        from django.http import HttpResponse

        if queryset.count() != 1:
            self.message_user(request, 'CSVエクスポートは1件ずつ選択してください。', messages.ERROR)
            return

        period = queryset.first()
        csv_content = generate_zengin_csv(period)

        response = HttpResponse(csv_content, content_type='text/csv; charset=shift_jis')
        filename = f'zengin_{period.store.name}_{period.year_month}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @admin.action(description=_('支払済みにする'))
    def mark_as_paid(self, request, queryset):
        count = queryset.filter(status='confirmed').update(status='paid')
        self.message_user(request, f'{count} 件の給与期間を支払済みにしました。')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            if staff.is_store_manager:
                return qs.filter(store=staff.store)
            return qs.none()
        except Staff.DoesNotExist:
            return qs.none()


class SalaryStructureAdmin(admin.ModelAdmin):
    list_display = ('store', 'pension_rate', 'health_insurance_rate', 'employment_insurance_rate',
                    'overtime_multiplier', 'late_night_multiplier', 'holiday_multiplier')
    search_fields = ('store__name',)
    list_per_page = 10
    ordering = ('store',)


class TableSeatAdmin(admin.ModelAdmin):
    list_display = ('store', 'label', 'is_active', 'has_qr', 'created_at')
    list_filter = ('store', 'is_active')
    search_fields = ('label', 'store__name')
    list_per_page = 10
    ordering = ('store', 'label')

    def has_qr(self, obj):
        return bool(obj.qr_code)
    has_qr.boolean = True
    has_qr.short_description = _('QRコード')
    has_qr.admin_order_field = 'qr_code'

    readonly_fields = ('id', 'qr_preview', 'created_at')

    def qr_preview(self, obj):
        if obj.qr_code:
            return format_html(
                '<img src="{}" width="200" /><br>'
                '<a href="{}" download>QRコードをダウンロード</a><br>'
                '<small>メニューURL: {}</small>',
                obj.qr_code.url, obj.qr_code.url, obj.get_menu_url()
            )
        return 'QRコード未生成（アクション「QRコード生成」を実行してください）'
    qr_preview.short_description = _('QRプレビュー')

    actions = ['generate_qr_codes', 'download_qr_zip']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Auto-generate QR code on save if not yet generated
        if not obj.qr_code:
            from ..services.qr_service import generate_table_qr
            url = obj.get_menu_url()
            qr_file = generate_table_qr(url, obj.label)
            obj.qr_code.save(qr_file.name, qr_file, save=True)

    @admin.action(description=_('QRコード生成'))
    def generate_qr_codes(self, request, queryset):
        from ..services.qr_service import generate_table_qr
        count = 0
        for seat in queryset:
            url = seat.get_menu_url()
            qr_file = generate_table_qr(url, seat.label)
            seat.qr_code.save(qr_file.name, qr_file, save=True)
            count += 1
        self.message_user(request, f'{count} 件のQRコードを生成しました。')

    @admin.action(description=_('QRコードZIPダウンロード'))
    def download_qr_zip(self, request, queryset):
        import zipfile
        from django.http import HttpResponse
        response = HttpResponse(content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="table_qr_codes.zip"'
        with zipfile.ZipFile(response, 'w') as zf:
            for seat in queryset:
                if seat.qr_code:
                    seat.qr_code.open('rb')
                    safe_label = seat.label.replace('/', '_').replace(' ', '_')
                    zf.writestr(
                        f'{seat.store.name}_{safe_label}.png',
                        seat.qr_code.read()
                    )
                    seat.qr_code.close()
        return response

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            if staff.is_store_manager:
                return qs.filter(store=staff.store)
            return qs.none()
        except Staff.DoesNotExist:
            return qs.none()


class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('store', 'display_name', 'method_type', 'is_enabled', 'sort_order')
    list_editable = ('is_enabled', 'sort_order')
    list_filter = ('store', 'method_type', 'is_enabled')
    search_fields = ('display_name', 'store__name')
    list_per_page = 10
    ordering = ('store', 'sort_order')

    fieldsets = (
        (None, {'fields': ('store', 'method_type', 'display_name', 'is_enabled', 'sort_order')}),
        (_('API設定'), {
            'classes': ('collapse',),
            'fields': ('api_key', 'api_secret', 'api_endpoint', 'extra_config'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            if staff.is_store_manager:
                return qs.filter(store=staff.store)
            return qs.none()
        except Staff.DoesNotExist:
            return qs.none()


class AttendanceTOTPConfigAdmin(admin.ModelAdmin):
    list_display = ('store', 'totp_interval', 'require_geo_check', 'is_active')
    list_filter = ('is_active',)
    list_per_page = 10
    ordering = ('store',)


class AttendanceStampAdmin(admin.ModelAdmin):
    list_display = ('staff', 'stamp_type', 'stamped_at', 'is_valid', 'ip_address')
    list_filter = ('stamp_type', 'is_valid')
    search_fields = ('staff__name',)
    readonly_fields = ('stamped_at',)
    list_per_page = 10
    ordering = ('-stamped_at',)
    date_hierarchy = 'stamped_at'


# Registration
custom_site.register(EmploymentContract, EmploymentContractAdmin)
custom_site.register(WorkAttendance, WorkAttendanceAdmin)
custom_site.register(PayrollPeriod, PayrollPeriodAdmin)
custom_site.register(PayrollEntry, PayrollEntryAdmin)
custom_site.register(SalaryStructure, SalaryStructureAdmin)
custom_site.register(TableSeat, TableSeatAdmin)
custom_site.register(PaymentMethod, PaymentMethodAdmin)
custom_site.register(AttendanceTOTPConfig, AttendanceTOTPConfigAdmin)
custom_site.register(AttendanceStamp, AttendanceStampAdmin)
