from django.contrib import admin, messages
from django.contrib.admin.sites import AdminSite
from django.db.models import F
from django.utils.html import format_html
import json

from social_django.models import Association, Nonce, UserSocialAuth

from .admin_site import custom_site

from .models import (
    Staff,
    Store,
    Schedule,
    Company,
    Notice,
    Media,
    IoTDevice,
    IoTEvent,
    IRCode,
    Category,
    Product,
    ProductTranslation,
    Order,
    OrderItem,
    StockMovement,
    SystemConfig,
    Property,
    PropertyDevice,
    PropertyAlert,
    StoreScheduleConfig,
    ShiftPeriod,
    ShiftRequest,
    ShiftAssignment,
    AdminTheme,
    SiteSettings,
    HomepageCustomBlock,
    HeroBanner,
    BannerAd,
    ExternalLink,
    AdminMenuConfig,
    EmploymentContract,
    WorkAttendance,
    PayrollPeriod,
    PayrollEntry,
    PayrollDeduction,
    SalaryStructure,
)


def _is_owner_or_super(request):
    """superuser または is_owner の場合 True"""
    if request.user.is_superuser:
        return True
    try:
        return request.user.staff.is_owner
    except Staff.DoesNotExist:
        return False

# ==============================
# 予約
# ==============================
class ScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'reservation_number',
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
    search_fields = ('customer_name', 'hashed_id', 'reservation_number', 'line_user_hash')
    ordering = ('-start',)

    readonly_fields = ('reservation_number', 'line_user_hash', 'line_user_enc', 'checkin_qr', 'checked_in_at')



# ==============================
# スタッフ / 店舗
# ==============================
class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'staff_type', 'is_store_manager', 'is_owner', 'is_recommended', 'display_thumbnail')

    list_editable = ('is_recommended',)
    search_fields = ('name', 'store__name')

    def display_thumbnail(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" width="50" height="50" />', obj.thumbnail.url)
        return ''

    display_thumbnail.short_description = 'サムネイル'

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
            else:
                return obj is not None and obj.id == staff.id
        except Staff.DoesNotExist:
            return False

    def has_add_permission(self, request):
        if _is_owner_or_super(request):
            return True
        try:
            staff = request.user.staff
            return staff.is_store_manager
        except Staff.DoesNotExist:
            return False

    def has_delete_permission(self, request, obj=None):
        if _is_owner_or_super(request):
            return True
        try:
            staff = request.user.staff
            return staff.is_store_manager
        except Staff.DoesNotExist:
            return False


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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            return qs.filter(id=staff.store.id)
        except Staff.DoesNotExist:
            return qs.none()


# Python Social Auth の非表示（不要なら管理画面から外す）
for m in (Association, Nonce, UserSocialAuth):
    try:
        admin.site.unregister(m)
    except Exception:
        pass


# ==============================
# お知らせ / 会社 / メディア
# ==============================
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'updated_at', 'link')
    search_fields = ('title', 'content', 'link')
    date_hierarchy = 'updated_at'


class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'tel')
    search_fields = ('name', 'address', 'tel')



    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Admin の date_hierarchy が start の MIN/MAX を取る際、NULL が混ざると SQLite で None になり落ちることがある
        return qs.exclude(start__isnull=True)
class MediaAdmin(admin.ModelAdmin):
    list_display = ('link', 'title', 'created_at')
    search_fields = ('title', 'link')
    date_hierarchy = 'created_at'


# ==============================
# IoT
# ==============================
class IoTEventInline(admin.TabularInline):
    model = IoTEvent
    extra = 0
    readonly_fields = ('created_at',)
    max_num = 50


class IoTDeviceAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'store',
        'device_type',
        'external_id',
        'is_active',
        'last_seen_at',
        'mq9_threshold',
        'alert_enabled',
        'alert_email',
        'alert_line_user_id',
        'wifi_ssid',
    )

    search_fields = ('name', 'external_id', 'store__name')
    readonly_fields = ('last_seen_at',)
    inlines = [IoTEventInline]


class IoTEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'event_type', 'mq9_value', 'device', 'sensor_summary')

    search_fields = ('device__name', 'device__external_id')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 20

    def sensor_summary(self, obj):
        if not obj.payload:
            return "-"
        try:
            data = json.loads(obj.payload)
        except Exception:
            return obj.payload[:50] + "..." if len(obj.payload) > 50 else obj.payload

        keys = ["mq9", "light", "sound", "temp", "hum"]
        parts = []
        for k in keys:
            if k in data and data[k] is not None:
                label = {"mq9": "CO", "light": "光", "sound": "音", "temp": "温度", "hum": "湿度"}[k]
                parts.append(f"{label}: {data[k]}")
        return " / ".join(parts) if parts else "-"

    sensor_summary.short_description = "センサー要約"


class IRCodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'device', 'protocol', 'code', 'created_at')

    search_fields = ('name', 'device__name', 'code')
    readonly_fields = ('created_at',)
    actions = ['send_ir_code']

    @admin.action(description='IRコードを送信')
    def send_ir_code(self, request, queryset):
        import json as _json
        count = 0
        for ir_code in queryset:
            device = ir_code.device
            device.pending_ir_command = _json.dumps({
                'action': 'send_ir',
                'code': ir_code.code,
                'protocol': ir_code.protocol,
            })
            device.save(update_fields=['pending_ir_command'])
            count += 1
        self.message_user(request, f'{count} 件のIRコード送信をキューしました。')


# ==============================
# 追加: 商品/翻訳
# ==============================
class ProductTranslationInline(admin.TabularInline):
    model = ProductTranslation
    extra = 0


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('store', 'name', 'sort_order')
    search_fields = ('name', 'store__name')
    list_editable = ('sort_order',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            return qs.filter(store=staff.store)
        except Staff.DoesNotExist:
            return qs.none()

    def has_change_permission(self, request, obj=None):
        if _is_owner_or_super(request):
            return True
        try:
            staff = request.user.staff
            if staff.is_developer:
                return False
            elif staff.is_store_manager:
                return True
            else:
                return False
        except Staff.DoesNotExist:
            return False

    def has_add_permission(self, request):
        if _is_owner_or_super(request):
            return True
        try:
            staff = request.user.staff
            if staff.is_developer:
                return False
            elif staff.is_store_manager:
                return True
            else:
                return False
        except Staff.DoesNotExist:
            return False

    def has_delete_permission(self, request, obj=None):
        if _is_owner_or_super(request):
            return True
        try:
            staff = request.user.staff
            if staff.is_developer:
                return False
            elif staff.is_store_manager:
                return True
            else:
                return False
        except Staff.DoesNotExist:
            return False


class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'store',
        'sku',
        'name',
        'category',
        'price',
        'stock',
        'low_stock_threshold',
        'is_active',
        'is_ec_visible',
        'is_sold_out',
        'last_low_stock_notified_at',
    )

    search_fields = ('sku', 'name', 'store__name')
    list_editable = ('price', 'stock', 'low_stock_threshold', 'is_active', 'is_ec_visible')
    inlines = [ProductTranslationInline]
    autocomplete_fields = ('category',)
    ordering = ('store', 'category', 'name')

    def is_sold_out(self, obj):
        return obj.stock <= 0
    is_sold_out.short_description = '売り切れ'
    is_sold_out.boolean = True

    actions = ['clear_low_stock_notification', 'stock_in', 'stock_out', 'stock_adjust_zero',
               'enable_ec_visibility', 'disable_ec_visibility']

    @admin.action(description='閾値通知フラグを解除（last_low_stock_notified_at を空にする）')
    def clear_low_stock_notification(self, request, queryset):
        queryset.update(last_low_stock_notified_at=None)

    @admin.action(description='入庫（1個）')
    def stock_in(self, request, queryset):
        count = 0
        for product in queryset:
            qty = 1
            StockMovement.objects.create(
                store=product.store,
                product=product,
                movement_type=StockMovement.TYPE_IN,
                qty=qty,
                by_staff=getattr(request.user, 'staff', None),
                note='admin action: stock_in',
            )
            product.stock += qty
            product.save()
            count += 1
        self.message_user(request, f'{count} 件の商品に入庫しました。')

    @admin.action(description='出庫（1個、在庫不足時はスキップ）')
    def stock_out(self, request, queryset):
        count = 0
        skipped = 0
        for product in queryset:
            qty = 1
            if product.stock < qty:
                skipped += 1
                continue
            StockMovement.objects.create(
                store=product.store,
                product=product,
                movement_type=StockMovement.TYPE_OUT,
                qty=qty,
                by_staff=getattr(request.user, 'staff', None),
                note='admin action: stock_out',
            )
            product.stock -= qty
            product.save()
            count += 1
        msg = f'{count} 件の商品を出庫しました。'
        if skipped:
            msg += f' 在庫不足でスキップ: {skipped} 件'
        self.message_user(request, msg)

    @admin.action(description='棚卸（在庫を0に調整）')
    def stock_adjust_zero(self, request, queryset):
        count = 0
        for product in queryset:
            qty = -product.stock
            if qty == 0:
                continue
            StockMovement.objects.create(
                store=product.store,
                product=product,
                movement_type=StockMovement.TYPE_ADJUST,
                qty=qty,
                by_staff=getattr(request.user, 'staff', None),
                note='admin action: stock_adjust_zero',
            )
            product.stock = 0
            product.save()
            count += 1
        self.message_user(request, f'{count} 件の商品の在庫を0に調整しました。')

    @admin.action(description='EC公開をONにする')
    def enable_ec_visibility(self, request, queryset):
        count = queryset.update(is_ec_visible=True)
        self.message_user(request, f'{count} 件の商品をEC公開にしました。')

    @admin.action(description='EC公開をOFFにする')
    def disable_ec_visibility(self, request, queryset):
        count = queryset.update(is_ec_visible=False)
        self.message_user(request, f'{count} 件の商品のEC公開を解除しました。')


