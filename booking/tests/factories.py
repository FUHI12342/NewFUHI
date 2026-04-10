"""
factory_boy ファクトリー定義 — booking アプリ全モデル対応

使用方法:
    from booking.tests.factories import StoreFactory, StaffFactory, ShiftPeriodFactory
    store = StoreFactory()
    staff = StaffFactory(store=store)
"""
import datetime
import uuid
from decimal import Decimal

import factory
from django.contrib.auth.models import User
from factory.django import DjangoModelFactory

from booking.models import (
    Store,
    Staff,
    Category,
    Product,
    ProductTranslation,
    SystemConfig,
    TableSeat,
    TaxServiceCharge,
    PaymentMethod,
    Schedule,
    StoreScheduleConfig,
    ShiftPeriod,
    ShiftRequest,
    ShiftAssignment,
    ShiftTemplate,
    ShiftPublishHistory,
    ShiftChangeLog,
    StoreClosedDate,
    ShiftStaffRequirement,
    ShiftStaffRequirementOverride,
    ShiftVacancy,
    ShiftSwapRequest,
    EmploymentContract,
    WorkAttendance,
    PayrollPeriod,
    PayrollEntry,
    PayrollDeduction,
    SalaryStructure,
    EvaluationCriteria,
    StaffEvaluation,
    AttendanceTOTPConfig,
    AttendanceStamp,
    Timer,
)


