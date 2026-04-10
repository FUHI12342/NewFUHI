"""
モデルの包括的テストスイート

対象モデル:
  - Timer, Store, Staff, Category, Product, ProductTranslation
  - SystemConfig, TableSeat, TaxServiceCharge, PaymentMethod
  - Schedule (cancel_token, LINE暗号化, get_store)
  - StoreScheduleConfig, ShiftPeriod, ShiftRequest, ShiftAssignment
  - ShiftTemplate, ShiftVacancy, ShiftSwapRequest, ShiftStaffRequirement
  - StoreClosedDate, EmploymentContract, WorkAttendance
  - PayrollPeriod, PayrollEntry, PayrollDeduction, SalaryStructure
  - EvaluationCriteria, StaffEvaluation, AttendanceTOTPConfig, AttendanceStamp

TDD原則:
  - 各テストは独立して実行可能
  - 外部依存（Fernet暗号化等）は設定依存のみ
  - エッジケース・境界値を網羅
"""
import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from booking.models import (
    Timer,
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
)
from booking.tests.factories import (
    UserFactory,
    StoreFactory,
    StaffFactory,
    ManagerStaffFactory,
    StoreScheduleConfigFactory,
    CategoryFactory,
    ProductFactory,
    ProductTranslationFactory,
    SystemConfigFactory,
    TableSeatFactory,
    TaxServiceChargeFactory,
    PaymentMethodFactory,
    ScheduleFactory,
    ShiftPeriodFactory,
    ShiftRequestFactory,
    ShiftAssignmentFactory,
    ShiftTemplateFactory,
    ShiftStaffRequirementFactory,
    ShiftVacancyFactory,
    StoreClosedDateFactory,
    EmploymentContractFactory,
    WorkAttendanceFactory,
    PayrollPeriodFactory,
    EvaluationCriteriaFactory,
    TimerFactory,
    SalaryStructureFactory,
)


# ===========================================================================
# Timer モデルのテスト
# ===========================================================================

class TestTimerModel(TestCase):
    """Timer モデルの基本テスト"""

    def test_str_representation(self):
        """__str__ が user_id と時刻の文字列を返す"""
        timer = TimerFactory(user_id='Uxxx123')
        result = str(timer)
        self.assertIn('Uxxx123', result)

    def test_end_time_nullable(self):
        """end_time は null を許容する"""
        timer = TimerFactory(end_time=None)
        self.assertIsNone(timer.end_time)

    def test_user_id_unique(self):
        """user_id はユニーク制約がある"""
        TimerFactory(user_id='unique_user')
        with self.assertRaises(Exception):
            TimerFactory(user_id='unique_user')

    def test_str_includes_arrow_separator(self):
        """__str__ に '->' が含まれる"""
        timer = TimerFactory(user_id='test_user')
        self.assertIn('->', str(timer))


# ===========================================================================
# Store モデルのテスト
# ===========================================================================

class TestStoreModel(TestCase):
    """Store モデルのテスト"""

    def test_str_returns_name(self):
        """__str__ が店舗名を返す"""
        store = StoreFactory(name='渋谷テスト店')
        self.assertEqual(str(store), '渋谷テスト店')

    def test_get_thumbnail_url_when_no_thumbnail(self):
        """サムネイルなしの場合はデフォルト画像URLを返す"""
        store = StoreFactory()
        url = store.get_thumbnail_url()
        self.assertIn('default_thumbnail.jpg', url)

    def test_default_timezone_is_asia_tokyo(self):
        """デフォルトタイムゾーンは Asia/Tokyo"""
        store = StoreFactory()
        self.assertEqual(store.timezone, 'Asia/Tokyo')

    def test_default_language_is_japanese(self):
        """デフォルト言語は日本語"""
        store = StoreFactory()
        self.assertEqual(store.default_language, 'ja')

    def test_store_creation_with_minimal_fields(self):
        """最小限のフィールドで店舗を作成できる"""
        store = Store.objects.create(name='ミニマム店舗')
        self.assertEqual(store.name, 'ミニマム店舗')
        self.assertIsNotNone(store.pk)

    def test_google_maps_embed_is_sanitized_on_save(self):
        """Google Maps埋め込みコードがsave時にサニタイズされる"""
        with patch('booking.services.html_sanitizer.sanitize_embed', return_value='<iframe></iframe>') as mock_sanitize:
            store = StoreFactory()
            store.google_maps_embed = '<script>alert("xss")</script><iframe></iframe>'
            store.save()
            mock_sanitize.assert_called_once()

    def test_empty_google_maps_embed_not_sanitized(self):
        """google_maps_embed が空の場合はサニタイズが呼ばれない"""
        with patch('booking.services.html_sanitizer.sanitize_embed') as mock_sanitize:
            store = StoreFactory()
            store.google_maps_embed = ''
            store.save()
            mock_sanitize.assert_not_called()

    def test_store_embed_allowed_domains_multiline(self):
        """埋め込み許可ドメインを複数行で保存できる"""
        store = StoreFactory(embed_allowed_domains='example.com\nexample2.com')
        self.assertIn('example.com', store.embed_allowed_domains)
        self.assertIn('example2.com', store.embed_allowed_domains)


# ===========================================================================
# Staff モデルのテスト
# ===========================================================================