# ==============================
# 追加: 注文
# ==============================
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('product',)


class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'store', 'status', 'table_label', 'schedule', 'created_at', 'updated_at')
    search_fields = ('id', 'store__name', 'table_label', 'customer_line_user_hash')
    inlines = [OrderItemInline]
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            return qs.filter(store=staff.store)
        except Staff.DoesNotExist:
            return qs.none()


class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product', 'qty', 'unit_price', 'status', 'created_at')

    search_fields = ('order__id', 'product__sku', 'product__name')
    date_hierarchy = 'created_at'
    autocomplete_fields = ('order', 'product')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            return qs.filter(order__store=staff.store)
        except Staff.DoesNotExist:
            return qs.none()


# ==============================
# 追加: 入出庫履歴
# ==============================
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'store', 'product', 'movement_type', 'qty', 'by_staff', 'note')

    search_fields = ('product__sku', 'product__name', 'note', 'store__name')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    autocomplete_fields = ('product', 'by_staff', 'store')

    actions = ['recompute_stock_from_movements']

    @admin.action(description='（上級）入出庫履歴の合計で在庫を再計算して反映')
    def recompute_stock_from_movements(self, request, queryset):
        """選択した入出庫履歴の product ごとに合計し、Product.stock に反映する。
        注意: 選択範囲のみで計算されるので、運用では「全期間」を対象にする想定。
        """
        # product_id -> delta
        deltas = {}
        for mv in queryset.select_related('product'):
            if mv.movement_type == StockMovement.TYPE_IN:
                delta = abs(int(mv.qty))
            elif mv.movement_type == StockMovement.TYPE_OUT:
                delta = -abs(int(mv.qty))
            elif mv.movement_type == StockMovement.TYPE_ADJUST:
                delta = int(mv.qty)
            else:
                delta = 0
            deltas[mv.product_id] = deltas.get(mv.product_id, 0) + delta

        if not deltas:
            return

        Product.objects.filter(id__in=deltas.keys()).update(stock=0)
        for pid, delta in deltas.items():
            Product.objects.filter(id=pid).update(stock=F('stock') + delta)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            return qs.filter(store=staff.store)
        except Staff.DoesNotExist:
            return qs.none()

    def has_change_permission(self, request, obj=None):
        if _is_owner_or_super(request):
            return True
        try:
            staff = request.user.staff
            if staff.is_developer:
                return False
            elif staff.is_store_manager:
                return True
            else:
                return False
        except Staff.DoesNotExist:
            return False

    def has_add_permission(self, request):
        if _is_owner_or_super(request):
            return True
        try:
            staff = request.user.staff
            if staff.is_developer:
                return False
            elif staff.is_store_manager:
                return True
            else:
                return False
        except Staff.DoesNotExist:
            return False

    def has_delete_permission(self, request, obj=None):
        if _is_owner_or_super(request):
            return True
        try:
            staff = request.user.staff
            if staff.is_developer:
                return False
            elif staff.is_store_manager:
                return True
            else:
                return False
        except Staff.DoesNotExist:
            return False

