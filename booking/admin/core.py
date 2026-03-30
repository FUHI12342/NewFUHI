"""Core admin: Schedule, Staff, Store."""
from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from ..admin_site import custom_site
from ..models import (
    Schedule, Staff, Store, StoreScheduleConfig, AdminTheme,
)
from .helpers import _is_owner_or_super


class ScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'short_reservation_number',
        'customer_name',
        'start',
        'end',
        'staff',
        'is_temporary',
        'is_cancelled',
        'is_checked_in',
        'price',
        'has_line_user',
    )
    list_filter = ('is_checked_in', 'is_temporary', 'is_cancelled')
    search_fields = ('customer_name', 'hashed_id', 'reservation_number', 'line_user_hash', 'checkin_backup_code')
    ordering = ('-start',)

    readonly_fields = (
        'reservation_number', 'line_user_hash', 'line_user_enc',
        'checkin_qr', 'checked_in_at', 'checkin_backup_code', 'checked_in_by',
    )

    def short_reservation_number(self, obj):
        rn = obj.reservation_number or ''
        short = rn[:9]
        if len(rn) > 9:
            return format_html('<span title="{}">{}&hellip;</span>', rn, short)
        return short

    short_reservation_number.short_description = _('予約番号')
    short_reservation_number.admin_order_field = 'reservation_number'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['add_button_label'] = _('予約を追加')
        return super().changelist_view(request, extra_context=extra_context)


