"""HR models: EmploymentContract, WorkAttendance, Payroll, Evaluation, Attendance TOTP."""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from decimal import Decimal


class EvaluationCriteria(models.Model):
    """評価基準マスタ"""
    store = models.ForeignKey(
        'Store', verbose_name=_('店舗'), on_delete=models.CASCADE,
        related_name='evaluation_criteria',
    )
    name = models.CharField(_('評価項目名'), max_length=100)
    description = models.TextField(_('説明'), blank=True, default='')
    CATEGORY_CHOICES = [
        ('attendance', _('出勤・勤怠')),
        ('performance', _('パフォーマンス')),
        ('skill', _('スキル')),
        ('attitude', _('勤務態度')),
        ('customer', _('顧客対応')),
    ]
    category = models.CharField(
        _('カテゴリ'), max_length=20, choices=CATEGORY_CHOICES,
        default='performance',
    )
    weight = models.FloatField(
        _('重み (0.0-1.0)'), default=1.0,
        help_text=_('総合スコア計算時の重み付け'),
    )
    is_auto = models.BooleanField(
        _('自動評価'), default=False,
        help_text=_('勤怠データから自動計算する項目'),
    )
    sort_order = models.IntegerField(_('表示順'), default=0)
    is_active = models.BooleanField(_('有効'), default=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('評価基準')
        verbose_name_plural = _('評価基準')
        ordering = ('store', 'sort_order', 'name')
        unique_together = ('store', 'name')

    def __str__(self):
        return f'{self.store.name} / {self.name}'


class StaffEvaluation(models.Model):
    """スタッフ評価レコード"""
    staff = models.ForeignKey(
        'Staff', verbose_name=_('スタッフ'), on_delete=models.CASCADE,
        related_name='evaluations',
    )
    evaluator = models.ForeignKey(
        'Staff', verbose_name=_('評価者'), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='given_evaluations',
    )
    period_start = models.DateField(_('評価期間（開始）'))
    period_end = models.DateField(_('評価期間（終了）'))

    # Auto-calculated from attendance
    attendance_rate = models.FloatField(
        _('出勤率 (%)'), null=True, blank=True,
        help_text=_('シフト割当に対する実際の出勤率'),
    )
    punctuality_score = models.FloatField(
        _('定時出勤スコア (0-5)'), null=True, blank=True,
        help_text=_('遅刻・早退の少なさ'),
    )
    total_work_hours = models.FloatField(
        _('総勤務時間'), null=True, blank=True,
    )

    # Manual evaluation
    scores = models.JSONField(
        _('項目別スコア'), default=dict, blank=True,
        help_text=_('{"criteria_id": score} 形式。各スコアは1-5'),
    )
    overall_score = models.FloatField(
        _('総合評価 (1.0-5.0)'), null=True, blank=True,
    )

    GRADE_CHOICES = [
        ('S', _('S (卓越)')),
        ('A', _('A (優秀)')),
        ('B', _('B (良好)')),
        ('C', _('C (標準)')),
        ('D', _('D (要改善)')),
    ]
    grade = models.CharField(
        _('評価ランク'), max_length=2, choices=GRADE_CHOICES,
        blank=True, default='',
    )

    comment = models.TextField(_('評価コメント'), blank=True, default='')
    staff_comment = models.TextField(
        _('スタッフ自己評価'), blank=True, default='',
        help_text=_('スタッフ本人のコメント'),
    )

    SOURCE_CHOICES = [
        ('auto', _('自動評価')),
        ('manual', _('手動評価')),
        ('mixed', _('自動+手動')),
    ]
    source = models.CharField(
        _('評価ソース'), max_length=10, choices=SOURCE_CHOICES,
        default='manual',
    )

    is_published = models.BooleanField(
        _('公開済み'), default=False,
        help_text=_('チェックするとスタッフ本人に表示されます'),
    )
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('スタッフ評価')
        verbose_name_plural = _('スタッフ評価')
        ordering = ('-period_end', 'staff__name')
        indexes = [
            models.Index(fields=['staff', '-period_end']),
        ]
        unique_together = ('staff', 'period_start', 'period_end')

    def __str__(self):
        return (f'{self.staff.name} ({self.period_start} ~ {self.period_end}) '
                f'[{self.grade or "未評価"}]')

    def calculate_grade(self):
        """overall_score から評価ランクを算出"""
        if self.overall_score is None:
            return ''
        score = self.overall_score
        if score >= 4.5:
            return 'S'
        elif score >= 3.5:
            return 'A'
        elif score >= 2.5:
            return 'B'
        elif score >= 1.5:
            return 'C'
        return 'D'


class EmploymentContract(models.Model):
    """雇用契約（Staff 1:1）"""
    EMPLOYMENT_TYPE_CHOICES = [
        ('full_time', _('正社員')),
        ('part_time', _('パート・アルバイト')),
        ('contract', _('契約社員')),
    ]
    PAY_TYPE_CHOICES = [
        ('hourly', _('時給')),
        ('monthly', _('月給')),
    ]

    staff = models.OneToOneField(
        'Staff', verbose_name=_('スタッフ'), on_delete=models.CASCADE, related_name='employment_contract',
    )
    employment_type = models.CharField(_('雇用形態'), max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default='part_time')
    pay_type = models.CharField(_('給与形態'), max_length=10, choices=PAY_TYPE_CHOICES, default='hourly')
    hourly_rate = models.IntegerField(_('時給（円）'), default=0, help_text=_('時給制の場合に設定'))
    monthly_salary = models.IntegerField(_('月給（円）'), default=0, help_text=_('月給制の場合に設定'))

    commute_allowance = models.IntegerField(_('通勤手当（円/月）'), default=0)
    housing_allowance = models.IntegerField(_('住宅手当（円/月）'), default=0)
    family_allowance = models.IntegerField(_('家族手当（円/月）'), default=0)

    standard_monthly_remuneration = models.IntegerField(
        _('標準報酬月額（円）'), default=0,
        help_text=_('社会保険料計算の基準額。4〜6月の平均報酬から算定。'),
    )
    resident_tax_monthly = models.IntegerField(_('住民税月額（円）'), default=0, help_text=_('特別徴収の月額'))

    birth_date = models.DateField(_('生年月日'), null=True, blank=True, help_text=_('介護保険適用判定に使用（40歳以上）'))
    contract_start = models.DateField(_('契約開始日'), null=True, blank=True)
    contract_end = models.DateField(_('契約終了日'), null=True, blank=True)
    is_active = models.BooleanField(_('有効'), default=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('雇用契約')
        verbose_name_plural = _('雇用契約')

    def __str__(self):
        return f'{self.staff.name} ({self.get_employment_type_display()} / {self.get_pay_type_display()})'


class WorkAttendance(models.Model):
    """勤怠記録"""
    SOURCE_CHOICES = [
        ('shift', _('シフトから自動生成')),
        ('manual', _('手動入力')),
        ('corrected', _('修正済み')),
        ('qr', _('QR打刻')),
    ]

    staff = models.ForeignKey('Staff', verbose_name=_('スタッフ'), on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(_('日付'), db_index=True)
    clock_in = models.TimeField(_('出勤時刻'), null=True, blank=True)
    clock_out = models.TimeField(_('退勤時刻'), null=True, blank=True)

    regular_minutes = models.IntegerField(_('通常勤務（分）'), default=0)
    overtime_minutes = models.IntegerField(_('残業（分）'), default=0)
    late_night_minutes = models.IntegerField(_('深夜勤務（分）'), default=0)
    holiday_minutes = models.IntegerField(_('休日勤務（分）'), default=0)
    break_minutes = models.IntegerField(_('休憩（分）'), default=0)

    qr_clock_in = models.DateTimeField(_('QR出勤日時'), null=True, blank=True)
    qr_clock_out = models.DateTimeField(_('QR退勤日時'), null=True, blank=True)

    source = models.CharField(_('データソース'), max_length=20, choices=SOURCE_CHOICES, default='shift')
    source_assignment = models.ForeignKey(
        'ShiftAssignment', verbose_name=_('元シフト'), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='derived_attendances',
    )

    class Meta:
        app_label = 'booking'
        verbose_name = _('勤怠記録')
        verbose_name_plural = _('勤怠記録')
        unique_together = ('staff', 'date')
        indexes = [
            models.Index(fields=['staff', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f'{self.staff.name} {self.date} ({self.get_source_display()})'

    @property
    def total_work_minutes(self):
        return self.regular_minutes + self.overtime_minutes + self.late_night_minutes + self.holiday_minutes


class PayrollPeriod(models.Model):
    """給与計算期間"""
    STATUS_CHOICES = [
        ('draft', _('下書き')),
        ('calculating', _('計算中')),
        ('confirmed', _('確定')),
        ('paid', _('支払済')),
    ]

    store = models.ForeignKey('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='payroll_periods')
    year_month = models.CharField(_('対象年月'), max_length=7, help_text=_('YYYY-MM形式'))
    period_start = models.DateField(_('計算期間開始'))
    period_end = models.DateField(_('計算期間終了'))
    status = models.CharField(_('状態'), max_length=20, choices=STATUS_CHOICES, default='draft')
    payment_date = models.DateField(_('支給日'), null=True, blank=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('給与計算期間')
        verbose_name_plural = _('給与計算期間')
        unique_together = ('store', 'year_month')

    def __str__(self):
        return f'{self.store.name} {self.year_month} ({self.get_status_display()})'


class PayrollEntry(models.Model):
    """個人別給与明細"""
    period = models.ForeignKey(PayrollPeriod, verbose_name=_('給与期間'), on_delete=models.CASCADE, related_name='entries')
    staff = models.ForeignKey('Staff', verbose_name=_('スタッフ'), on_delete=models.CASCADE, related_name='payroll_entries')
    contract = models.ForeignKey(
        EmploymentContract, verbose_name=_('雇用契約'), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payroll_entries',
    )

    total_work_days = models.IntegerField(_('出勤日数'), default=0)
    total_regular_hours = models.DecimalField(_('通常勤務時間'), max_digits=6, decimal_places=2, default=0)
    total_overtime_hours = models.DecimalField(_('残業時間'), max_digits=6, decimal_places=2, default=0)
    total_late_night_hours = models.DecimalField(_('深夜勤務時間'), max_digits=6, decimal_places=2, default=0)
    total_holiday_hours = models.DecimalField(_('休日勤務時間'), max_digits=6, decimal_places=2, default=0)

    base_pay = models.IntegerField(_('基本給'), default=0)
    overtime_pay = models.IntegerField(_('残業手当'), default=0)
    late_night_pay = models.IntegerField(_('深夜手当'), default=0)
    holiday_pay = models.IntegerField(_('休日手当'), default=0)
    allowances = models.IntegerField(_('各種手当合計'), default=0, help_text=_('通勤+住宅+家族手当'))

    gross_pay = models.IntegerField(_('総支給額'), default=0)
    total_deductions = models.IntegerField(_('控除合計'), default=0)
    net_pay = models.IntegerField(_('差引支給額'), default=0)

    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('給与明細')
        verbose_name_plural = _('給与明細')
        unique_together = ('period', 'staff')

    def __str__(self):
        return f'{self.staff.name} {self.period.year_month} 総支給:{self.gross_pay:,}円'


class PayrollDeduction(models.Model):
    """控除明細行"""
    DEDUCTION_TYPE_CHOICES = [
        ('income_tax', _('所得税（源泉徴収）')),
        ('resident_tax', _('住民税')),
        ('pension', _('厚生年金')),
        ('health_insurance', _('健康保険')),
        ('employment_insurance', _('雇用保険')),
        ('long_term_care', _('介護保険')),
        ('workers_comp', _('労災保険')),
        ('other', _('その他')),
    ]

    entry = models.ForeignKey(PayrollEntry, verbose_name=_('給与明細'), on_delete=models.CASCADE, related_name='deductions')
    deduction_type = models.CharField(_('控除種別'), max_length=30, choices=DEDUCTION_TYPE_CHOICES)
    amount = models.IntegerField(_('金額'), default=0)
    is_employer_only = models.BooleanField(_('事業主負担のみ'), default=False, help_text=_('労災保険等、従業員控除なし'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('控除明細')
        verbose_name_plural = _('控除明細')

    def __str__(self):
        label = self.get_deduction_type_display()
        return f'{label}: {self.amount:,}円'


class SalaryStructure(models.Model):
    """給与体系（Store 1:1）— 社会保険料率・割増率"""
    store = models.OneToOneField('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='salary_structure')

    # 社会保険料率（従業員負担分、%表記→小数で格納）
    pension_rate = models.DecimalField(_('厚生年金料率(%)'), max_digits=5, decimal_places=3, default=Decimal('9.150'),
        help_text=_('従業員負担分 例: 9.150'))
    health_insurance_rate = models.DecimalField(_('健康保険料率(%)'), max_digits=5, decimal_places=3, default=Decimal('5.000'),
        help_text=_('従業員負担分 例: 5.000（協会けんぽ東京支部）'))
    employment_insurance_rate = models.DecimalField(_('雇用保険料率(%)'), max_digits=5, decimal_places=3, default=Decimal('0.600'),
        help_text=_('従業員負担分 例: 0.600'))
    long_term_care_rate = models.DecimalField(_('介護保険料率(%)'), max_digits=5, decimal_places=3, default=Decimal('0.820'),
        help_text=_('40歳以上のみ適用 例: 0.820'))
    workers_comp_rate = models.DecimalField(_('労災保険料率(%)'), max_digits=5, decimal_places=3, default=Decimal('0.300'),
        help_text=_('事業主全額負担（記録用） 例: 0.300'))

    # 割増率
    overtime_multiplier = models.DecimalField(_('残業割増率'), max_digits=4, decimal_places=2, default=Decimal('1.25'))
    late_night_multiplier = models.DecimalField(_('深夜割増率'), max_digits=4, decimal_places=2, default=Decimal('1.35'))
    holiday_multiplier = models.DecimalField(_('休日割増率'), max_digits=4, decimal_places=2, default=Decimal('1.50'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('給与体系')
        verbose_name_plural = _('給与体系')

    def __str__(self):
        return f'{self.store.name} 給与体系'


class AttendanceTOTPConfig(models.Model):
    """店舗ごとのTOTP設定（QR勤怠用）"""
    store = models.OneToOneField('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='totp_config')
    totp_secret = models.CharField(_('TOTPシークレット'), max_length=64)
    totp_interval = models.IntegerField(_('TOTP間隔(秒)'), default=30)
    location_lat = models.FloatField(_('緯度'), null=True, blank=True)
    location_lng = models.FloatField(_('経度'), null=True, blank=True)
    geo_fence_radius_m = models.IntegerField(_('ジオフェンス半径(m)'), default=200)
    require_geo_check = models.BooleanField(_('位置確認必須'), default=False)
    is_active = models.BooleanField(_('有効'), default=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('TOTP勤怠設定')
        verbose_name_plural = _('TOTP勤怠設定')

    def __str__(self):
        return f'{self.store.name} TOTP設定'


class AttendanceStamp(models.Model):
    """打刻ログ"""
    STAMP_TYPE_CHOICES = [
        ('clock_in', _('出勤')),
        ('clock_out', _('退勤')),
        ('break_start', _('休憩開始')),
        ('break_end', _('休憩終了')),
    ]
    staff = models.ForeignKey('Staff', verbose_name=_('スタッフ'), on_delete=models.CASCADE, related_name='attendance_stamps')
    stamp_type = models.CharField(_('打刻種別'), max_length=20, choices=STAMP_TYPE_CHOICES)
    stamped_at = models.DateTimeField(_('打刻日時'), auto_now_add=True)
    totp_used = models.CharField(_('使用TOTP'), max_length=10, blank=True, default='')
    ip_address = models.GenericIPAddressField(_('IPアドレス'), null=True, blank=True)
    user_agent = models.TextField(_('User-Agent'), blank=True, default='')
    latitude = models.FloatField(_('緯度'), null=True, blank=True)
    longitude = models.FloatField(_('経度'), null=True, blank=True)
    is_valid = models.BooleanField(_('有効'), default=True)
    invalidation_reason = models.CharField(_('無効理由'), max_length=100, blank=True, default='')

    class Meta:
        app_label = 'booking'
        verbose_name = _('打刻ログ')
        verbose_name_plural = _('打刻ログ')
        ordering = ('-stamped_at',)
        indexes = [
            models.Index(fields=['staff', 'stamped_at']),
            models.Index(fields=['stamp_type', 'stamped_at']),
        ]

    def __str__(self):
        return f'{self.staff.name} {self.get_stamp_type_display()} {self.stamped_at}'