# モデル登録
custom_site.register(Schedule, ScheduleAdmin)
custom_site.register(Staff, StaffAdmin)
custom_site.register(Store, StoreAdmin)
custom_site.register(Notice, NoticeAdmin)
custom_site.register(Company, CompanyAdmin)
custom_site.register(Media, MediaAdmin)
custom_site.register(IoTDevice, IoTDeviceAdmin)
custom_site.register(IRCode, IRCodeAdmin)
custom_site.register(Category, CategoryAdmin)
custom_site.register(Product, ProductAdmin)
custom_site.register(Order, OrderAdmin)
# StockMovement (入出庫履歴) は管理画面から削除
# custom_site.register(StockMovement, StockMovementAdmin)

# User/Group も
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
custom_site.register(User, UserAdmin)
custom_site.register(Group, GroupAdmin)

# ==============================
# Phase 2: システム設定
# ==============================
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'updated_at')
    search_fields = ('key', 'value')
    readonly_fields = ('updated_at',)


# ==============================
# Phase 5: 不動産
# ==============================
class PropertyDeviceInline(admin.TabularInline):
    model = PropertyDevice
    extra = 0
    autocomplete_fields = ('device',)


class PropertyAlertInline(admin.TabularInline):
    model = PropertyAlert
    extra = 0
    readonly_fields = ('created_at',)


class PropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'property_type', 'owner_name', 'store', 'is_active')

    search_fields = ('name', 'address', 'owner_name')
    inlines = [PropertyDeviceInline, PropertyAlertInline]


custom_site.register(SystemConfig, SystemConfigAdmin)
custom_site.register(Property, PropertyAdmin)


# ==============================
# Phase Round2: シフト管理
# ==============================
class ShiftRequestInline(admin.TabularInline):
    model = ShiftRequest
    extra = 0
    readonly_fields = ('staff', 'date', 'start_hour', 'end_hour', 'preference')


class ShiftAssignmentInline(admin.TabularInline):
    model = ShiftAssignment
    extra = 0


class ShiftPeriodAdmin(admin.ModelAdmin):
    list_display = ('store', 'year_month', 'deadline', 'status', 'created_by')
    inlines = [ShiftRequestInline, ShiftAssignmentInline]
    actions = ['run_auto_schedule', 'approve_and_sync']

    @admin.action(description='自動スケジューリング実行')
    def run_auto_schedule(self, request, queryset):
        from booking.services.shift_scheduler import auto_schedule
        total = 0
        for period in queryset:
            count = auto_schedule(period)
            total += count
        self.message_user(request, f'{total} 件のシフトを自動割り当てしました。')

    @admin.action(description='承認してScheduleに同期')
    def approve_and_sync(self, request, queryset):
        from booking.services.shift_scheduler import sync_assignments_to_schedule
        from booking.services.shift_notifications import notify_shift_approved
        total = 0
        for period in queryset:
            count = sync_assignments_to_schedule(period)
            total += count
            notify_shift_approved(period)
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
    list_display = ('period', 'staff', 'date', 'start_hour', 'end_hour', 'is_synced')

    search_fields = ('staff__name',)


custom_site.register(ShiftPeriod, ShiftPeriodAdmin)
custom_site.register(ShiftRequest, ShiftRequestAdmin)
custom_site.register(ShiftAssignment, ShiftAssignmentAdmin)


# ==============================
# Round 4: ページ設定 (CMS)
# ==============================
class SiteSettingsAdmin(admin.ModelAdmin):
    """シングルトン設定 — 一覧は常にpk=1へリダイレクト"""
    fieldsets = (
        ('基本設定', {'fields': ('site_name', 'staff_label')}),
        ('ホームページカード表示', {'fields': (
            'show_card_store', 'show_card_fortune_teller',
            'show_card_calendar', 'show_card_shop',
        )}),
        ('ヒーローバナー / ランキング', {'fields': (
            'show_hero_banner', 'show_ranking', 'ranking_limit',
        )}),
        ('サイドバー表示', {'fields': (
            'show_sidebar_notice', 'show_sidebar_company',
            'show_sidebar_media', 'show_sidebar_social',
            'show_sidebar_external_links',
        )}),
        ('SNS連携', {'fields': ('twitter_url', 'instagram_url', 'instagram_embed_html')}),
        ('機能ON/OFF', {'fields': ('show_ai_chat',)}),
        ('法定ページ', {
            'fields': ('privacy_policy_html', 'tokushoho_html'),
            'description': 'HTMLで記述できます。空の場合はデフォルトの内容が表示されます。',
        }),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        from django.shortcuts import redirect
        return redirect(f'/admin/booking/sitesettings/{obj.pk}/change/')


custom_site.register(SiteSettings, SiteSettingsAdmin)


class HomepageCustomBlockAdmin(admin.ModelAdmin):
    list_display = ('title', 'position', 'sort_order', 'is_active', 'updated_at')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('title',)


custom_site.register(HomepageCustomBlock, HomepageCustomBlockAdmin)


# ==============================
# Round 4.5: ヒーローバナー / バナー広告 / 外部リンク
# ==============================
class HeroBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'sort_order', 'is_active', 'image_position', 'link_type', 'updated_at')
    list_editable = ('sort_order', 'is_active', 'image_position', 'link_type')
    search_fields = ('title',)
    fieldsets = (
        (None, {'fields': ('title', 'image', 'image_position', 'sort_order', 'is_active')}),
        ('リンク設定', {'fields': ('link_type', 'linked_store', 'linked_staff', 'link_url')}),
    )