class TestStaffModel(TestCase):
    """Staff モデルのテスト"""

    def test_str_includes_store_and_name(self):
        """__str__ に店舗名とスタッフ名が含まれる"""
        store = StoreFactory(name='銀座店')
        staff = StaffFactory(store=store, name='山田花子')
        self.assertEqual(str(staff), '銀座店 - 山田花子')

    def test_get_effective_slot_duration_uses_own_setting(self):
        """個別設定がある場合はそれを返す"""
        staff = StaffFactory(slot_duration=30)
        self.assertEqual(staff.get_effective_slot_duration(), 30)

    def test_get_effective_slot_duration_falls_back_to_store(self):
        """個別設定がない場合は店舗設定を返す"""
        store = StoreFactory()
        StoreScheduleConfigFactory(store=store, slot_duration=30)
        staff = StaffFactory(store=store, slot_duration=None)
        self.assertEqual(staff.get_effective_slot_duration(), 30)

    def test_get_effective_slot_duration_default_when_no_config(self):
        """店舗設定もない場合はデフォルト60分を返す"""
        store = StoreFactory()
        staff = StaffFactory(store=store, slot_duration=None)
        self.assertEqual(staff.get_effective_slot_duration(), 60)

    def test_set_and_check_attendance_pin_hashed(self):
        """PINをハッシュ化して保存し、照合できる"""
        staff = StaffFactory()
        staff.set_attendance_pin('1234')
        staff.save()
        self.assertTrue(staff.check_attendance_pin('1234'))

    def test_check_attendance_pin_wrong_pin_returns_false(self):
        """間違ったPINは False を返す"""
        staff = StaffFactory()
        staff.set_attendance_pin('1234')
        staff.save()
        self.assertFalse(staff.check_attendance_pin('9999'))

    def test_check_attendance_pin_empty_pin_returns_false(self):
        """PINが未設定の場合は False を返す"""
        staff = StaffFactory(attendance_pin='')
        self.assertFalse(staff.check_attendance_pin('1234'))

    def test_check_attendance_pin_legacy_plain_text(self):
        """旧データ（平文PIN6文字以下）との後方互換"""
        staff = StaffFactory()
        staff.attendance_pin = '1234'  # 平文（旧形式）
        staff.save()
        self.assertTrue(staff.check_attendance_pin('1234'))
        self.assertFalse(staff.check_attendance_pin('5678'))

    def test_staff_type_choices_are_valid(self):
        """有効なスタッフ種別で作成できる"""
        store = StoreFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        s1 = Staff.objects.create(user=user1, store=store, name='キャスト', staff_type='fortune_teller')
        s2 = Staff.objects.create(user=user2, store=store, name='スタッフ', staff_type='store_staff')
        self.assertEqual(s1.staff_type, 'fortune_teller')
        self.assertEqual(s2.staff_type, 'store_staff')

    def test_notify_flags_default_to_true(self):
        """通知フラグはデフォルトTrue"""
        staff = StaffFactory()
        self.assertTrue(staff.notify_booking)
        self.assertTrue(staff.notify_shift)
        self.assertTrue(staff.notify_business)

    def test_role_flags_default_to_false(self):
        """役職フラグはデフォルトFalse"""
        staff = StaffFactory()
        self.assertFalse(staff.is_store_manager)
        self.assertFalse(staff.is_owner)
        self.assertFalse(staff.is_developer)


# ===========================================================================
# Category モデルのテスト
# ===========================================================================

class TestCategoryModel(TestCase):
    """Category モデルのテスト"""

    def test_str_includes_store_and_category_name(self):
        """__str__ に店舗名とカテゴリ名が含まれる"""
        store = StoreFactory(name='新宿店')
        cat = CategoryFactory(store=store, name='フード')
        self.assertEqual(str(cat), '新宿店 / フード')

    def test_unique_together_store_and_name(self):
        """同一店舗内で重複カテゴリ名は作成不可"""
        store = StoreFactory()
        CategoryFactory(store=store, name='ドリンク')
        with self.assertRaises(Exception):
            CategoryFactory(store=store, name='ドリンク')

    def test_different_stores_can_have_same_category_name(self):
        """異なる店舗では同じカテゴリ名を持てる"""
        store1 = StoreFactory()
        store2 = StoreFactory()
        cat1 = CategoryFactory(store=store1, name='ドリンク')
        cat2 = CategoryFactory(store=store2, name='ドリンク')
        self.assertEqual(cat1.name, cat2.name)

    def test_ordering_by_sort_order(self):
        """sort_order 順で並んでいる"""
        store = StoreFactory()
        cat3 = CategoryFactory(store=store, name='C', sort_order=3)
        cat1 = CategoryFactory(store=store, name='A', sort_order=1)
        cat2 = CategoryFactory(store=store, name='B', sort_order=2)
        cats = list(Category.objects.filter(store=store))
        self.assertEqual(cats[0].sort_order, 1)
        self.assertEqual(cats[1].sort_order, 2)
        self.assertEqual(cats[2].sort_order, 3)


# ===========================================================================
# Product モデルのテスト
# ===========================================================================

class TestProductModel(TestCase):
    """Product モデルのテスト"""

    def test_str_includes_store_sku_name(self):
        """__str__ に店舗名・SKU・商品名が含まれる"""
        store = StoreFactory(name='池袋店')
        product = ProductFactory(store=store, sku='SKU-001', name='コーヒー')
        self.assertIn('池袋店', str(product))
        self.assertIn('SKU-001', str(product))
        self.assertIn('コーヒー', str(product))

    def test_is_sold_out_when_stock_is_zero(self):
        """在庫0の場合は is_sold_out が True"""
        product = ProductFactory(stock=0)
        self.assertTrue(product.is_sold_out)

    def test_is_sold_out_when_stock_is_negative(self):
        """在庫がマイナスの場合も is_sold_out が True"""
        product = ProductFactory(stock=-1)
        self.assertTrue(product.is_sold_out)

    def test_is_not_sold_out_when_stock_positive(self):
        """在庫が1以上の場合は is_sold_out が False"""
        product = ProductFactory(stock=1)
        self.assertFalse(product.is_sold_out)

    def test_should_notify_low_stock_when_threshold_exceeded(self):
        """閾値以下かつ未通知の場合は True"""
        product = ProductFactory(stock=5, low_stock_threshold=10, last_low_stock_notified_at=None)
        self.assertTrue(product.should_notify_low_stock())

    def test_should_not_notify_low_stock_when_already_notified(self):
        """既に通知済みの場合は False"""
        product = ProductFactory(
            stock=5,
            low_stock_threshold=10,
            last_low_stock_notified_at=timezone.now()
        )
        self.assertFalse(product.should_notify_low_stock())

    def test_should_not_notify_low_stock_when_above_threshold(self):
        """閾値超えの場合は False"""
        product = ProductFactory(stock=15, low_stock_threshold=10, last_low_stock_notified_at=None)
        self.assertFalse(product.should_notify_low_stock())

    def test_mark_low_stock_notified_sets_timestamp(self):
        """mark_low_stock_notified が現在時刻を設定する"""
        product = ProductFactory(last_low_stock_notified_at=None)
        product.mark_low_stock_notified()
        self.assertIsNotNone(product.last_low_stock_notified_at)

    def test_unique_together_store_and_sku(self):
        """同一店舗でSKUの重複は許可されない"""
        store = StoreFactory()
        ProductFactory(store=store, sku='DUP-001')
        with self.assertRaises(Exception):
            ProductFactory(store=store, sku='DUP-001')

    def test_stock_boundary_at_zero(self):
        """stock=0 は is_sold_out が True、stock=1 は False"""
        p0 = ProductFactory(stock=0)
        p1 = ProductFactory(stock=1)
        self.assertTrue(p0.is_sold_out)
        self.assertFalse(p1.is_sold_out)

    def test_low_stock_threshold_at_boundary(self):
        """stock == low_stock_threshold でも通知対象"""
        product = ProductFactory(stock=10, low_stock_threshold=10, last_low_stock_notified_at=None)
        self.assertTrue(product.should_notify_low_stock())


