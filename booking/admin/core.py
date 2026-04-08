"""Core admin: Schedule, Staff, Store."""
import logging

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from ..admin_site import custom_site
from ..models import (
    Schedule, Staff, Store, StoreScheduleConfig, AdminTheme, StoreTheme,
)
from .helpers import _is_owner_or_super

logger = logging.getLogger(__name__)


class ScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'short_reservation_number',
        'customer_name',
        'pen_name',
        'start',
        'end',
        'staff',
        'store',
        'is_temporary',
        'is_cancelled',
        'refund_status',
        'is_checked_in',
        'price',
        'has_line_user',
    )
    list_filter = ('is_checked_in', 'is_temporary', 'is_cancelled', 'refund_status', 'store')
    search_fields = ('customer_name', 'pen_name', 'hashed_id', 'reservation_number', 'line_user_hash', 'checkin_backup_code')
    ordering = ('-start',)
    list_per_page = 10

    readonly_fields = (
        'reservation_number', 'line_user_hash', 'line_user_enc',
        'checkin_qr', 'checked_in_at', 'checkin_backup_code', 'checked_in_by',
        'refund_completed_at', 'refund_completed_by',
    )
    actions = ['mark_refund_completed']

    def short_reservation_number(self, obj):
        rn = obj.reservation_number or ''
        short = rn[:9]
        if len(rn) > 9:
            return format_html('<span title="{}">{}&hellip;</span>', rn, short)
        return short

    short_reservation_number.short_description = _('予約番号')
    short_reservation_number.admin_order_field = 'reservation_number'

    @admin.action(description=_('選択した予約を「返金済み」にする'))
    def mark_refund_completed(self, request, queryset):
        """選択した返金待ち予約を返金済みに更新し、顧客にLINE通知を送信する。"""
        from linebot import LineBotApi
        from linebot.models import TextSendMessage
        import pytz

        local_tz = pytz.timezone('Asia/Tokyo')
        bot = LineBotApi(settings.LINE_ACCESS_TOKEN)
        staff_member = None
        try:
            staff_member = request.user.staff_set.first() or request.user.staff
        except Exception:
            pass

        count = 0
        for schedule in queryset.filter(refund_status='pending'):
            schedule.refund_status = 'completed'
            schedule.refund_completed_at = timezone.now()
            schedule.refund_completed_by = staff_member
            schedule.save(update_fields=[
                'refund_status', 'refund_completed_at', 'refund_completed_by',
            ])

            # 顧客LINE通知
            try:
                line_user_id = schedule.get_line_user_id()
                if line_user_id:
                    local_start = schedule.start.astimezone(local_tz)
                    msg = (
                        f'【返金完了のお知らせ】\n\n'
                        f'ご予約 {schedule.reservation_number} の返金処理が完了いたしました。\n\n'
                        f'日時: {local_start.strftime("%Y年%m月%d日 %H:%M")}\n'
                        f'金額: {schedule.price:,}円\n\n'
                        f'返金の反映までに数日かかる場合がございます。'
                        f'ご不明な点がございましたらお気軽にお問い合わせください。'
                    )
                    bot.push_message(line_user_id, TextSendMessage(text=msg))
            except Exception as e:
                logger.warning('返金完了LINE通知に失敗 (schedule=%s): %s', schedule.pk, e)

            count += 1

        if count:
            self.message_user(request, _(f'{count}件の返金処理を完了しました。'), messages.SUCCESS)
        else:
            self.message_user(request, _('返金待ちの予約が選択されていません。'), messages.WARNING)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['add_button_label'] = _('予約を追加')
        return super().changelist_view(request, extra_context=extra_context)


class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'staff_type', 'is_store_manager', 'is_owner', 'is_recommended', 'display_thumbnail')
    list_filter = ('staff_type', 'is_store_manager', 'store')
    list_editable = ('is_recommended',)
    search_fields = ('name', 'store__name')
    list_per_page = 10
    ordering = ('store', 'name')
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
    extra = 1
    max_num = 1
    can_delete = False
    verbose_name = _('店舗スケジュール設定')
    verbose_name_plural = _('店舗スケジュール設定')
    radio_fields = {'slot_duration': admin.HORIZONTAL}
    fieldsets = (
        (_('営業時間'), {
            'fields': ('open_hour', 'close_hour'),
            'description': '営業開始・終了時間（0〜23の整数）',
        }),
        (_('予約カレンダー設定'), {
            'fields': ('slot_duration',),
            'description': 'カレンダーの1コマの長さを選択してください',
        }),
        (_('シフト設定'), {
            'fields': ('min_shift_hours',),
            'classes': ('collapse',),
        }),
    )


class AdminThemeInline(admin.StackedInline):
    model = AdminTheme
    extra = 0
    max_num = 1


