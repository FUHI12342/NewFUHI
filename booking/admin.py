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
    Category,
    Product,
    ProductTranslation,
    Order,
    OrderItem,
    StockMovement,
)

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
        'price',
        'has_line_user',
    )
    search_fields = ('customer_name', 'hashed_id', 'reservation_number', 'line_user_hash')
    ordering = ('-start',)
    list_filter = ('is_temporary', 'is_cancelled', 'staff__store')
    readonly_fields = ('reservation_number', 'line_user_hash', 'line_user_enc')



# ==============================
# スタッフ / 店舗
# ==============================
class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'is_store_manager', 'display_thumbnail')
    list_filter = ('store', 'is_store_manager')
    search_fields = ('name', 'store__name')

    def display_thumbnail(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" width="50" height="50" />', obj.thumbnail.url)
        return ''

    display_thumbnail.short_description = 'サムネイル'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
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
        if request.user.is_superuser:
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
        if request.user.is_superuser:
            return True
        try:
            staff = request.user.staff
            return staff.is_store_manager
        except Staff.DoesNotExist:
            return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        try:
            staff = request.user.staff
            return staff.is_store_manager
        except Staff.DoesNotExist:
            return False


class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'nearest_station', 'business_hours', 'regular_holiday', 'default_language')
    search_fields = ('name', 'address', 'nearest_station')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
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
        'wifi_ssid',
    )
    list_filter = ('device_type', 'is_active', 'store', 'alert_enabled')
    search_fields = ('name', 'external_id', 'store__name')
    readonly_fields = ('last_seen_at',)


class IoTEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'event_type', 'mq9_value', 'device', 'sensor_summary')
    list_filter = ('event_type', 'device__store')
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


# ==============================
# 追加: 商品/翻訳
# ==============================
class ProductTranslationInline(admin.TabularInline):
    model = ProductTranslation
    extra = 0


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('store', 'name', 'sort_order')
    list_filter = ('store',)
    search_fields = ('name', 'store__name')
    list_editable = ('sort_order',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        try:
            staff = request.user.staff
            return qs.filter(store=staff.store)
        except Staff.DoesNotExist:
            return qs.none()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
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
        if request.user.is_superuser:
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
        if request.user.is_superuser:
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
        'is_sold_out',
        'last_low_stock_notified_at',
    )
    list_filter = ('store', 'category', 'is_active')
    search_fields = ('sku', 'name', 'store__name')
    list_editable = ('price', 'stock', 'low_stock_threshold', 'is_active')
    inlines = [ProductTranslationInline]
    autocomplete_fields = ('category',)
    ordering = ('store', 'category', 'name')

    actions = ['clear_low_stock_notification', 'stock_in', 'stock_out', 'stock_adjust_zero']

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
    list_filter = ('store', 'status')
    search_fields = ('id', 'store__name', 'table_label', 'customer_line_user_hash')
    inlines = [OrderItemInline]
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        try:
            staff = request.user.staff
            return qs.filter(store=staff.store)
        except Staff.DoesNotExist:
            return qs.none()


class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product', 'qty', 'unit_price', 'status', 'created_at')
    list_filter = ('status', 'order__store')
    search_fields = ('order__id', 'product__sku', 'product__name')
    date_hierarchy = 'created_at'
    autocomplete_fields = ('order', 'product')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
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
    list_filter = ('store', 'movement_type')
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
        if request.user.is_superuser:
            return qs
        try:
            staff = request.user.staff
            return qs.filter(store=staff.store)
        except Staff.DoesNotExist:
            return qs.none()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
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
        if request.user.is_superuser:
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
        if request.user.is_superuser:
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
custom_site.register(IoTEvent, IoTEventAdmin)
custom_site.register(Category, CategoryAdmin)
custom_site.register(Product, ProductAdmin)
custom_site.register(Order, OrderAdmin)
custom_site.register(OrderItem, OrderItemAdmin)
custom_site.register(StockMovement, StockMovementAdmin)

# User/Group も
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
custom_site.register(User, UserAdmin)
custom_site.register(Group, GroupAdmin)

print("booking.admin loaded")