# ===========================================================================
# ProductTranslation モデルのテスト
# ===========================================================================

class TestProductTranslationModel(TestCase):
    """ProductTranslation モデルのテスト"""

    def test_str_includes_sku_and_lang(self):
        """__str__ にSKUと言語コードが含まれる"""
        product = ProductFactory(sku='TL-001')
        trans = ProductTranslationFactory(product=product, lang='en')
        self.assertIn('TL-001', str(trans))
        self.assertIn('en', str(trans))

    def test_unique_together_product_and_lang(self):
        """同一商品・同一言語の翻訳は重複不可"""
        product = ProductFactory()
        ProductTranslationFactory(product=product, lang='en')
        with self.assertRaises(Exception):
            ProductTranslationFactory(product=product, lang='en')

    def test_multiple_languages_for_same_product(self):
        """同一商品に複数言語の翻訳を登録できる"""
        product = ProductFactory()
        t_en = ProductTranslationFactory(product=product, lang='en')
        t_zh = ProductTranslationFactory(product=product, lang='zh-hant')
        self.assertEqual(t_en.lang, 'en')
        self.assertEqual(t_zh.lang, 'zh-hant')


# ===========================================================================
# SystemConfig モデルのテスト
# ===========================================================================

class TestSystemConfigModel(TestCase):
    """SystemConfig モデルのテスト"""

    def test_str_representation(self):
        """__str__ が key = value 形式を返す"""
        config = SystemConfigFactory(key='log_level', value='DEBUG')
        self.assertEqual(str(config), 'log_level = DEBUG')

    def test_get_returns_value_for_existing_key(self):
        """get() が既存キーの値を返す"""
        SystemConfig.objects.create(key='app_mode', value='production')
        result = SystemConfig.get('app_mode')
        self.assertEqual(result, 'production')

    def test_get_returns_default_for_missing_key(self):
        """get() が存在しないキーに対してデフォルト値を返す"""
        result = SystemConfig.get('nonexistent_key', default='fallback')
        self.assertEqual(result, 'fallback')

    def test_get_returns_empty_string_by_default(self):
        """get() のデフォルト値は空文字列"""
        result = SystemConfig.get('another_missing_key')
        self.assertEqual(result, '')

    def test_set_creates_new_entry(self):
        """set() が新しいエントリを作成する"""
        SystemConfig.set('new_key', 'new_value')
        obj = SystemConfig.objects.get(key='new_key')
        self.assertEqual(obj.value, 'new_value')

    def test_set_updates_existing_entry(self):
        """set() が既存エントリを更新する"""
        SystemConfig.set('update_key', 'initial')
        SystemConfig.set('update_key', 'updated')
        obj = SystemConfig.objects.get(key='update_key')
        self.assertEqual(obj.value, 'updated')

    def test_set_converts_value_to_string(self):
        """set() が数値を文字列に変換して保存する"""
        SystemConfig.set('numeric_key', 42)
        result = SystemConfig.get('numeric_key')
        self.assertEqual(result, '42')

    def test_key_uniqueness(self):
        """key はユニーク制約がある"""
        SystemConfig.objects.create(key='unique_config')
        with self.assertRaises(Exception):
            SystemConfig.objects.create(key='unique_config')


# ===========================================================================
# TableSeat モデルのテスト
# ===========================================================================

class TestTableSeatModel(TestCase):
    """TableSeat モデルのテスト"""

    def test_str_includes_store_and_label(self):
        """__str__ に店舗名とラベルが含まれる"""
        store = StoreFactory(name='原宿店')
        seat = TableSeatFactory(store=store, label='A1')
        self.assertEqual(str(seat), '原宿店 / A1')

    def test_get_menu_url_includes_id(self):
        """get_menu_url() がUUIDを含むURLを返す"""
        seat = TableSeatFactory()
        url = seat.get_menu_url()
        self.assertIn(str(seat.id), url)
        self.assertIn('/t/', url)

    def test_primary_key_is_uuid(self):
        """primary key が UUID 型"""
        seat = TableSeatFactory()
        import uuid
        self.assertIsInstance(seat.id, uuid.UUID)

    def test_unique_together_store_and_label(self):
        """同一店舗内でラベルの重複は不可"""
        store = StoreFactory()
        TableSeatFactory(store=store, label='B2')
        with self.assertRaises(Exception):
            TableSeatFactory(store=store, label='B2')

    def test_is_active_default_true(self):
        """is_active はデフォルト True"""
        seat = TableSeatFactory()
        self.assertTrue(seat.is_active)


# ===========================================================================
# TaxServiceCharge モデルのテスト
# ===========================================================================

class TestTaxServiceChargeModel(TestCase):
    """TaxServiceCharge モデルのテスト"""

    def test_str_without_hour(self):
        """applies_after_hour なしの __str__"""
        store = StoreFactory(name='銀座店')
        charge = TaxServiceChargeFactory(store=store, name='消費税', rate=Decimal('10.00'))
        result = str(charge)
        self.assertIn('銀座店', result)
        self.assertIn('消費税', result)
        self.assertIn('10.00%', result)
        self.assertNotIn('時以降', result)

    def test_str_with_hour(self):
        """applies_after_hour ありの __str__ に '時以降' が含まれる"""
        charge = TaxServiceChargeFactory(applies_after_hour=22)
        result = str(charge)
        self.assertIn('22時以降', result)

    def test_rate_is_decimal(self):
        """rate は Decimal 型"""
        charge = TaxServiceChargeFactory(rate=Decimal('8.50'))
        self.assertEqual(charge.rate, Decimal('8.50'))


# ===========================================================================
# PaymentMethod モデルのテスト
# ===========================================================================