class StoreThemeForm(forms.ModelForm):
    """StoreTheme のフォーム。カラーフィールドに type="color" を適用。"""
    class Meta:
        model = StoreTheme
        fields = '__all__'
        widgets = {
            'primary_color': forms.TextInput(attrs={'type': 'color', 'style': 'width:60px;height:30px;padding:2px;'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color', 'style': 'width:60px;height:30px;padding:2px;'}),
            'accent_color': forms.TextInput(attrs={'type': 'color', 'style': 'width:60px;height:30px;padding:2px;'}),
            'text_color': forms.TextInput(attrs={'type': 'color', 'style': 'width:60px;height:30px;padding:2px;'}),
            'header_bg_color': forms.TextInput(attrs={'type': 'color', 'style': 'width:60px;height:30px;padding:2px;'}),
            'footer_bg_color': forms.TextInput(attrs={'type': 'color', 'style': 'width:60px;height:30px;padding:2px;'}),
            'custom_css': forms.Textarea(attrs={'rows': 5, 'style': 'font-family:monospace;'}),
        }


class StoreThemeInline(admin.StackedInline):
    model = StoreTheme
    form = StoreThemeForm
    extra = 0
    max_num = 1
    fieldsets = (
        (_('テーマプリセット'), {'fields': ('preset',)}),
        (_('カラー設定'), {
            'fields': (
                'primary_color', 'secondary_color', 'accent_color',
                'text_color', 'header_bg_color', 'footer_bg_color',
            ),
        }),
        (_('フォント'), {'fields': ('heading_font', 'body_font')}),
        (_('ブランディング'), {'fields': ('logo', 'favicon')}),
        (_('上級者向け'), {
            'classes': ('collapse',),
            'fields': ('custom_css',),
        }),
    )

    class Media:
        js = ('js/store_theme_preset.js',)


class WeekdayCheckboxWidget(forms.CheckboxSelectMultiple):
    """曜日チェックボックスウィジェット"""
    pass


class RegularHolidayField(forms.MultipleChoiceField):
    """定休日をカンマ区切り文字列で保存するフィールド"""

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = Store.WEEKDAY_CHOICES
        kwargs['widget'] = WeekdayCheckboxWidget
        kwargs['required'] = False
        super().__init__(*args, **kwargs)

    def prepare_value(self, value):
        if isinstance(value, str):
            return [v.strip() for v in value.split(',') if v.strip()]
        return value or []


class StoreAdminForm(forms.ModelForm):
    regular_holiday = RegularHolidayField(label=_('定休日'))

    class Meta:
        model = Store
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            val = self.instance.regular_holiday or ''
            self.initial['regular_holiday'] = [v.strip() for v in val.split(',') if v.strip()]

    def clean_regular_holiday(self):
        days = self.cleaned_data.get('regular_holiday', [])
        return ','.join(days)


class StoreAdmin(admin.ModelAdmin):
    form = StoreAdminForm
    list_display = ('name', 'address', 'nearest_station', 'business_hours', 'regular_holiday_display', 'default_language', 'is_recommended')
    list_editable = ('is_recommended',)
    search_fields = ('name', 'address', 'nearest_station')
    list_per_page = 10
    ordering = ('name',)
    inlines = [StoreScheduleConfigInline, AdminThemeInline, StoreThemeInline]

    class Media:
        js = ('js/store_change_tabs.js',)

    @admin.display(description=_('定休日'))
    def regular_holiday_display(self, obj):
        if not obj.regular_holiday:
            return _('なし')
        day_map = dict(Store.WEEKDAY_CHOICES)
        return ', '.join(str(day_map.get(d.strip(), d.strip())) for d in obj.regular_holiday.split(',') if d.strip())

    fieldsets = (
        (None, {'fields': ('name', 'address', 'business_hours', 'nearest_station', 'regular_holiday', 'is_recommended', 'default_language')}),
        (_('店舗紹介'), {'fields': ('description', 'access_info', 'map_url', 'google_maps_embed')}),
        (_('店舗写真'), {'fields': ('thumbnail', 'photo_2', 'photo_3')}),
        (_('外部埋め込み'), {'fields': ('embed_api_key', 'embed_allowed_domains'), 'classes': ('collapse',)}),
    )
    actions = ['generate_embed_api_key']

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['customization_links'] = [
            {
                'label': _('セットアップウィザード'),
                'url': reverse('admin_site_wizard', args=[object_id]),
                'icon': '🚀',
            },
            {
                'label': _('テーマカスタマイザー'),
                'url': reverse('admin_theme_customizer', args=[object_id]),
                'icon': '🎨',
            },
            {
                'label': _('レイアウトエディタ'),
                'url': reverse('admin_page_layout_editor', args=[object_id]),
                'icon': '📐',
            },
            {
                'label': _('ページビルダー'),
                'url': reverse('admin_page_builder_list', args=[object_id]),
                'icon': '📄',
            },
        ]
        return super().change_view(request, object_id, form_url, extra_context)

    def has_delete_permission(self, request, obj=None):
        return False

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
