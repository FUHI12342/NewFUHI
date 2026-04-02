"""Orders admin: Category, Product, EC, Order, StockMovement, ShippingConfig."""
from django.contrib import admin
from django.db.models import F
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from ..admin_site import custom_site
from ..models import (
    Staff, Category, Product, ProductTranslation,
    ECCategory, ECProduct,
    Order, OrderItem, StockMovement, ShippingConfig,
)
from .helpers import _is_owner_or_super


class ProductTranslationInline(admin.TabularInline):
    model = ProductTranslation
    extra = 0


class CategoryAdmin(admin.ModelAdmin):
    """店内メニュー用カテゴリ（is_restaurant_menu=True のみ）"""
    list_display = ('store', 'name', 'sort_order')
    list_display_links = ('name',)
    search_fields = ('name', 'store__name')
    list_editable = ('sort_order',)
    list_per_page = 10
    ordering = ('store', 'sort_order', 'name')

    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(is_restaurant_menu=True)
        if _is_owner_or_super(request):
            return qs
        try:
            staff = request.user.staff
            return qs.filter(store=staff.store)
        except Staff.DoesNotExist:
            return qs.none()

    def save_model(self, request, obj, form, change):
        obj.is_restaurant_menu = True
        super().save_model(request, obj, form, change)

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
    """店内メニュー用商品（is_restaurant_menu カテゴリのみ）"""
    list_display = (
        'short_store',
        'sku',
        'short_name',
        'short_category',
        'price',
        'stock',
        'low_stock_threshold',
        'is_active',
        'is_sold_out',
        'display_image',
    )
    list_display_links = ('sku', 'short_name')

    search_fields = ('sku', 'name', 'store__name')
    list_editable = ('price', 'stock', 'low_stock_threshold', 'is_active')
    inlines = [ProductTranslationInline]
    autocomplete_fields = ('category',)
    ordering = ('store', 'category', 'name')
    list_per_page = 10

    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(
            category__is_restaurant_menu=True,
        )
        if _is_owner_or_super(request):
            return qs
        try:
            return qs.filter(store=request.user.staff.store)
        except (Staff.DoesNotExist, AttributeError):
            return qs.none()

    def short_store(self, obj):
        name = obj.store.name if obj.store else ''
        if len(name) > 8:
            return format_html('<span title="{}">{}&hellip;</span>', name, name[:8])
        return name
    short_store.short_description = _('店舗')
    short_store.admin_order_field = 'store__name'

    def short_name(self, obj):
        if len(obj.name) > 12:
            return format_html('<span title="{}">{}&hellip;</span>', obj.name, obj.name[:12])
        return obj.name
    short_name.short_description = _('商品名')
    short_name.admin_order_field = 'name'

    def short_category(self, obj):
        name = obj.category.name if obj.category else '-'
        if len(name) > 8:
            return format_html('<span title="{}">{}&hellip;</span>', name, name[:8])
        return name
    short_category.short_description = _('カテゴリ')
    short_category.admin_order_field = 'category__name'

    def is_sold_out(self, obj):
        return obj.stock <= 0
    is_sold_out.short_description = _('売切')
    is_sold_out.boolean = True
    is_sold_out.admin_order_field = 'stock'

    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="40" height="40" style="object-fit:cover;border-radius:4px;" />', obj.image.url)
        return '-'
    display_image.short_description = _('画像')

    actions = ['clear_low_stock_notification', 'stock_in', 'stock_out', 'stock_adjust_zero']

    @admin.action(description=_('閾値通知フラグを解除（last_low_stock_notified_at を空にする）'))
    def clear_low_stock_notification(self, request, queryset):
        queryset.update(last_low_stock_notified_at=None)

    @admin.action(description=_('入庫（1個）'))
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

    @admin.action(description=_('出庫（1個、在庫不足時はスキップ）'))
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

    @admin.action(description=_('棚卸（在庫を0に調整）'))
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