class TestPaymentMethodModel(TestCase):
    """PaymentMethod モデルのテスト"""

    def test_str_includes_store_and_display_name(self):
        """__str__ に店舗名と表示名が含まれる"""
        store = StoreFactory(name='六本木店')
        method = PaymentMethodFactory(store=store, display_name='クレジットカード')
        self.assertEqual(str(method), '六本木店 / クレジットカード')

    def test_unique_together_store_and_method_type(self):
        """同一店舗で決済種別の重複は不可"""
        store = StoreFactory()
        PaymentMethodFactory(store=store, method_type='cash')
        with self.assertRaises(Exception):
            PaymentMethodFactory(store=store, method_type='cash')

    def test_different_stores_can_have_same_method_type(self):
        """異なる店舗は同じ決済種別を持てる"""
        store1 = StoreFactory()
        store2 = StoreFactory()
        m1 = PaymentMethodFactory(store=store1, method_type='cash')
        m2 = PaymentMethodFactory(store=store2, method_type='cash')
        self.assertEqual(m1.method_type, m2.method_type)

    def test_is_enabled_default_true(self):
        """is_enabled はデフォルト True"""
        method = PaymentMethodFactory()
        self.assertTrue(method.is_enabled)


# ===========================================================================
# Schedule モデルのテスト
# ===========================================================================

class TestScheduleModel(TestCase):
    """Schedule モデルのテスト"""

    def test_str_includes_reservation_number(self):
        """__str__ に予約番号が含まれる"""
        schedule = ScheduleFactory()
        result = str(schedule)
        self.assertIn(str(schedule.reservation_number), result)

    def test_cancel_token_auto_generated_on_save(self):
        """cancel_token が保存時に自動生成される"""
        schedule = ScheduleFactory()
        self.assertIsNotNone(schedule.cancel_token)
        self.assertEqual(len(schedule.cancel_token), 8)

    def test_cancel_token_is_unique(self):
        """cancel_token はユニーク"""
        s1 = ScheduleFactory()
        s2 = ScheduleFactory()
        self.assertNotEqual(s1.cancel_token, s2.cancel_token)

    def test_cancel_token_only_uppercase_alphanumeric(self):
        """cancel_token は英大文字と数字のみ"""
        import re
        schedule = ScheduleFactory()
        self.assertRegex(schedule.cancel_token, r'^[A-Z0-9]{8}$')

    def test_has_line_user_false_when_empty(self):
        """line_user_enc が空なら has_line_user は False"""
        schedule = ScheduleFactory()
        schedule.line_user_enc = None
        self.assertFalse(schedule.has_line_user)

    def test_get_store_returns_staff_store_when_not_set(self):
        """store が未設定の場合はスタッフの店舗を返す"""
        store = StoreFactory()
        staff = StaffFactory(store=store)
        schedule = ScheduleFactory(staff=staff, store=None)
        self.assertEqual(schedule.get_store(), store)

    def test_get_store_returns_own_store_when_set(self):
        """store が設定されている場合はそれを返す"""
        store1 = StoreFactory()
        store2 = StoreFactory()
        staff = StaffFactory(store=store1)
        schedule = ScheduleFactory(staff=staff, store=store2)
        self.assertEqual(schedule.get_store(), store2)

    def test_make_line_user_hash_is_deterministic(self):
        """同じ入力から同じハッシュが生成される"""
        h1 = Schedule.make_line_user_hash('Utest123')
        h2 = Schedule.make_line_user_hash('Utest123')
        self.assertEqual(h1, h2)

    def test_make_line_user_hash_is_hex_string(self):
        """ハッシュは 64文字の16進数文字列"""
        h = Schedule.make_line_user_hash('Utest456')
        self.assertEqual(len(h), 64)
        int(h, 16)  # 16進数として変換できる

    def test_make_line_user_hash_differs_for_different_inputs(self):
        """異なる入力からは異なるハッシュが生成される"""
        h1 = Schedule.make_line_user_hash('UserA')
        h2 = Schedule.make_line_user_hash('UserB')
        self.assertNotEqual(h1, h2)

    def test_confirmation_status_defaults_to_none(self):
        """確認ステータスのデフォルトは 'none'"""
        schedule = ScheduleFactory()
        self.assertEqual(schedule.confirmation_status, 'none')

    def test_is_checked_in_defaults_to_false(self):
        """is_checked_in のデフォルトは False"""
        schedule = ScheduleFactory()
        self.assertFalse(schedule.is_checked_in)

    def test_get_line_user_id_returns_none_when_no_enc(self):
        """暗号文がない場合は None を返す"""
        schedule = ScheduleFactory()
        schedule.line_user_enc = None
        self.assertIsNone(schedule.get_line_user_id())


# ===========================================================================
# StoreScheduleConfig モデルのテスト
# ===========================================================================

class TestStoreScheduleConfigModel(TestCase):
    """StoreScheduleConfig モデルのテスト"""

    def test_str_includes_store_and_hours(self):
        """__str__ に店舗名と営業時間が含まれる"""
        store = StoreFactory(name='テスト店')
        config = StoreScheduleConfigFactory(store=store, open_hour=10, close_hour=22)
        result = str(config)
        self.assertIn('テスト店', result)
        self.assertIn('10:00', result)
        self.assertIn('22:00', result)

    def test_default_slot_duration_is_60(self):
        """デフォルトスロット時間は60分"""
        store = StoreFactory()
        config = StoreScheduleConfig.objects.create(store=store)
        self.assertEqual(config.slot_duration, 60)

    def test_min_shift_hours_validator(self):
        """min_shift_hours は1以上12以下"""
        store = StoreFactory()
        config = StoreScheduleConfigFactory(store=store, min_shift_hours=2)
        config.full_clean()  # バリデーション通過
        self.assertEqual(config.min_shift_hours, 2)

    def test_one_to_one_with_store(self):
        """店舗との1対1関係"""
        store = StoreFactory()
        config = StoreScheduleConfigFactory(store=store)
        self.assertEqual(config.store, store)


# ===========================================================================
# ShiftPeriod モデルのテスト
# ===========================================================================

