"""
pytest conftest.py - Test environment setup for FUHI Django project.

Provides common fixtures for Store, Staff, IoTDevice, and API client.
"""
import os
import pytest
import hashlib
from datetime import date, time, timedelta
from unittest.mock import patch, MagicMock
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings.local')

import django
django.setup()

# テスト環境でtestserverを必ず許可
from django.conf import settings as _settings
if 'testserver' not in _settings.ALLOWED_HOSTS:
    _settings.ALLOWED_HOSTS.append('testserver')

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from booking.models import (
    Store, Staff, IoTDevice,
    Category, Product, Order, OrderItem, StockMovement,
    StoreScheduleConfig, ShiftPeriod, ShiftRequest, ShiftAssignment,
    ShiftTemplate, ShiftPublishHistory,
    EmploymentContract, SalaryStructure, PayrollPeriod, WorkAttendance,
    Property, PropertyDevice, TableSeat,
    SiteSettings, SecurityAudit, SecurityLog, CostReport,
    AttendanceTOTPConfig, AttendanceStamp, POSTransaction,
    PaymentMethod, VisitorCount, VisitorAnalyticsConfig,
    StaffRecommendationModel, StaffRecommendationResult,
)

User = get_user_model()


# ==============================
# autouse: テスト用暗号化キー設定
# ==============================

@pytest.fixture(autouse=True)
def encryption_settings(settings):
    """Fernet鍵をテスト用に設定（autouse）"""
    from cryptography.fernet import Fernet
    test_key = Fernet.generate_key().decode('utf-8')
    settings.LINE_USER_ID_ENCRYPTION_KEY = test_key
    settings.LINE_USER_ID_HASH_PEPPER = 'test-pepper'
    settings.IOT_ENCRYPTION_KEY = test_key


# ==============================
# 基本フィクスチャ
# ==============================

@pytest.fixture
def store(db):
    """Create and return a test Store instance."""
    return Store.objects.create(
        name="テスト店舗",
        address="東京都新宿区",
        business_hours="9:00-17:00",
        nearest_station="新宿駅",
    )


@pytest.fixture
def staff(db, store):
    """Create and return a test Staff instance with an associated User."""
    user = User.objects.create_user(
        username="teststaff",
        password="testpass123",
        email="teststaff@example.com",
    )
    return Staff.objects.create(
        name="テストスタッフ",
        store=store,
        user=user,
    )


@pytest.fixture
def admin_user(db):
    """Create and return an admin (superuser) User."""
    return User.objects.create_superuser(
        username="admin",
        password="adminpass123",
        email="admin@example.com",
    )


@pytest.fixture
def staff_user(db, store):
    """Create and return a staff (is_staff=True) User with Staff profile."""
    user = User.objects.create_user(
        username="staffuser",
        password="staffpass123",
        email="staffuser@example.com",
        is_staff=True,
    )
    Staff.objects.create(name="スタッフユーザー", store=store, user=user)
    return user


@pytest.fixture
def authenticated_client(db, staff):
    """Return a Django test Client logged in as a regular staff user."""
    client = Client()
    client.login(username="teststaff", password="testpass123")
    return client


@pytest.fixture
def admin_client(db, admin_user, store):
    """Return a Django test Client logged in as admin."""
    Staff.objects.create(name="管理者", store=store, user=admin_user, is_developer=True)
    client = Client()
    client.login(username="admin", password="adminpass123")
    return client


@pytest.fixture
def iot_device(db, store):
    """Create and return a test IoTDevice with a known API key hash."""
    raw_api_key = "test-api-key-12345"
    api_key_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()
    return IoTDevice.objects.create(
        name="テストデバイス",
        store=store,
        device_type="multi",
        external_id="test-device-001",
        api_key_hash=api_key_hash,
        api_key_prefix=raw_api_key[:8],
    )


@pytest.fixture
def api_client():
    """Return a Django test Client instance."""
    return Client()


# ==============================
# 商品・注文フィクスチャ
# ==============================

@pytest.fixture
def category(db, store):
    """Create and return a test Category."""
    return Category.objects.create(
        store=store,
        name="テストカテゴリ",
        sort_order=0,
    )


@pytest.fixture
def product(db, store, category):
    """Create and return a test Product with stock."""
    return Product.objects.create(
        store=store,
        category=category,
        sku="TEST-001",
        name="テスト商品",
        price=500,
        stock=100,
        low_stock_threshold=10,
        is_active=True,
    )


@pytest.fixture
def order(db, store):
    """Create and return an OPEN Order."""
    return Order.objects.create(
        store=store,
        status=Order.STATUS_OPEN,
    )


@pytest.fixture
def order_item(db, order, product):
    """Create and return an OrderItem."""
    return OrderItem.objects.create(
        order=order,
        product=product,
        qty=2,
        unit_price=product.price,
        status=OrderItem.STATUS_ORDERED,
    )


# ==============================
# シフト管理フィクスチャ
# ==============================

@pytest.fixture
def store_schedule_config(db, store):
    """Create and return a StoreScheduleConfig."""
    return StoreScheduleConfig.objects.create(
        store=store,
        open_hour=9,
        close_hour=21,
        slot_duration=60,
    )


@pytest.fixture
def shift_period(db, store, staff):
    """Create and return a ShiftPeriod."""
    return ShiftPeriod.objects.create(
        store=store,
        year_month=date(2025, 4, 1),
        deadline=timezone.now() + timedelta(days=7),
        status='open',
        created_by=staff,
    )


