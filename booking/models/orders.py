"""Order, OrderItem, StockMovement, POSTransaction, ShippingConfig models."""
from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db import transaction


class Order(models.Model):
    """注文（セッション/会計単位のかたまり）"""

    STATUS_OPEN = 'OPEN'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (STATUS_OPEN, 'Open'),
        (STATUS_CLOSED, 'Closed'),
    )
    PAYMENT_STATUS_CHOICES = [
        ('pending', _('未払い')),
        ('partial', _('一部支払')),
        ('paid', _('支払済')),
        ('refunded', _('返金済')),
    ]
    CHANNEL_CHOICES = [
        ('ec', _('ECショップ')),
        ('pos', _('POS')),
        ('table', _('テーブル注文')),
        ('reservation', _('予約')),
    ]

    store = models.ForeignKey('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='orders')
    schedule = models.ForeignKey(
        'Schedule',
        verbose_name=_('予約'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )

    channel = models.CharField(_('注文チャネル'), max_length=20, choices=CHANNEL_CHOICES, default='pos', db_index=True)
    customer_line_user_hash = models.CharField(_('顧客LINEハッシュ'), max_length=64, null=True, blank=True, db_index=True)
    table_label = models.CharField(_('席/テーブル'), max_length=50, blank=True, default='')
    table_seat = models.ForeignKey(
        'TableSeat', verbose_name=_('席'), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders',
    )

    status = models.CharField(_('状態'), max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    payment_status = models.CharField(_('支払状態'), max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', db_index=True)
    discount_amount = models.IntegerField(_('割引額'), default=0)
    tax_amount = models.IntegerField(_('税額'), default=0)

    # EC顧客情報
    customer_name = models.CharField(_('顧客名'), max_length=100, blank=True, default='')
    customer_email = models.EmailField(_('メールアドレス'), blank=True, default='')
    customer_phone = models.CharField(_('電話番号'), max_length=20, blank=True, default='')
    customer_address = models.TextField(_('配送先住所'), blank=True, default='')

    # 発送管理
    SHIPPING_STATUS_CHOICES = [
        ('none', _('発送不要')),
        ('pending', _('発送待ち')),
        ('shipped', _('発送済み')),
        ('delivered', _('配達完了')),
    ]
    shipping_status = models.CharField(
        _('発送ステータス'), max_length=20,
        choices=SHIPPING_STATUS_CHOICES, default='none', db_index=True,
    )
    tracking_number = models.CharField(_('追跡番号'), max_length=100, blank=True, default='')
    shipped_at = models.DateTimeField(_('発送日時'), null=True, blank=True)
    shipping_note = models.TextField(_('発送メモ'), blank=True, default='')
    shipping_fee = models.PositiveIntegerField(_('送料'), default=0)

    is_demo = models.BooleanField(_('デモデータ'), default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('注文履歴')
        verbose_name_plural = _('注文履歴')
        indexes = [
            models.Index(fields=['store', 'status', 'created_at']),
            models.Index(fields=['customer_line_user_hash', 'created_at']),
        ]

    def __str__(self):
        return f"Order#{self.id} {self.store.name} ({self.status})"

    @property
    def all_items_served(self):
        """全アイテムが配膳済みかどうか"""
        items = self.items.all()
        return items.exists() and all(i.status == 'SERVED' for i in items)


class OrderItem(models.Model):
    """注文明細"""

    STATUS_ORDERED = 'ORDERED'
    STATUS_PREPARING = 'PREPARING'
    STATUS_SERVED = 'SERVED'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (STATUS_ORDERED, 'Ordered'),
        (STATUS_PREPARING, 'Preparing'),
        (STATUS_SERVED, 'Served'),
        (STATUS_CLOSED, 'Closed'),
    )

    order = models.ForeignKey(Order, verbose_name=_('注文'), on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', verbose_name=_('商品'), on_delete=models.PROTECT, related_name='order_items')

    qty = models.IntegerField(_('数量'), default=1)
    unit_price = models.IntegerField(_('単価'), default=0)

    status = models.CharField(_('状態'), max_length=20, choices=STATUS_CHOICES, default=STATUS_ORDERED, db_index=True)
    note = models.CharField(_('備考'), max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('注文明細')
        verbose_name_plural = _('注文明細')
        indexes = [
            models.Index(fields=['order', 'status', 'created_at']),
            models.Index(fields=['product', 'created_at']),
        ]

    def __str__(self):
        return f"OrderItem#{self.id} {self.product.sku} x{self.qty} ({self.status})"


class StockMovement(models.Model):
    """入出庫履歴（棚卸/入庫QR/注文引当のベース）"""

    TYPE_IN = 'IN'
    TYPE_OUT = 'OUT'
    TYPE_ADJUST = 'ADJUST'
    TYPE_CHOICES = (
        (TYPE_IN, _('入庫')),
        (TYPE_OUT, _('出庫')),
        (TYPE_ADJUST, _('棚卸調整')),
    )

    store = models.ForeignKey('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='stock_movements')
    product = models.ForeignKey('Product', verbose_name=_('商品'), on_delete=models.PROTECT, related_name='stock_movements')

    movement_type = models.CharField(_('種別'), max_length=10, choices=TYPE_CHOICES, db_index=True)
    qty = models.IntegerField(_('数量'))

    by_staff = models.ForeignKey('Staff', verbose_name=_('実施スタッフ'), on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(_('メモ'), max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('入出庫履歴')
        verbose_name_plural = _('入出庫履歴')
        indexes = [
            models.Index(fields=['store', 'created_at']),
            models.Index(fields=['product', 'created_at']),
            models.Index(fields=['movement_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.store.name} {self.product.sku} {self.movement_type} {self.qty}"


def apply_stock_movement(
    product,
    movement_type: str,
    qty: int,
    *,
    allow_negative: bool = False,
) -> None:
    """在庫数を更新するユーティリティ（同時更新に強い版）。

    - Product行を select_for_update() でロックしてから更新
    - IN: +abs(qty)
    - OUT: -abs(qty)
    - ADJUST: qty(差分)
    """
    from .core import Product  # avoid circular import at module level

    q = int(qty)

    if movement_type == StockMovement.TYPE_IN:
        delta = abs(q)
    elif movement_type == StockMovement.TYPE_OUT:
        delta = -abs(q)
    elif movement_type == StockMovement.TYPE_ADJUST:
        delta = q
    else:
        raise ValueError("invalid movement_type")

    with transaction.atomic():
        locked = Product.objects.select_for_update().get(pk=product.pk)

        new_stock = int(locked.stock) + int(delta)
        if (not allow_negative) and new_stock < 0:
            raise ValueError("stock would become negative")

        # 在庫更新（競合に強い）
        Product.objects.filter(pk=locked.pk).update(stock=F("stock") + delta)

        # 更新後の状態で閾値判定
        locked.refresh_from_db(fields=["stock", "low_stock_threshold", "last_low_stock_notified_at", "updated_at"])

        # 在庫が閾値より上に戻ったら通知フラグ解除
        if int(locked.stock) > int(locked.low_stock_threshold):
            if locked.last_low_stock_notified_at is not None:
                Product.objects.filter(pk=locked.pk).update(last_low_stock_notified_at=None)
                locked.last_low_stock_notified_at = None

        # 呼び出し元インスタンスにも反映
        product.stock = locked.stock
        product.last_low_stock_notified_at = locked.last_low_stock_notified_at
        product.updated_at = locked.updated_at


class POSTransaction(models.Model):
    """POS決済記録"""
    order = models.OneToOneField(Order, verbose_name=_('注文'), on_delete=models.CASCADE, related_name='pos_transaction')
    payment_method = models.ForeignKey('PaymentMethod', verbose_name=_('決済方法'), on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.IntegerField(_('合計金額'), default=0)
    tax_amount = models.IntegerField(_('税額'), default=0)
    discount_amount = models.IntegerField(_('割引額'), default=0)
    cash_received = models.IntegerField(_('受取金額'), null=True, blank=True)
    change_given = models.IntegerField(_('お釣り'), null=True, blank=True)
    receipt_number = models.CharField(_('レシート番号'), max_length=20, unique=True)
    staff = models.ForeignKey('Staff', verbose_name=_('担当'), on_delete=models.SET_NULL, null=True, blank=True)
    completed_at = models.DateTimeField(_('完了日時'), null=True, blank=True)
    is_demo = models.BooleanField(_('デモデータ'), default=False, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('POS決済履歴')
        verbose_name_plural = _('POS決済履歴')
        indexes = [
            models.Index(fields=['receipt_number']),
            models.Index(fields=['completed_at']),
        ]

    def __str__(self):
        return f'POS#{self.receipt_number} ¥{self.total_amount:,}'


class ShippingConfig(models.Model):
    """送料設定"""
    store = models.OneToOneField('Store', on_delete=models.CASCADE, related_name='shipping_config')
    is_enabled = models.BooleanField(_('送料を有効にする'), default=False)
    shipping_fee = models.PositiveIntegerField(_('送料（税込）'), default=0)
    free_shipping_threshold = models.PositiveIntegerField(
        _('送料無料の注文金額'), default=0,
        help_text=_('0の場合は常に送料がかかります'),
    )
    delivery_area = models.TextField(_('配達対応範囲'), blank=True, default='')
    note = models.TextField(_('送料に関する備考'), blank=True, default='')

    class Meta:
        app_label = 'booking'
        verbose_name = _('送料設定')
        verbose_name_plural = _('送料設定')

    def __str__(self):
        return f'{self.store.name} 送料設定'