class TestShiftPeriodModel(TestCase):
    """ShiftPeriod モデルのテスト"""

    def test_str_includes_store_year_month_status(self):
        """__str__ に店舗名・年月・ステータスが含まれる"""
        store = StoreFactory(name='上野店')
        period = ShiftPeriodFactory(
            store=store,
            year_month=datetime.date(2026, 4, 1),
            status='open',
        )
        result = str(period)
        self.assertIn('上野店', result)
        self.assertIn('2026', result)
        self.assertIn('4月', result)

    def test_default_status_is_open(self):
        """デフォルトステータスは 'open'"""
        period = ShiftPeriodFactory()
        self.assertEqual(period.status, 'open')

    def test_status_choices_are_valid(self):
        """有効なステータス値で作成できる"""
        store = StoreFactory()
        for status in ['open', 'closed', 'scheduled', 'approved']:
            period = ShiftPeriodFactory(store=store, status=status)
            self.assertEqual(period.status, status)

    def test_is_demo_default_false(self):
        """is_demo はデフォルト False"""
        period = ShiftPeriodFactory()
        self.assertFalse(period.is_demo)


# ===========================================================================
# ShiftRequest モデルのテスト
# ===========================================================================

class TestShiftRequestModel(TestCase):
    """ShiftRequest モデルのテスト"""

    def test_str_includes_staff_date_hours_preference(self):
        """__str__ にスタッフ名・日付・時間・希望区分が含まれる"""
        staff = StaffFactory(name='鈴木次郎')
        period = ShiftPeriodFactory(store=staff.store)
        req = ShiftRequestFactory(
            staff=staff,
            period=period,
            date=datetime.date(2026, 4, 7),
            start_hour=9,
            end_hour=17,
            preference='available',
        )
        result = str(req)
        self.assertIn('鈴木次郎', result)
        self.assertIn('2026-04-07', result)
        self.assertIn('9:00', result)
        self.assertIn('17:00', result)

    def test_unique_together_period_staff_date_start_hour(self):
        """同一期間・スタッフ・日付・開始時間の組み合わせは重複不可"""
        period = ShiftPeriodFactory()
        staff = StaffFactory(store=period.store)
        ShiftRequestFactory(period=period, staff=staff, date=datetime.date(2026, 4, 7), start_hour=9)
        with self.assertRaises(Exception):
            ShiftRequestFactory(period=period, staff=staff, date=datetime.date(2026, 4, 7), start_hour=9)

    def test_preference_choices(self):
        """有効な希望区分で作成できる"""
        period = ShiftPeriodFactory()
        staff = StaffFactory(store=period.store)
        for i, pref in enumerate(['available', 'preferred', 'unavailable']):
            req = ShiftRequestFactory(
                period=period,
                staff=staff,
                date=datetime.date(2026, 4, 7 + i),
                preference=pref,
            )
            self.assertEqual(req.preference, pref)

    def test_default_preference_is_available(self):
        """デフォルトの希望区分は 'available'"""
        req = ShiftRequestFactory()
        self.assertEqual(req.preference, 'available')


# ===========================================================================
# ShiftAssignment モデルのテスト
# ===========================================================================

class TestShiftAssignmentModel(TestCase):
    """ShiftAssignment モデルのテスト"""

    def test_str_includes_staff_date_hours(self):
        """__str__ にスタッフ名・日付・時間が含まれる"""
        staff = StaffFactory(name='田中太郎')
        period = ShiftPeriodFactory(store=staff.store)
        assignment = ShiftAssignmentFactory(
            staff=staff,
            period=period,
            date=datetime.date(2026, 4, 10),
            start_hour=10,
            end_hour=18,
        )
        result = str(assignment)
        self.assertIn('田中太郎', result)
        self.assertIn('2026-04-10', result)
        self.assertIn('10:00', result)
        self.assertIn('18:00', result)

    def test_get_store_returns_assigned_store(self):
        """store が設定されている場合はそれを返す"""
        store1 = StoreFactory()
        store2 = StoreFactory()
        staff = StaffFactory(store=store1)
        period = ShiftPeriodFactory(store=store1)
        assignment = ShiftAssignmentFactory(staff=staff, period=period, store=store2)
        self.assertEqual(assignment.get_store(), store2)

    def test_get_store_falls_back_to_staff_store(self):
        """store が未設定の場合はスタッフの店舗を返す"""
        store = StoreFactory()
        staff = StaffFactory(store=store)
        period = ShiftPeriodFactory(store=store)
        assignment = ShiftAssignmentFactory(staff=staff, period=period, store=None)
        self.assertEqual(assignment.get_store(), store)

    def test_is_synced_default_false(self):
        """is_synced はデフォルト False"""
        assignment = ShiftAssignmentFactory()
        self.assertFalse(assignment.is_synced)

    def test_default_color_is_blue(self):
        """デフォルト表示色は青"""
        assignment = ShiftAssignmentFactory()
        self.assertEqual(assignment.color, '#3B82F6')


# ===========================================================================
# ShiftTemplate モデルのテスト
# ===========================================================================

class TestShiftTemplateModel(TestCase):
    """ShiftTemplate モデルのテスト"""

    def test_str_includes_store_name_and_times(self):
        """__str__ に店舗名・テンプレート名・時刻が含まれる"""
        store = StoreFactory(name='渋谷店')
        template = ShiftTemplateFactory(
            store=store,
            name='早番',
            start_time=datetime.time(8, 0),
            end_time=datetime.time(16, 0),
        )
        result = str(template)
        self.assertIn('渋谷店', result)
        self.assertIn('早番', result)
        self.assertIn('08:00:00', result)
        self.assertIn('16:00:00', result)

    def test_is_active_default_true(self):
        """is_active はデフォルト True"""
        template = ShiftTemplateFactory()
        self.assertTrue(template.is_active)

    def test_ordering_by_sort_order(self):
        """sort_order 順でソートされる"""
        store = StoreFactory()
        t3 = ShiftTemplateFactory(store=store, name='C', sort_order=3)
        t1 = ShiftTemplateFactory(store=store, name='A', sort_order=1)
        t2 = ShiftTemplateFactory(store=store, name='B', sort_order=2)
        templates = list(ShiftTemplate.objects.filter(store=store))
        self.assertEqual(templates[0].sort_order, 1)


# ===========================================================================
# ShiftVacancy モデルのテスト
# ===========================================================================