class BannerAdAdmin(admin.ModelAdmin):
    list_display = ('title', 'position', 'sort_order', 'is_active', 'link_url', 'updated_at')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('title',)


class ExternalLinkAdmin(admin.ModelAdmin):
    list_display = ('title', 'url', 'sort_order', 'is_active', 'open_in_new_tab')
    list_editable = ('sort_order', 'is_active', 'open_in_new_tab')
    search_fields = ('title', 'url')


custom_site.register(HeroBanner, HeroBannerAdmin)
custom_site.register(BannerAd, BannerAdAdmin)
custom_site.register(ExternalLink, ExternalLinkAdmin)


# ==============================
# メニュー権限設定 (superuser のみ)
# ==============================
from .forms import AdminMenuConfigForm
from .admin_site import GROUP_MAP, invalidate_menu_config_cache


class AdminMenuConfigAdmin(admin.ModelAdmin):
    form = AdminMenuConfigForm
    list_display = ('role', 'get_role_display', 'model_count', 'updated_at', 'updated_by')
    readonly_fields = ('updated_at', 'updated_by')
    change_form_template = 'admin/booking/adminmenuconfig/change_form.html'

    def get_role_display(self, obj):
        return obj.get_role_display()
    get_role_display.short_description = 'ロール名'

    def model_count(self, obj):
        if isinstance(obj.allowed_models, list):
            return len(obj.allowed_models)
        return 0
    model_count.short_description = '許可モデル数'

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        obj.allowed_models = form.cleaned_data.get('allowed_models', [])
        super().save_model(request, obj, form, change)
        invalidate_menu_config_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        invalidate_menu_config_cache()

    def _get_group_map_json(self):
        return json.dumps(GROUP_MAP, ensure_ascii=False)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['group_map_json'] = self._get_group_map_json()
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['group_map_json'] = self._get_group_map_json()
        return super().add_view(request, form_url, extra_context)


custom_site.register(AdminMenuConfig, AdminMenuConfigAdmin)


# ==============================
# 給与管理・勤怠管理
# ==============================
class EmploymentContractAdmin(admin.ModelAdmin):
    list_display = ('staff', 'employment_type', 'pay_type', 'hourly_rate', 'monthly_salary',
                    'standard_monthly_remuneration', 'is_active')

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

    search_fields = ('staff__name',)
    date_hierarchy = 'date'
    autocomplete_fields = ('staff',)

    actions = ['derive_from_shifts']

    @admin.action(description='確定シフトから勤怠データを自動生成')
    def derive_from_shifts(self, request, queryset):
        from booking.services.attendance_service import derive_attendance_from_shifts
        # Get unique stores from selected attendances, or use user's store
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
    inlines = [PayrollEntryInline]

    actions = ['run_payroll_calculation', 'export_zengin_csv', 'mark_as_paid']

    @admin.action(description='給与計算を実行')
    def run_payroll_calculation(self, request, queryset):
        from booking.services.payroll_calculator import calculate_payroll_for_period
        total = 0
        for period in queryset.filter(status__in=['draft', 'confirmed']):
            entries = calculate_payroll_for_period(period)
            total += len(entries)
        self.message_user(request, f'{total} 件の給与明細を計算しました。')

    @admin.action(description='全銀フォーマットCSVダウンロード')
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

    @admin.action(description='支払済みにする')
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


custom_site.register(EmploymentContract, EmploymentContractAdmin)
custom_site.register(WorkAttendance, WorkAttendanceAdmin)
custom_site.register(PayrollPeriod, PayrollPeriodAdmin)
custom_site.register(PayrollEntry, PayrollEntryAdmin)
custom_site.register(SalaryStructure, SalaryStructureAdmin)


print("booking.admin loaded")