class UserFactory(DjangoModelFactory):
    """Djangoユーザーファクトリー"""

    class Meta:
        model = User
        django_get_or_create = ('username',)

    username = factory.Sequence(lambda n: f'user_{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_staff = True
    is_active = True


class StoreFactory(DjangoModelFactory):
    """店舗ファクトリー"""

    class Meta:
        model = Store

    name = factory.Sequence(lambda n: f'テスト店舗{n}')
    address = '東京都渋谷区1-1-1'
    business_hours = '10:00-21:00'
    nearest_station = '渋谷駅'
    timezone = 'Asia/Tokyo'
    default_language = 'ja'


class StaffFactory(DjangoModelFactory):
    """スタッフファクトリー"""

    class Meta:
        model = Staff

    user = factory.SubFactory(UserFactory)
    store = factory.SubFactory(StoreFactory)
    name = factory.Sequence(lambda n: f'スタッフ{n}')
    staff_type = 'fortune_teller'
    is_recommended = False
    is_store_manager = False
    is_owner = False
    is_developer = False
    price = 3000
    slot_duration = None
    notify_booking = True
    notify_shift = True
    notify_business = True


class ManagerStaffFactory(StaffFactory):
    """店長スタッフファクトリー"""

    is_store_manager = True
    staff_type = 'store_staff'


class StoreScheduleConfigFactory(DjangoModelFactory):
    """店舗スケジュール設定ファクトリー"""

    class Meta:
        model = StoreScheduleConfig

    store = factory.SubFactory(StoreFactory)
    open_hour = 9
    close_hour = 21
    slot_duration = 60
    min_shift_hours = 2


class CategoryFactory(DjangoModelFactory):
    """商品カテゴリファクトリー"""

    class Meta:
        model = Category

    store = factory.SubFactory(StoreFactory)
    name = factory.Sequence(lambda n: f'カテゴリ{n}')
    sort_order = factory.Sequence(lambda n: n)
    is_restaurant_menu = True


class ProductFactory(DjangoModelFactory):
    """商品ファクトリー"""

    class Meta:
        model = Product

    store = factory.SubFactory(StoreFactory)
    category = factory.SubFactory(CategoryFactory, store=factory.SelfAttribute('..store'))
    sku = factory.Sequence(lambda n: f'SKU-{n:04d}')
    name = factory.Sequence(lambda n: f'商品{n}')
    description = 'テスト商品の説明'
    price = 1000
    stock = 100
    low_stock_threshold = 10
    is_active = True
    is_ec_visible = False
    popularity = 0
    margin_rate = 0.3


class SystemConfigFactory(DjangoModelFactory):
    """システム設定ファクトリー"""

    class Meta:
        model = SystemConfig
        django_get_or_create = ('key',)

    key = factory.Sequence(lambda n: f'config_key_{n}')
    value = 'test_value'


class TableSeatFactory(DjangoModelFactory):
    """テーブル席ファクトリー"""

    class Meta:
        model = TableSeat

    store = factory.SubFactory(StoreFactory)
    label = factory.Sequence(lambda n: f'A{n}')
    is_active = True


class TaxServiceChargeFactory(DjangoModelFactory):
    """税・サービス料ファクトリー"""

    class Meta:
        model = TaxServiceCharge

    store = factory.SubFactory(StoreFactory)
    name = '消費税'
    rate = Decimal('10.00')
    is_active = True
    sort_order = 0


class PaymentMethodFactory(DjangoModelFactory):
    """決済方法ファクトリー"""

    class Meta:
        model = PaymentMethod

    store = factory.SubFactory(StoreFactory)
    method_type = 'cash'
    display_name = '現金'
    is_enabled = True
    sort_order = 0


class ScheduleFactory(DjangoModelFactory):
    """予約スケジュールファクトリー"""

    class Meta:
        model = Schedule

    staff = factory.SubFactory(StaffFactory)
    store = factory.LazyAttribute(lambda o: o.staff.store)
    start = factory.LazyFunction(
        lambda: datetime.datetime(2026, 4, 10, 10, 0, tzinfo=datetime.timezone.utc)
    )
    end = factory.LazyFunction(
        lambda: datetime.datetime(2026, 4, 10, 11, 0, tzinfo=datetime.timezone.utc)
    )
    customer_name = 'テスト顧客'
    price = 3000
    is_temporary = False
    is_cancelled = False
    memo = 'テスト備考'
    booking_channel = 'line'


class ShiftPeriodFactory(DjangoModelFactory):
    """シフト募集期間ファクトリー"""

    class Meta:
        model = ShiftPeriod

    store = factory.SubFactory(StoreFactory)
    year_month = datetime.date(2026, 4, 1)
    status = 'open'
    is_demo = False


class ShiftRequestFactory(DjangoModelFactory):
    """シフト希望ファクトリー"""

    class Meta:
        model = ShiftRequest

    period = factory.SubFactory(ShiftPeriodFactory)
    staff = factory.SubFactory(StaffFactory)
    date = datetime.date(2026, 4, 7)
    start_hour = 9
    end_hour = 17
    preference = 'available'
    note = ''


class ShiftAssignmentFactory(DjangoModelFactory):
    """確定シフトファクトリー"""

    class Meta:
        model = ShiftAssignment

    period = factory.SubFactory(ShiftPeriodFactory)
    staff = factory.SubFactory(StaffFactory)
    date = datetime.date(2026, 4, 7)
    start_hour = 9
    end_hour = 17
    start_time = datetime.time(9, 0)
    end_time = datetime.time(17, 0)
    color = '#3B82F6'
    note = ''
    is_synced = False
    is_demo = False


class ShiftTemplateFactory(DjangoModelFactory):
    """シフトテンプレートファクトリー"""

    class Meta:
        model = ShiftTemplate

    store = factory.SubFactory(StoreFactory)
    name = factory.Sequence(lambda n: f'シフトパターン{n}')
    start_time = datetime.time(9, 0)
    end_time = datetime.time(17, 0)
    color = '#3B82F6'
    is_active = True
    sort_order = 0


class ShiftStaffRequirementFactory(DjangoModelFactory):
    """必要人数ファクトリー"""

    class Meta:
        model = ShiftStaffRequirement

    store = factory.SubFactory(StoreFactory)
    day_of_week = 0
    staff_type = 'fortune_teller'
    required_count = 2


class ShiftVacancyFactory(DjangoModelFactory):
    """シフト不足枠ファクトリー"""

    class Meta:
        model = ShiftVacancy

    period = factory.SubFactory(ShiftPeriodFactory)
    store = factory.LazyAttribute(lambda o: o.period.store)
    date = datetime.date(2026, 4, 7)
    start_hour = 9
    end_hour = 17
    staff_type = 'fortune_teller'
    required_count = 2
    assigned_count = 1
    status = 'open'


class StoreClosedDateFactory(DjangoModelFactory):
    """休業日ファクトリー"""

    class Meta:
        model = StoreClosedDate

    store = factory.SubFactory(StoreFactory)
    date = datetime.date(2026, 4, 7)
    reason = 'テスト休業'


class EmploymentContractFactory(DjangoModelFactory):
    """雇用契約ファクトリー"""

    class Meta:
        model = EmploymentContract

    staff = factory.SubFactory(StaffFactory)
    employment_type = 'part_time'
    pay_type = 'hourly'
    hourly_rate = 1100
    monthly_salary = 0
    commute_allowance = 10000
    is_active = True


class WorkAttendanceFactory(DjangoModelFactory):
    """勤怠記録ファクトリー"""

    class Meta:
        model = WorkAttendance

    staff = factory.SubFactory(StaffFactory)
    date = factory.Sequence(lambda n: datetime.date(2026, 4, 1) + datetime.timedelta(days=n))
    clock_in = datetime.time(9, 0)
    clock_out = datetime.time(17, 0)
    regular_minutes = 480
    overtime_minutes = 0
    late_night_minutes = 0
    holiday_minutes = 0
    break_minutes = 60
    source = 'shift'


class PayrollPeriodFactory(DjangoModelFactory):
    """給与計算期間ファクトリー"""

    class Meta:
        model = PayrollPeriod

    store = factory.SubFactory(StoreFactory)
    year_month = '2026-04'
    period_start = datetime.date(2026, 4, 1)
    period_end = datetime.date(2026, 4, 30)
    status = 'draft'


class EvaluationCriteriaFactory(DjangoModelFactory):
    """評価基準ファクトリー"""

    class Meta:
        model = EvaluationCriteria

    store = factory.SubFactory(StoreFactory)
    name = factory.Sequence(lambda n: f'評価項目{n}')
    category = 'performance'
    weight = 1.0
    is_auto = False
    sort_order = 0
    is_active = True


class TimerFactory(DjangoModelFactory):
    """タイマーファクトリー"""

    class Meta:
        model = Timer

    user_id = factory.Sequence(lambda n: f'U{n:010d}')
    end_time = None


class SalaryStructureFactory(DjangoModelFactory):
    """給与体系ファクトリー"""

    class Meta:
        model = SalaryStructure

    store = factory.SubFactory(StoreFactory)
    pension_rate = Decimal('9.150')
    health_insurance_rate = Decimal('5.000')
    employment_insurance_rate = Decimal('0.600')
    long_term_care_rate = Decimal('0.820')
    workers_comp_rate = Decimal('0.300')
    overtime_multiplier = Decimal('1.25')
    late_night_multiplier = Decimal('1.35')
    holiday_multiplier = Decimal('1.50')


class AttendanceTOTPConfigFactory(DjangoModelFactory):
    """TOTP設定ファクトリー"""

    class Meta:
        model = AttendanceTOTPConfig

    store = factory.SubFactory(StoreFactory)
    totp_secret = factory.Sequence(lambda n: f'JBSWY3DPEHPK3PXP{n:04d}')
    totp_interval = 30
    geo_fence_radius_m = 200
    require_geo_check = False
    is_active = True


class ProductTranslationFactory(DjangoModelFactory):
    """商品翻訳ファクトリー"""

    class Meta:
        model = ProductTranslation

    product = factory.SubFactory(ProductFactory)
    lang = 'en'
    name = factory.Sequence(lambda n: f'Product {n}')
    description = 'Test product description'