class TestShiftVacancyModel(TestCase):
    """ShiftVacancy モデルのテスト"""

    def test_str_includes_key_info(self):
        """__str__ に店舗名・日付・時間・人数が含まれる"""
        store = StoreFactory(name='新橋店')
        period = ShiftPeriodFactory(store=store)
        vacancy = ShiftVacancyFactory(
            store=store,
            period=period,
            date=datetime.date(2026, 4, 7),
            start_hour=9,
            end_hour=17,
            required_count=3,
            assigned_count=1,
        )
        result = str(vacancy)
        self.assertIn('新橋店', result)
        self.assertIn('2026-04-07', result)

    def test_shortage_property_calculates_correctly(self):
        """shortage プロパティが正しく計算される"""
        vacancy = ShiftVacancyFactory(required_count=3, assigned_count=1)
        self.assertEqual(vacancy.shortage, 2)

    def test_shortage_property_is_zero_when_fully_covered(self):
        """assigned >= required の場合 shortage は 0"""
        vacancy = ShiftVacancyFactory(required_count=2, assigned_count=3)
        self.assertEqual(vacancy.shortage, 0)

    def test_shortage_property_never_negative(self):
        """shortage は負にならない（max(0, ...)）"""
        vacancy = ShiftVacancyFactory(required_count=1, assigned_count=5)
        self.assertGreaterEqual(vacancy.shortage, 0)

    def test_status_choices_are_valid(self):
        """有効なステータス値で作成できる"""
        period = ShiftPeriodFactory()
        for i, status in enumerate(['open', 'filled', 'cancelled']):
            vacancy = ShiftVacancyFactory(period=period, status=status, start_hour=9 + i)
            self.assertEqual(vacancy.status, status)

    def test_default_status_is_open(self):
        """デフォルトステータスは 'open'"""
        vacancy = ShiftVacancyFactory()
        self.assertEqual(vacancy.status, 'open')


# ===========================================================================
# StoreClosedDate モデルのテスト
# ===========================================================================

class TestStoreClosedDateModel(TestCase):
    """StoreClosedDate モデルのテスト"""

    def test_str_includes_store_date_reason(self):
        """__str__ に店舗名・日付・理由が含まれる"""
        store = StoreFactory(name='秋葉原店')
        closed = StoreClosedDateFactory(
            store=store,
            date=datetime.date(2026, 1, 1),
            reason='元旦',
        )
        result = str(closed)
        self.assertIn('秋葉原店', result)
        self.assertIn('2026-01-01', result)
        self.assertIn('元旦', result)

    def test_unique_together_store_and_date(self):
        """同一店舗・日付の重複は不可"""
        store = StoreFactory()
        StoreClosedDateFactory(store=store, date=datetime.date(2026, 1, 1))
        with self.assertRaises(Exception):
            StoreClosedDateFactory(store=store, date=datetime.date(2026, 1, 1))


# ===========================================================================
# ShiftStaffRequirement モデルのテスト
# ===========================================================================

class TestShiftStaffRequirementModel(TestCase):
    """ShiftStaffRequirement モデルのテスト"""

    def test_str_includes_store_day_type_count(self):
        """__str__ に店舗名・曜日・スタッフ種別・人数が含まれる"""
        store = StoreFactory(name='浅草店')
        req = ShiftStaffRequirementFactory(
            store=store,
            day_of_week=0,  # 月曜
            staff_type='fortune_teller',
            required_count=3,
        )
        result = str(req)
        self.assertIn('浅草店', result)
        self.assertIn('×3', result)

    def test_unique_together_store_day_staff_type(self):
        """同一店舗・曜日・スタッフ種別の重複は不可"""
        store = StoreFactory()
        ShiftStaffRequirementFactory(store=store, day_of_week=0, staff_type='fortune_teller')
        with self.assertRaises(Exception):
            ShiftStaffRequirementFactory(store=store, day_of_week=0, staff_type='fortune_teller')

    def test_all_days_of_week_are_valid(self):
        """0-6 すべての曜日で作成できる"""
        store = StoreFactory()
        for dow in range(7):
            req = ShiftStaffRequirementFactory(
                store=store,
                day_of_week=dow,
                staff_type='fortune_teller',
            )
            self.assertEqual(req.day_of_week, dow)


# ===========================================================================
# ShiftSwapRequest モデルのテスト
# ===========================================================================

class TestShiftSwapRequestModel(TestCase):
    """ShiftSwapRequest モデルのテスト"""

    def setUp(self):
        self.store = StoreFactory()
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.staff1 = StaffFactory(user=self.user1, store=self.store)
        self.staff2 = StaffFactory(user=self.user2, store=self.store)
        self.period = ShiftPeriodFactory(store=self.store)
        self.assignment = ShiftAssignmentFactory(
            staff=self.staff1,
            period=self.period,
        )

    def test_str_includes_requester_type_date_status(self):
        """__str__ に申請者名・種別・日付・ステータスが含まれる"""
        swap = ShiftSwapRequest.objects.create(
            assignment=self.assignment,
            request_type='swap',
            requested_by=self.staff1,
            reason='テスト理由',
        )
        result = str(swap)
        self.assertIn(self.staff1.name, result)

    def test_default_status_is_pending(self):
        """デフォルトステータスは 'pending'"""
        swap = ShiftSwapRequest.objects.create(
            assignment=self.assignment,
            request_type='absence',
            requested_by=self.staff1,
            reason='体調不良',
        )
        self.assertEqual(swap.status, 'pending')

    def test_request_type_choices(self):
        """有効な申請種別で作成できる"""
        for i, req_type in enumerate(['swap', 'cover', 'absence']):
            assignment = ShiftAssignmentFactory(
                staff=self.staff1, period=self.period,
                date=datetime.date(2026, 4, 10 + i),
                start_hour=10 + i,
            )
            swap = ShiftSwapRequest.objects.create(
                assignment=assignment,
                request_type=req_type,
                requested_by=self.staff1,
                reason='テスト',
            )
            self.assertEqual(swap.request_type, req_type)


# ===========================================================================
# EmploymentContract モデルのテスト
# ===========================================================================

class TestEmploymentContractModel(TestCase):
    """EmploymentContract モデルのテスト"""

    def test_str_includes_staff_and_types(self):
        """__str__ にスタッフ名・雇用形態・給与形態が含まれる"""
        staff = StaffFactory(name='佐藤花子')
        contract = EmploymentContractFactory(
            staff=staff,
            employment_type='part_time',
            pay_type='hourly',
        )
        result = str(contract)
        self.assertIn('佐藤花子', result)

    def test_default_employment_type_is_part_time(self):
        """デフォルト雇用形態はパート・アルバイト"""
        staff = StaffFactory()
        contract = EmploymentContract.objects.create(staff=staff)
        self.assertEqual(contract.employment_type, 'part_time')

    def test_is_active_default_true(self):
        """is_active はデフォルト True"""
        contract = EmploymentContractFactory()
        self.assertTrue(contract.is_active)

    def test_one_to_one_with_staff(self):
        """スタッフとの1対1関係"""
        staff = StaffFactory()
        contract = EmploymentContractFactory(staff=staff)
        self.assertEqual(contract.staff, staff)