class ECCategoryAdmin(admin.ModelAdmin):
    """EC商品カテゴリ（is_restaurant_menu=False のみ）"""
    list_display = ('store', 'name', 'sort_order')
    list_display_links = ('name',)
    search_fields = ('name', 'store__name')
    list_editable = ('sort_order',)
    list_per_page = 10
    ordering = ('store', 'sort_order', 'name')

    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(is_restaurant_menu=False)
        if _is_owner_or_super(request):
            return qs
        try:
            return qs.filter(store=request.user.staff.store)
        except (Staff.DoesNotExist, AttributeError):
            return qs.none()

    def save_model(self, request, obj, form, change):
        obj.is_restaurant_menu = False
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        if _is_owner_or_super(request):
            return True
        try:
            staff = request.user.staff
            return staff.is_store_manager
        except Staff.DoesNotExist:
            return False

    def has_add_permission(self, request):
        return self.has_change_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        from ..admin_site import get_user_role, _get_allowed_models_for_role
        role = get_user_role(request)
        if role == 'none':
            return False
        allowed = _get_allowed_models_for_role(role)
        return allowed is None or 'eccategory' in allowed

    def has_module_permission(self, request):
        return self.has_view_permission(request)


class ECProductAdmin(admin.ModelAdmin):
    """EC商品（is_ec_visible=True / ECカテゴリのみ）"""
    list_display = (
        'short_store', 'sku', 'short_name', 'short_category',
        'price', 'stock', 'low_stock_threshold',
        'is_active', 'is_sold_out', 'display_image',
    )
    list_display_links = ('sku', 'short_name')
    search_fields = ('sku', 'name', 'store__name')
    list_editable = ('price', 'stock', 'low_stock_threshold', 'is_active')
    inlines = [ProductTranslationInline]
    ordering = ('store', 'category', 'name')
    list_per_page = 10

    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(is_ec_visible=True)
        if _is_owner_or_super(request):
            return qs
        try:
            return qs.filter(store=request.user.staff.store)
        except (Staff.DoesNotExist, AttributeError):
            return qs.none()

    def save_model(self, request, obj, form, change):
        obj.is_ec_visible = True
        super().save_model(request, obj, form, change)

    def short_store(self, obj):
        name = obj.store.name if obj.store else ''
        if len(name) > 8:
            return format_html('<span title="{}">{}&hellip;</span>', name, name[:8])
        return name
    short_store.short_description = _('店舗')
    short_store.admin_order_field = 'store__name'

    def short_name(self, obj):
        if len(obj.name) > 12:
            return format_html('<span title="{}">{}&hellip;</span>', obj.name, obj.name[:12])
        return obj.name
    short_name.short_description = _('商品名')
    short_name.admin_order_field = 'name'

    def short_category(self, obj):
        name = obj.category.name if obj.category else '-'
        if len(name) > 8:
            return format_html('<span title="{}">{}&hellip;</span>', name, name[:8])
        return name
    short_category.short_description = _('カテゴリ')
    short_category.admin_order_field = 'category__name'

    def is_sold_out(self, obj):
        return obj.stock <= 0
    is_sold_out.short_description = _('売切')
    is_sold_out.boolean = True
    is_sold_out.admin_order_field = 'stock'

    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="40" height="40" style="object-fit:cover;border-radius:4px;" />', obj.image.url)
        return '-'
    display_image.short_description = _('画像')

    actions = ['stock_in', 'stock_out']

    @admin.action(description=_('入庫（1個）'))
    def stock_in(self, request, queryset):
        count = 0
        for product in queryset:
            StockMovement.objects.create(
                store=product.store, product=product,
                movement_type=StockMovement.TYPE_IN, qty=1,
                by_staff=getattr(request.user, 'staff', None),
                note='EC admin: stock_in',
            )
            product.stock += 1
            product.save()
            count += 1
        self.message_user(request, f'{count} 件入庫しました。')

    @admin.action(description=_('出庫（1個）'))
    def stock_out(self, request, queryset):
        count = 0
        for product in queryset:
            if product.stock < 1:
                continue
            StockMovement.objects.create(
                store=product.store, product=product,
                movement_type=StockMovement.TYPE_OUT, qty=1,
                by_staff=getattr(request.user, 'staff', None),
                note='EC admin: stock_out',
            )
            product.stock -= 1
            product.save()
            count += 1
        self.message_user(request, f'{count} 件出庫しました。')

    def has_change_permission(self, request, obj=None):
        if _is_owner_or_super(request):
            return True
        try:
            staff = request.user.staff
            return staff.is_store_manager
        except Staff.DoesNotExist:
            return False

    def has_add_permission(self, request):
        return self.has_change_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        from ..admin_site import get_user_role, _get_allowed_models_for_role
        role = get_user_role(request)
        if role == 'none':
            return False
        allowed = _get_allowed_models_for_role(role)
        return allowed is None or 'ecproduct' in allowed

    def has_module_permission(self, request):
        return self.has_view_permission(request)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('product',)