@pytest.fixture
def shift_request(db, shift_period, staff):
    """Create and return a ShiftRequest."""
    return ShiftRequest.objects.create(
        period=shift_period,
        staff=staff,
        date=date(2025, 4, 10),
        start_hour=9,
        end_hour=17,
        preference='preferred',
    )


@pytest.fixture
def shift_assignment(db, shift_period, staff):
    """Create and return a ShiftAssignment."""
    return ShiftAssignment.objects.create(
        period=shift_period,
        staff=staff,
        date=date(2025, 4, 10),
        start_hour=9,
        end_hour=17,
    )


# ==============================
# 給与・勤怠フィクスチャ
# ==============================

@pytest.fixture
def employment_contract(db, staff):
    """Create and return an EmploymentContract."""
    return EmploymentContract.objects.create(
        staff=staff,
        employment_type='part_time',
        pay_type='hourly',
        hourly_rate=1200,
        commute_allowance=10000,
        housing_allowance=0,
        family_allowance=0,
        standard_monthly_remuneration=200000,
        resident_tax_monthly=5000,
        birth_date=date(1990, 5, 15),
        is_active=True,
    )


@pytest.fixture
def salary_structure(db, store):
    """Create and return a SalaryStructure."""
    return SalaryStructure.objects.create(
        store=store,
        pension_rate=Decimal('9.150'),
        health_insurance_rate=Decimal('5.000'),
        employment_insurance_rate=Decimal('0.600'),
        long_term_care_rate=Decimal('0.820'),
        workers_comp_rate=Decimal('0.300'),
        overtime_multiplier=Decimal('1.25'),
        late_night_multiplier=Decimal('1.35'),
        holiday_multiplier=Decimal('1.50'),
    )


@pytest.fixture
def payroll_period(db, store):
    """Create and return a PayrollPeriod."""
    return PayrollPeriod.objects.create(
        store=store,
        year_month='2025-04',
        period_start=date(2025, 4, 1),
        period_end=date(2025, 4, 30),
        status='draft',
        payment_date=date(2025, 5, 25),
    )


@pytest.fixture
def work_attendance(db, staff):
    """Create and return a WorkAttendance."""
    return WorkAttendance.objects.create(
        staff=staff,
        date=date(2025, 4, 10),
        clock_in=time(9, 0),
        clock_out=time(17, 0),
        regular_minutes=420,
        overtime_minutes=60,
        late_night_minutes=0,
        holiday_minutes=0,
        break_minutes=60,
        source='shift',
    )


# ==============================
# プロパティフィクスチャ
# ==============================

@pytest.fixture
def property_obj(db, store):
    """Create and return a Property."""
    return Property.objects.create(
        name="テスト物件",
        address="東京都渋谷区",
        property_type='apartment',
        store=store,
        is_active=True,
    )


@pytest.fixture
def property_device(db, property_obj, iot_device):
    """Create and return a PropertyDevice."""
    return PropertyDevice.objects.create(
        property=property_obj,
        device=iot_device,
        location_label="リビング",
    )


@pytest.fixture
def table_seat(db, store):
    """Create and return a TableSeat."""
    return TableSeat.objects.create(
        store=store,
        label="A1",
        is_active=True,
    )


@pytest.fixture
def site_settings(db):
    """Create and return SiteSettings (singleton)."""
    return SiteSettings.load()


# ==============================
# モック フィクスチャ
# ==============================

@pytest.fixture
def mock_line_notify():
    """Mock send_line_notify."""
    with patch('booking.line_notify.send_line_notify', return_value=True) as m:
        yield m


@pytest.fixture
def mock_linebot():
    """Mock LineBotApi."""
    with patch('booking.views.LineBotApi') as m:
        mock_api = MagicMock()
        m.return_value = mock_api
        yield mock_api


@pytest.fixture
def mock_gemini_api():
    """Mock Gemini API calls."""
    with patch('booking.services.ai_chat._call_gemini', return_value='テスト回答') as m:
        yield m


@pytest.fixture
def mock_boto3():
    """Mock boto3."""
    with patch('boto3.Session') as m:
        yield m


@pytest.fixture
def mail_outbox(settings):
    """Enable Django mail outbox for testing."""
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    from django.core import mail
    mail.outbox = []
    return mail.outbox


# ==============================
# Air統合フィクスチャ
# ==============================

@pytest.fixture
def shift_template(db, store):
    """Create and return a ShiftTemplate."""
    return ShiftTemplate.objects.create(
        store=store,
        name="早番",
        start_time=time(9, 0),
        end_time=time(14, 0),
        color='#10B981',
    )


@pytest.fixture
def totp_config(db, store):
    """Create and return an AttendanceTOTPConfig."""
    from booking.services.totp_service import generate_totp_secret
    return AttendanceTOTPConfig.objects.create(
        store=store,
        totp_secret=generate_totp_secret(),
        totp_interval=30,
        is_active=True,
    )


@pytest.fixture
def payment_method(db, store):
    """Create and return a PaymentMethod."""
    return PaymentMethod.objects.create(
        store=store,
        method_type='cash',
        display_name='現金',
        is_enabled=True,
    )


@pytest.fixture
def visitor_count(db, store):
    """Create and return a VisitorCount."""
    return VisitorCount.objects.create(
        store=store,
        date=date.today(),
        hour=12,
        pir_count=20,
        estimated_visitors=8,
        order_count=5,
    )


@pytest.fixture
def manager_client(db, store):
    """Return a Django test Client logged in as store manager."""
    user = User.objects.create_user(
        username="manager",
        password="managerpass123",
        email="manager@example.com",
        is_staff=True,
    )
    Staff.objects.create(name="店長", store=store, user=user, is_store_manager=True)
    client = Client()
    client.login(username="manager", password="managerpass123")
    return client