# ===========================================================================
# WorkAttendance モデルのテスト
# ===========================================================================

class TestWorkAttendanceModel(TestCase):
    """WorkAttendance モデルのテスト"""

    def test_str_includes_staff_date_source(self):
        """__str__ にスタッフ名・日付・ソースが含まれる"""
        staff = StaffFactory(name='伊藤健一')
        attendance = WorkAttendanceFactory(
            staff=staff,
            date=datetime.date(2026, 4, 7),
            source='shift',
        )
        result = str(attendance)
        self.assertIn('伊藤健一', result)
        self.assertIn('2026-04-07', result)

    def test_total_work_minutes_property(self):
        """total_work_minutes が全種別の合計を返す"""
        attendance = WorkAttendanceFactory(
            regular_minutes=480,
            overtime_minutes=60,
            late_night_minutes=30,
            holiday_minutes=0,
        )
        self.assertEqual(attendance.total_work_minutes, 570)

    def test_total_work_minutes_when_all_zero(self):
        """全分数が0の場合は0を返す"""
        attendance = WorkAttendanceFactory(
            regular_minutes=0,
            overtime_minutes=0,
            late_night_minutes=0,
            holiday_minutes=0,
        )
        self.assertEqual(attendance.total_work_minutes, 0)

    def test_unique_together_staff_and_date(self):
        """同一スタッフ・日付の重複は不可"""
        staff = StaffFactory()
        WorkAttendanceFactory(staff=staff, date=datetime.date(2026, 4, 7))
        with self.assertRaises(Exception):
            WorkAttendanceFactory(staff=staff, date=datetime.date(2026, 4, 7))

    def test_source_choices_are_valid(self):
        """有効なデータソースで作成できる"""
        staff = StaffFactory()
        for i, source in enumerate(['shift', 'manual', 'corrected', 'qr']):
            attendance = WorkAttendanceFactory(
                staff=staff,
                date=datetime.date(2026, 4, 7 + i),
                source=source,
            )
            self.assertEqual(attendance.source, source)


# ===========================================================================
# PayrollPeriod モデルのテスト
# ===========================================================================

class TestPayrollPeriodModel(TestCase):
    """PayrollPeriod モデルのテスト"""

    def test_str_includes_store_year_month_status(self):
        """__str__ に店舗名・年月・ステータスが含まれる"""
        store = StoreFactory(name='恵比寿店')
        period = PayrollPeriodFactory(
            store=store,
            year_month='2026-04',
            status='draft',
        )
        result = str(period)
        self.assertIn('恵比寿店', result)
        self.assertIn('2026-04', result)

    def test_default_status_is_draft(self):
        """デフォルトステータスは 'draft'"""
        period = PayrollPeriodFactory()
        self.assertEqual(period.status, 'draft')

    def test_unique_together_store_year_month(self):
        """同一店舗・年月の重複は不可"""
        store = StoreFactory()
        PayrollPeriodFactory(store=store, year_month='2026-04')
        with self.assertRaises(Exception):
            PayrollPeriodFactory(store=store, year_month='2026-04')


# ===========================================================================
# EvaluationCriteria モデルのテスト
# ===========================================================================

class TestEvaluationCriteriaModel(TestCase):
    """EvaluationCriteria モデルのテスト"""

    def test_str_includes_store_and_name(self):
        """__str__ に店舗名と評価項目名が含まれる"""
        store = StoreFactory(name='品川店')
        criteria = EvaluationCriteriaFactory(store=store, name='遅刻率')
        result = str(criteria)
        self.assertIn('品川店', result)
        self.assertIn('遅刻率', result)

    def test_unique_together_store_and_name(self):
        """同一店舗・評価項目名の重複は不可"""
        store = StoreFactory()
        EvaluationCriteriaFactory(store=store, name='出勤率')
        with self.assertRaises(Exception):
            EvaluationCriteriaFactory(store=store, name='出勤率')

    def test_is_active_default_true(self):
        """is_active はデフォルト True"""
        criteria = EvaluationCriteriaFactory()
        self.assertTrue(criteria.is_active)

    def test_category_choices_are_valid(self):
        """有効なカテゴリで作成できる"""
        store = StoreFactory()
        categories = ['attendance', 'performance', 'skill', 'attitude', 'customer']
        for i, cat in enumerate(categories):
            criteria = EvaluationCriteriaFactory(
                store=store,
                name=f'評価{i}',
                category=cat,
            )
            self.assertEqual(criteria.category, cat)


# ===========================================================================
# StaffEvaluation モデルのテスト
# ===========================================================================

class TestStaffEvaluationModel(TestCase):
    """StaffEvaluation モデルのテスト"""

    def test_str_includes_staff_period_grade(self):
        """__str__ にスタッフ名・期間・評価ランクが含まれる"""
        staff = StaffFactory(name='木村さくら')
        evaluation = StaffEvaluation.objects.create(
            staff=staff,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 3, 31),
        )
        result = str(evaluation)
        self.assertIn('木村さくら', result)

    def test_calculate_grade_s_for_high_score(self):
        """overall_score >= 4.5 は 'S' ランク"""
        staff = StaffFactory()
        evaluation = StaffEvaluation.objects.create(
            staff=staff,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 3, 31),
            overall_score=4.8,
        )
        self.assertEqual(evaluation.calculate_grade(), 'S')

    def test_calculate_grade_a(self):
        """overall_score 3.5-4.5 は 'A' ランク"""
        staff = StaffFactory()
        evaluation = StaffEvaluation.objects.create(
            staff=staff,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 3, 31),
            overall_score=4.0,
        )
        self.assertEqual(evaluation.calculate_grade(), 'A')

    def test_calculate_grade_b(self):
        """overall_score 2.5-3.5 は 'B' ランク"""
        staff = StaffFactory()
        evaluation = StaffEvaluation.objects.create(
            staff=staff,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 3, 31),
            overall_score=3.0,
        )
        self.assertEqual(evaluation.calculate_grade(), 'B')

    def test_calculate_grade_c(self):
        """overall_score 1.5-2.5 は 'C' ランク"""
        staff = StaffFactory()
        evaluation = StaffEvaluation.objects.create(
            staff=staff,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 3, 31),
            overall_score=2.0,
        )
        self.assertEqual(evaluation.calculate_grade(), 'C')

    def test_calculate_grade_d_for_low_score(self):
        """overall_score < 1.5 は 'D' ランク"""
        staff = StaffFactory()
        evaluation = StaffEvaluation.objects.create(
            staff=staff,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 3, 31),
            overall_score=1.0,
        )
        self.assertEqual(evaluation.calculate_grade(), 'D')

    def test_calculate_grade_returns_empty_when_no_score(self):
        """overall_score が None の場合は空文字を返す"""
        staff = StaffFactory()
        evaluation = StaffEvaluation.objects.create(
            staff=staff,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 3, 31),
            overall_score=None,
        )
        self.assertEqual(evaluation.calculate_grade(), '')

    def test_calculate_grade_boundary_at_4_5(self):
        """境界値 4.5 は 'S' ランク"""
        staff = StaffFactory()
        evaluation = StaffEvaluation.objects.create(
            staff=staff,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 3, 31),
            overall_score=4.5,
        )
        self.assertEqual(evaluation.calculate_grade(), 'S')

    def test_calculate_grade_boundary_below_4_5(self):
        """4.5 未満は 'A' ランク（4.5 未満 3.5 以上）"""
        staff = StaffFactory()
        evaluation = StaffEvaluation.objects.create(
            staff=staff,
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 3, 31),
            overall_score=4.4,
        )
        self.assertEqual(evaluation.calculate_grade(), 'A')