class ChannelGroupFilter(admin.SimpleListFilter):
    """注文チャネルを「店内」「EC」にグループ化するフィルタ"""
    title = _('注文種別')
    parameter_name = 'channel_group'

    def lookups(self, request, model_admin):
        return [
            ('instore', _('店内注文')),
            ('ec', _('EC注文')),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'instore':
            return queryset.filter(channel__in=['pos', 'table', 'reservation'])
        if self.value() == 'ec':
            return queryset.filter(channel='ec')
        return queryset


class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'store', 'channel', 'status', 'customer_name',
        'shipping_status', 'table_label', 'schedule', 'created_at',
    )
    list_filter = (ChannelGroupFilter, 'status', 'payment_status', 'shipping_status')
    search_fields = ('id', 'store__name', 'table_label', 'customer_line_user_hash', 'customer_name', 'customer_email')
    inlines = [OrderItemInline]
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 10
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    fieldsets = (
        (None, {
            'fields': ('store', 'schedule', 'channel', 'table_label', 'table_seat', 'status', 'payment_status', 'discount_amount', 'tax_amount'),
        }),
        (_('EC顧客情報'), {
            'classes': ('collapse',),
            'fields': ('customer_name', 'customer_email', 'customer_phone', 'customer_address'),
        }),
        (_('発送情報'), {
            'classes': ('collapse',),
            'fields': ('shipping_status', 'tracking_number', 'shipped_at', 'shipping_note'),
        }),
        (_('タイムスタンプ'), {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    actions = ['mark_shipped', 'delete_selected_orders']

    @admin.action(description=_('発送済みにする'))
    def mark_shipped(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(shipping_status='pending').update(
            shipping_status='shipped', shipped_at=timezone.now(),
        )
        self.message_user(request, f'{count} 件の注文を発送済みにしました。')

    @admin.action(description=_('選択した注文を削除'))
    def delete_selected_orders(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'{count} 件の注文を削除しました。')

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
    list_per_page = 10
    ordering = ('-created_at',)

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


class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'store', 'product', 'movement_type', 'qty', 'by_staff', 'note')
    list_per_page = 10
    ordering = ('-created_at',)

    search_fields = ('product__sku', 'product__name', 'note', 'store__name')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    autocomplete_fields = ('product', 'by_staff', 'store')

    actions = ['recompute_stock_from_movements']

    @admin.action(description=_('（上級）入出庫履歴の合計で在庫を再計算して反映'))
    def recompute_stock_from_movements(self, request, queryset):
        """選択した入出庫履歴の product ごとに合計し、Product.stock に反映する。
        注意: 選択範囲のみで計算されるので、運用では「全期間」を対象にする想定。
        """
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


class ShippingConfigAdmin(admin.ModelAdmin):
    """送料設定"""
    list_display = ('store', 'is_enabled', 'shipping_fee', 'free_shipping_threshold')
    list_per_page = 10
    ordering = ('store',)
    fieldsets = (
        (None, {'fields': ('store', 'is_enabled', 'shipping_fee', 'free_shipping_threshold')}),
        (_('配達情報'), {'fields': ('delivery_area', 'note')}),
    )

    def has_change_permission(self, request, obj=None):
        if _is_owner_or_super(request):
            return True
        try:
            return request.user.staff.is_store_manager
        except Staff.DoesNotExist:
            return False

    def has_add_permission(self, request):
        return self.has_change_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        from ..admin_site import get_user_role, _get_allowed_models_for_role
        role = get_user_role(request)
        if role == 'none':
            return False
        allowed = _get_allowed_models_for_role(role)
        return allowed is None or 'shippingconfig' in allowed

    def has_module_permission(self, request):
        return self.has_view_permission(request)


# Registration
custom_site.register(Category, CategoryAdmin)
custom_site.register(Product, ProductAdmin)
custom_site.register(ECCategory, ECCategoryAdmin)
custom_site.register(ECProduct, ECProductAdmin)
custom_site.register(Order, OrderAdmin)
custom_site.register(ShippingConfig, ShippingConfigAdmin)
# StockMovement: 管理画面から廃止（モデルは残す）
# custom_site.register(StockMovement, StockMovementAdmin)
