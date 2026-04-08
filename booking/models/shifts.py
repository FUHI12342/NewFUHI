"""Shift management models: ShiftPeriod, ShiftRequest, ShiftAssignment, etc."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from .core import STAFF_TYPE_CHOICES


class StoreScheduleConfig(models.Model):
    """店舗営業時間 + 予約コマ設定"""
    store = models.OneToOneField('Store', on_delete=models.CASCADE, related_name='schedule_config')
    open_hour = models.IntegerField(_('営業開始時間'), default=9)      # 0-23
    close_hour = models.IntegerField(_('営業終了時間'), default=21)     # 0-23
    SLOT_DURATION_CHOICES = [
        (30, _('30分')),
        (60, _('60分（デフォルト）')),
    ]
    slot_duration = models.IntegerField(
        _('予約枠の単位'), default=60,
        choices=SLOT_DURATION_CHOICES,
        help_text=_('カレンダーの1コマの長さ'),
    )
    min_shift_hours = models.IntegerField(
        _('最低シフト時間(時間)'), default=2,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text=_('自動調整時に割り当てる最低連続勤務時間'),
    )

    class Meta:
        app_label = 'booking'
        verbose_name = _('店舗スケジュール設定')
        verbose_name_plural = _('店舗スケジュール設定')

    def __str__(self):
        return f"{self.store.name} ({self.open_hour}:00-{self.close_hour}:00 / {self.slot_duration}分)"


class ShiftPeriod(models.Model):
    """マネージャーが作成するシフト募集期間（3ヶ月分など）"""
    STATUS_CHOICES = [
        ('open', _('募集中')),
        ('closed', _('締切')),
        ('scheduled', _('スケジュール済')),
        ('approved', _('承認済')),
    ]
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='shift_periods')
    year_month = models.DateField(_('対象年月'))  # 月初の日付
    deadline = models.DateTimeField(_('申請締切'), null=True, blank=True)
    status = models.CharField(_('状態'), max_length=20, choices=STATUS_CHOICES, default='open')
    created_by = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_demo = models.BooleanField(_('デモデータ'), default=False, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('シフト募集期間')
        verbose_name_plural = _('シフト募集期間')

    def __str__(self):
        return f"{self.store.name} {self.year_month.strftime('%Y年%m月')} ({self.get_status_display()})"


class ShiftRequest(models.Model):
    """スタッフのシフト希望"""
    PREF_CHOICES = [
        ('available', _('出勤可能')),
        ('preferred', _('希望')),
        ('unavailable', _('出勤不可')),
    ]
    period = models.ForeignKey(ShiftPeriod, on_delete=models.CASCADE, related_name='requests')
    staff = models.ForeignKey('Staff', on_delete=models.CASCADE, related_name='shift_requests')
    date = models.DateField(_('日付'), db_index=True)
    start_hour = models.IntegerField(_('開始時間'), validators=[MinValueValidator(0), MaxValueValidator(23)])
    end_hour = models.IntegerField(_('終了時間'), validators=[MinValueValidator(1), MaxValueValidator(24)])
    start_time = models.TimeField(_('開始時刻'), null=True, blank=True)
    end_time = models.TimeField(_('終了時刻'), null=True, blank=True)
    preference = models.CharField(_('希望区分'), max_length=20, choices=PREF_CHOICES, default='available')
    note = models.TextField(_('備考'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('シフト希望')
        verbose_name_plural = _('シフト希望')
        unique_together = ('period', 'staff', 'date', 'start_hour')
        indexes = [
            models.Index(fields=['period', 'date'], name='idx_shiftreq_period_date'),
            models.Index(fields=['staff', 'date'], name='idx_shiftreq_staff_date'),
        ]

    def __str__(self):
        return f"{self.staff.name} {self.date} {self.start_hour}:00-{self.end_hour}:00 ({self.get_preference_display()})"


class ShiftAssignment(models.Model):
    """確定シフト"""
    period = models.ForeignKey(ShiftPeriod, on_delete=models.CASCADE, related_name='assignments')
    staff = models.ForeignKey('Staff', on_delete=models.CASCADE, related_name='shift_assignments')
    date = models.DateField(_('日付'), db_index=True)
    start_hour = models.IntegerField(_('開始時間'), validators=[MinValueValidator(0), MaxValueValidator(23)])
    end_hour = models.IntegerField(_('終了時間'), validators=[MinValueValidator(1), MaxValueValidator(24)])
    start_time = models.TimeField(_('開始時刻'), null=True, blank=True)
    end_time = models.TimeField(_('終了時刻'), null=True, blank=True)
    store = models.ForeignKey(
        'Store', verbose_name=_('出勤店舗'),
        on_delete=models.CASCADE, null=True, blank=True,
        related_name='shift_assignments',
        help_text=_('未設定の場合はスタッフの主店舗'),
    )
    color = models.CharField(_('表示色'), max_length=7, default='#3B82F6')
    note = models.TextField(_('備考'), blank=True, default='')
    is_synced = models.BooleanField(_('Schedule同期済み'), default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_demo = models.BooleanField(_('デモデータ'), default=False, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('確定シフト')
        verbose_name_plural = _('確定シフト')
        unique_together = ('period', 'staff', 'date', 'start_hour')
        indexes = [
            models.Index(fields=['period', 'date'], name='idx_shiftasgn_period_date'),
            models.Index(fields=['staff', 'date'], name='idx_shiftasgn_staff_date'),
            models.Index(fields=['is_synced'], name='idx_shiftasgn_synced'),
            models.Index(fields=['store', 'date'], name='idx_shiftasgn_store_date'),
        ]

    def __str__(self):
        return f"{self.staff.name} {self.date} {self.start_hour}:00-{self.end_hour}:00"

    def get_store(self):
        """出勤店舗を返す（未設定なら主店舗）"""
        return self.store or self.staff.store


class ShiftTemplate(models.Model):
    """定型シフトパターン（早番・遅番・通し等）"""
    store = models.ForeignKey('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='shift_templates')
    name = models.CharField(_('テンプレート名'), max_length=100)
    start_time = models.TimeField(_('開始時刻'))
    end_time = models.TimeField(_('終了時刻'))
    color = models.CharField(_('表示色'), max_length=7, default='#3B82F6')
    is_active = models.BooleanField(_('有効'), default=True)
    sort_order = models.IntegerField(_('並び順'), default=0)

    class Meta:
        app_label = 'booking'
        verbose_name = _('シフトテンプレート')
        verbose_name_plural = _('シフトテンプレート')
        ordering = ('store', 'sort_order', 'name')

    def __str__(self):
        return f"{self.store.name} / {self.name} ({self.start_time}-{self.end_time})"


class ShiftPublishHistory(models.Model):
    """シフト公開履歴"""
    ACTION_CHOICES = [
        ('publish', _('公開')),
        ('revoke', _('撤回')),
        ('reopen', _('再募集')),
    ]
    period = models.ForeignKey(ShiftPeriod, verbose_name=_('シフト期間'), on_delete=models.CASCADE, related_name='publish_history')
    published_by = models.ForeignKey('Staff', verbose_name=_('公開者'), on_delete=models.SET_NULL, null=True, blank=True)
    published_at = models.DateTimeField(_('公開日時'), auto_now_add=True)
    assignment_count = models.IntegerField(_('シフト数'), default=0)
    note = models.TextField(_('備考'), blank=True, default='')
    action = models.CharField(_('操作'), max_length=10, choices=ACTION_CHOICES, default='publish')
    reason = models.TextField(_('理由'), blank=True, default='')

    class Meta:
        app_label = 'booking'
        verbose_name = _('シフト公開履歴')
        verbose_name_plural = _('シフト公開履歴')
        ordering = ('-published_at',)

    def __str__(self):
        return f"{self.period} - {self.get_action_display()} - {self.published_at}"


class ShiftChangeLog(models.Model):
    """個別シフト変更の監査証跡"""
    CHANGE_TYPE_CHOICES = [
        ('revised', _('修正')),
        ('deleted', _('削除')),
    ]
    assignment = models.ForeignKey(ShiftAssignment, on_delete=models.CASCADE, related_name='change_logs')
    changed_by = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    change_type = models.CharField(_('変更種別'), max_length=20, choices=CHANGE_TYPE_CHOICES)
    old_values = models.JSONField(_('変更前'), default=dict)
    new_values = models.JSONField(_('変更後'), default=dict)
    reason = models.TextField(_('変更理由'), blank=True, default='')

    class Meta:
        app_label = 'booking'
        verbose_name = _('シフト変更ログ')
        verbose_name_plural = _('シフト変更ログ')
        ordering = ('-changed_at',)

    def __str__(self):
        return f"{self.assignment} - {self.get_change_type_display()} - {self.changed_at}"


class StoreClosedDate(models.Model):
    """店舗の休業日（シフト自動配置で除外）"""
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='closed_dates')
    date = models.DateField(_('休業日'))
    reason = models.CharField(_('理由'), max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        unique_together = ('store', 'date')
        verbose_name = _('休業日')
        verbose_name_plural = _('休業日')

    def __str__(self):
        return f"{self.store.name} {self.date} {self.reason}"


class ShiftStaffRequirement(models.Model):
    """曜日ごとのデフォルト必要人数"""
    DAY_CHOICES = [
        (0, _('月曜')), (1, _('火曜')), (2, _('水曜')), (3, _('木曜')),
        (4, _('金曜')), (5, _('土曜')), (6, _('日曜')),
    ]
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='staff_requirements')
    day_of_week = models.IntegerField(_('曜日'), choices=DAY_CHOICES)
    staff_type = models.CharField(_('従業員種別'), max_length=20, choices=STAFF_TYPE_CHOICES)
    required_count = models.PositiveIntegerField(_('必要人数'), default=1)

    class Meta:
        app_label = 'booking'
        unique_together = ('store', 'day_of_week', 'staff_type')
        ordering = ['day_of_week', 'staff_type']
        verbose_name = _('シフト必要人数（曜日別）')
        verbose_name_plural = _('シフト必要人数（曜日別）')

    def __str__(self):
        return f"{self.store.name} {self.get_day_of_week_display()} {self.get_staff_type_display()} ×{self.required_count}"


class ShiftStaffRequirementOverride(models.Model):
    """特定日の必要人数オーバーライド（棚卸し日など）"""
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='staff_requirement_overrides')
    date = models.DateField(_('日付'))
    staff_type = models.CharField(_('従業員種別'), max_length=20, choices=STAFF_TYPE_CHOICES)
    required_count = models.PositiveIntegerField(_('必要人数'), default=1)
    reason = models.CharField(_('理由'), max_length=100, blank=True, default='')

    class Meta:
        app_label = 'booking'
        unique_together = ('store', 'date', 'staff_type')
        ordering = ['date', 'staff_type']
        verbose_name = _('シフト必要人数（日付指定）')
        verbose_name_plural = _('シフト必要人数（日付指定）')

    def __str__(self):
        return f"{self.store.name} {self.date} {self.get_staff_type_display()} ×{self.required_count}"


class ShiftVacancy(models.Model):
    """シフト不足枠（再募集用）— auto_schedule後に定員未達の時間帯を記録"""
    VACANCY_STATUS_CHOICES = [
        ('open', _('募集中')),
        ('filled', _('充足')),
        ('cancelled', _('取消')),
    ]
    period = models.ForeignKey(ShiftPeriod, on_delete=models.CASCADE, related_name='vacancies')
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='shift_vacancies')
    date = models.DateField(_('日付'), db_index=True)
    start_hour = models.IntegerField(_('開始時間'), validators=[MinValueValidator(0), MaxValueValidator(23)])
    end_hour = models.IntegerField(_('終了時間'), validators=[MinValueValidator(1), MaxValueValidator(24)])
    staff_type = models.CharField(_('従業員種別'), max_length=20, choices=STAFF_TYPE_CHOICES)
    required_count = models.PositiveIntegerField(_('必要人数'))
    assigned_count = models.PositiveIntegerField(_('配置済み人数'), default=0)
    status = models.CharField(_('状態'), max_length=10, choices=VACANCY_STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        unique_together = ('period', 'date', 'start_hour', 'staff_type')
        ordering = ['date', 'start_hour']
        verbose_name = _('シフト不足枠')
        verbose_name_plural = _('シフト不足枠')

    def __str__(self):
        return (
            f"{self.store.name} {self.date} {self.start_hour}:00-{self.end_hour}:00 "
            f"{self.get_staff_type_display()} ({self.assigned_count}/{self.required_count})"
        )

    @property
    def shortage(self):
        return max(0, self.required_count - self.assigned_count)


class ShiftSwapRequest(models.Model):
    """シフト交代・欠勤申請"""
    REQUEST_TYPE_CHOICES = [
        ('swap', _('交代')),
        ('cover', _('カバー')),
        ('absence', _('欠勤')),
    ]
    SWAP_STATUS_CHOICES = [
        ('pending', _('申請中')),
        ('approved', _('承認')),
        ('rejected', _('却下')),
        ('cancelled', _('取消')),
    ]
    assignment = models.ForeignKey(ShiftAssignment, on_delete=models.CASCADE, related_name='swap_requests')
    request_type = models.CharField(_('申請種別'), max_length=10, choices=REQUEST_TYPE_CHOICES)
    requested_by = models.ForeignKey(
        'Staff', on_delete=models.CASCADE, related_name='swap_requests_made',
        verbose_name=_('申請者'),
    )
    cover_staff = models.ForeignKey(
        'Staff', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='swap_requests_received', verbose_name=_('交代先スタッフ'),
    )
    reason = models.TextField(_('理由'))
    status = models.CharField(_('状態'), max_length=10, choices=SWAP_STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        'Staff', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='swap_requests_reviewed', verbose_name=_('承認者'),
    )
    reviewed_at = models.DateTimeField(_('承認日時'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        ordering = ['-created_at']
        verbose_name = _('シフト交代・欠勤申請')
        verbose_name_plural = _('シフト交代・欠勤申請')

    def __str__(self):
        return (
            f"{self.requested_by.name} {self.get_request_type_display()} "
            f"{self.assignment.date} ({self.get_status_display()})"
        )