# ===========================================================================
# AttendanceTOTPConfig モデルのテスト
# ===========================================================================

class TestAttendanceTOTPConfigModel(TestCase):
    """AttendanceTOTPConfig モデルのテスト"""

    def test_str_includes_store_name(self):
        """__str__ に店舗名が含まれる"""
        store = StoreFactory(name='上野店')
        config = AttendanceTOTPConfig.objects.create(
            store=store,
            totp_secret='JBSWY3DPEHPK3PXP',
        )
        result = str(config)
        self.assertIn('上野店', result)

    def test_default_totp_interval_is_30(self):
        """デフォルトTOTP間隔は30秒"""
        store = StoreFactory()
        config = AttendanceTOTPConfig.objects.create(
            store=store,
            totp_secret='JBSWY3DPEHPK3PXP',
        )
        self.assertEqual(config.totp_interval, 30)

    def test_one_to_one_with_store(self):
        """店舗との1対1関係"""
        store = StoreFactory()
        config = AttendanceTOTPConfig.objects.create(
            store=store,
            totp_secret='JBSWY3DPEHPK3PXP',
        )
        self.assertEqual(config.store, store)


# ===========================================================================
# SalaryStructure モデルのテスト
# ===========================================================================

class TestSalaryStructureModel(TestCase):
    """SalaryStructure モデルのテスト"""

    def test_str_includes_store_name(self):
        """__str__ に店舗名が含まれる"""
        store = StoreFactory(name='秋葉原店')
        structure = SalaryStructureFactory(store=store)
        result = str(structure)
        self.assertIn('秋葉原店', result)
        self.assertIn('給与体系', result)

    def test_default_overtime_multiplier(self):
        """残業割増率のデフォルトは 1.25"""
        structure = SalaryStructureFactory()
        self.assertEqual(structure.overtime_multiplier, Decimal('1.25'))

    def test_default_late_night_multiplier(self):
        """深夜割増率のデフォルトは 1.35"""
        structure = SalaryStructureFactory()
        self.assertEqual(structure.late_night_multiplier, Decimal('1.35'))

    def test_default_holiday_multiplier(self):
        """休日割増率のデフォルトは 1.50"""
        structure = SalaryStructureFactory()
        self.assertEqual(structure.holiday_multiplier, Decimal('1.50'))

    def test_one_to_one_with_store(self):
        """店舗との1対1関係"""
        store = StoreFactory()
        structure = SalaryStructureFactory(store=store)
        self.assertEqual(structure.store, store)


# ===========================================================================
# ShiftPublishHistory モデルのテスト
# ===========================================================================

class TestShiftPublishHistoryModel(TestCase):
    """ShiftPublishHistory モデルのテスト"""

    def test_str_includes_period_action_and_datetime(self):
        """__str__ に期間・操作・日時が含まれる"""
        period = ShiftPeriodFactory()
        history = ShiftPublishHistory.objects.create(
            period=period,
            assignment_count=5,
            action='publish',
        )
        result = str(history)
        # action may be displayed as Japanese label (公開) or English (publish)
        self.assertTrue('publish' in result or '公開' in result, f'Expected publish/公開 in: {result}')

    def test_default_action_is_publish(self):
        """デフォルト操作は 'publish'"""
        period = ShiftPeriodFactory()
        history = ShiftPublishHistory.objects.create(
            period=period,
            assignment_count=0,
        )
        self.assertEqual(history.action, 'publish')

    def test_action_choices_are_valid(self):
        """有効な操作値で作成できる"""
        period = ShiftPeriodFactory()
        for action in ['publish', 'revoke', 'reopen']:
            history = ShiftPublishHistory.objects.create(
                period=period,
                assignment_count=0,
                action=action,
            )
            self.assertEqual(history.action, action)


# ===========================================================================
# AttendanceStamp モデルのテスト
# ===========================================================================

class TestAttendanceStampModel(TestCase):
    """AttendanceStamp モデルのテスト"""

    def test_str_includes_staff_type_datetime(self):
        """__str__ にスタッフ名・打刻種別・日時が含まれる"""
        staff = StaffFactory(name='高橋次郎')
        stamp = AttendanceStamp.objects.create(
            staff=staff,
            stamp_type='clock_in',
        )
        result = str(stamp)
        self.assertIn('高橋次郎', result)

    def test_default_is_valid_true(self):
        """is_valid はデフォルト True"""
        staff = StaffFactory()
        stamp = AttendanceStamp.objects.create(
            staff=staff,
            stamp_type='clock_in',
        )
        self.assertTrue(stamp.is_valid)

    def test_stamp_type_choices(self):
        """有効な打刻種別で作成できる"""
        staff = StaffFactory()
        for stamp_type in ['clock_in', 'clock_out', 'break_start', 'break_end']:
            stamp = AttendanceStamp.objects.create(
                staff=staff,
                stamp_type=stamp_type,
            )
            self.assertEqual(stamp.stamp_type, stamp_type)