class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'staff_type', 'is_store_manager', 'is_owner', 'is_recommended', 'display_thumbnail')
    list_filter = ('staff_type', 'is_store_manager', 'store')
    list_editable = ('is_recommended',)
    search_fields = ('name', 'store__name')
    save_on_top = True

    # --- superuser用（LINE ID含む全フィールド）---
    _su_fieldsets_cast = (
        (None, {'fields': ('user', 'store', 'name', 'staff_type')}),
        (_('プロフィール'), {'fields': ('thumbnail', 'introduction', 'price', 'slot_duration', 'line_id')}),
        (_('通知設定'), {'fields': ('notify_booking', 'notify_shift', 'notify_business')}),
        (_('メニュー表示設定'), {'fields': ('can_see_inventory', 'can_see_orders')}),
        (_('権限'), {'fields': ('is_owner', 'is_store_manager', 'is_developer', 'is_recommended')}),
        (_('勤怠'), {'fields': ('attendance_pin',)}),
    )
    _su_fieldsets_staff = (
        (None, {'fields': ('user', 'store', 'name', 'staff_type')}),
        (_('プロフィール'), {'fields': ('thumbnail', 'introduction', 'price', 'line_id')}),
        (_('通知設定'), {'fields': ('notify_booking', 'notify_shift', 'notify_business')}),
        (_('メニュー表示設定'), {'fields': ('can_see_inventory', 'can_see_orders')}),
        (_('権限'), {'fields': ('is_owner', 'is_store_manager', 'is_developer', 'is_recommended')}),
        (_('勤怠'), {'fields': ('attendance_pin',)}),
    )

    # --- 管理者用（LINE ID非表示）---
    _full_fieldsets_cast = (
        (None, {'fields': ('user', 'store', 'name', 'staff_type')}),
        (_('プロフィール'), {'fields': ('thumbnail', 'introduction', 'price', 'slot_duration')}),
        (_('通知設定'), {'fields': ('notify_booking', 'notify_shift', 'notify_business')}),
        (_('メニュー表示設定'), {'fields': ('can_see_inventory', 'can_see_orders')}),
        (_('権限'), {'fields': ('is_owner', 'is_store_manager', 'is_developer', 'is_recommended')}),
        (_('勤怠'), {'fields': ('attendance_pin',)}),
    )
    _full_fieldsets_staff = (
        (None, {'fields': ('user', 'store', 'name', 'staff_type')}),
        (_('プロフィール'), {'fields': ('thumbnail', 'introduction', 'price')}),
        (_('通知設定'), {'fields': ('notify_booking', 'notify_shift', 'notify_business')}),
        (_('メニュー表示設定'), {'fields': ('can_see_inventory', 'can_see_orders')}),
        (_('権限'), {'fields': ('is_owner', 'is_store_manager', 'is_developer', 'is_recommended')}),
        (_('勤怠'), {'fields': ('attendance_pin',)}),
    )

    # --- 本人用（LINE ID表示, デフォルト****マスク）---
    _profile_fieldsets_cast = (
        (_('マイプロフィール'), {'fields': ('name', 'thumbnail', 'introduction', 'price', 'slot_duration', 'line_id')}),
        (_('通知設定'), {'fields': ('notify_booking', 'notify_shift', 'notify_business')}),
    )
    _profile_fieldsets_staff = (
        (_('マイプロフィール'), {'fields': ('name', 'thumbnail', 'introduction', 'price', 'line_id')}),
        (_('通知設定'), {'fields': ('notify_booking', 'notify_shift', 'notify_business')}),
    )

    def changelist_view(self, request, extra_context=None):
        """一般スタッフは自分のchange formにリダイレクト"""
        if not _is_owner_or_super(request):
            try:
                staff = request.user.staff
                if not staff.is_store_manager and not staff.is_developer:
                    return redirect(
                        reverse('admin:booking_staff_change', args=[staff.pk])
                    )
            except Staff.DoesNotExist:
                pass
        return super().changelist_view(request, extra_context=extra_context)

    def _is_cast(self, obj):
        """対象objがキャスト（fortune_teller）かどうか"""
        return obj is not None and obj.staff_type == 'fortune_teller'

    def get_fieldsets(self, request, obj=None):
        is_cast = self._is_cast(obj)
        if request.user.is_superuser:
            return self._su_fieldsets_cast if is_cast else self._su_fieldsets_staff
        if _is_owner_or_super(request):
            return self._full_fieldsets_cast if is_cast else self._full_fieldsets_staff
        try:
            staff = request.user.staff
            if staff.is_store_manager or staff.is_developer:
                return self._full_fieldsets_cast if is_cast else self._full_fieldsets_staff
        except Staff.DoesNotExist:
            pass
        return self._profile_fieldsets_cast if is_cast else self._profile_fieldsets_staff

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'line_id' in form.base_fields and obj and obj.line_id:
            field = form.base_fields['line_id']
            field.widget = forms.TextInput(attrs={
                'data-real-value': obj.line_id,
                'value': '****',
                'onfocus': "if(this.value==='****'){this.value=this.dataset.realValue;}",
                'onblur': "if(this.value===this.dataset.realValue){this.value='****';}",
            })
        return form

    def save_model(self, request, obj, form, change):
        if 'line_id' in form.changed_data:
            new_val = form.cleaned_data.get('line_id', '')
            if new_val == '****':
                obj.line_id = Staff.objects.filter(pk=obj.pk).values_list('line_id', flat=True).first()
        if 'attendance_pin' in form.changed_data:
            raw_pin = form.cleaned_data['attendance_pin']
            if raw_pin:
                obj.set_attendance_pin(raw_pin)
            else:
                obj.attendance_pin = ''
        super().save_model(request, obj, form, change)

    def display_thumbnail(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" width="50" height="50" />', obj.thumbnail.url)
        return ''

    display_thumbnail.short_description = _('サムネイル')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            if staff.is_store_manager:
                return qs.filter(store=staff.store)
            else:
                return qs.filter(id=staff.id)
        except Staff.DoesNotExist:
            return qs.none()

    def has_change_permission(self, request, obj=None):
        if _is_owner_or_super(request):
            return True
        try:
            staff = request.user.staff
            if staff.is_store_manager:
                return True
            if obj is None:
                return True
            return obj.id == staff.id
        except Staff.DoesNotExist:
            return False

    def has_add_permission(self, request):
        if _is_owner_or_super(request):
            return True
        try:
            return request.user.staff.is_store_manager
        except Staff.DoesNotExist:
            return False

    def has_delete_permission(self, request, obj=None):
        if _is_owner_or_super(request):
            return True
        try:
            return request.user.staff.is_store_manager
        except Staff.DoesNotExist:
            return False

    # --------------------------------------------------
    # カスタムアクション: LINE業務連絡送信
    # --------------------------------------------------
    actions = ['send_business_line']

    @admin.action(description=_('選択したスタッフにLINE業務連絡を送信'))
    def send_business_line(self, request, queryset):
        from django.shortcuts import render
        from booking.services.staff_notifications import send_business_message

        if 'send' in request.POST:
            message_text = request.POST.get('message', '').strip()
            if not message_text:
                self.message_user(request, _('メッセージを入力してください。'), messages.ERROR)
                return

            sender_name = ''
            try:
                sender_name = request.user.staff.name
            except (Staff.DoesNotExist, AttributeError):
                sender_name = request.user.get_full_name() or request.user.username

            results = send_business_message(queryset, message_text, sender_name=sender_name)
            self.message_user(
                request,
                _(f'送信完了: {results["sent"]}件成功, {results["skipped"]}件スキップ, {results["failed"]}件失敗'),
                messages.SUCCESS if results['failed'] == 0 else messages.WARNING,
            )
            return

        return render(request, 'admin/booking/send_business_line.html', {
            'title': _('LINE業務連絡送信'),
            'staffs': queryset,
            'opts': self.model._meta,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        })


class StoreScheduleConfigInline(admin.StackedInline):
    model = StoreScheduleConfig
    extra = 0
    max_num = 1


class AdminThemeInline(admin.StackedInline):
    model = AdminTheme
    extra = 0
    max_num = 1


class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'nearest_station', 'business_hours', 'regular_holiday', 'default_language', 'is_recommended')
    list_editable = ('is_recommended',)
    search_fields = ('name', 'address', 'nearest_station')
    inlines = [StoreScheduleConfigInline, AdminThemeInline]
    fieldsets = (
        (None, {'fields': ('name', 'address', 'business_hours', 'nearest_station', 'regular_holiday', 'is_recommended', 'default_language')}),
        (_('店舗紹介'), {'fields': ('description', 'access_info', 'map_url', 'google_maps_embed')}),
        (_('店舗写真'), {'fields': ('thumbnail', 'photo_2', 'photo_3')}),
        (_('外部埋め込み'), {'fields': ('embed_api_key', 'embed_allowed_domains'), 'classes': ('collapse',)}),
    )
    actions = ['generate_embed_api_key']

    @admin.action(description=_('選択した店舗の埋め込みAPIキーを生成'))
    def generate_embed_api_key(self, request, queryset):
        from booking.views_embed import generate_embed_api_key
        updated = 0
        for store in queryset:
            store.embed_api_key = generate_embed_api_key()
            store.save(update_fields=['embed_api_key'])
            updated += 1
        self.message_user(request, _(f'{updated}件の店舗にAPIキーを生成しました。'), messages.SUCCESS)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            return qs.filter(id=staff.store.id)
        except Staff.DoesNotExist:
            return qs.none()


# Registration
custom_site.register(Schedule, ScheduleAdmin)
custom_site.register(Staff, StaffAdmin)
custom_site.register(Store, StoreAdmin)
