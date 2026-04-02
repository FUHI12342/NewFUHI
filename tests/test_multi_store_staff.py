"""
tests/test_multi_store_staff.py
Tests for multi-store staff support:
  - Staff with shift at store B appears in store B's list
  - Staff with shift at store B is excluded from primary store A's list
  - Staff with no shift today appears in primary store's list
  - Schedule.get_store() returns correct store
  - ShiftAssignment.get_store() returns correct store
"""
import pytest
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from booking.models import Store, Staff, Schedule, ShiftPeriod, ShiftAssignment

User = get_user_model()


@pytest.fixture
def store_a(db):
    return Store.objects.create(name="店舗A", address="東京都")


@pytest.fixture
def store_b(db):
    return Store.objects.create(name="店舗B", address="大阪府")


@pytest.fixture
def cast_user(db):
    return User.objects.create_user(username="cast1", password="pass123")


@pytest.fixture
def cast(db, store_a, cast_user):
    """Cast with primary store = A."""
    return Staff.objects.create(
        name="キャストA", store=store_a, user=cast_user,
        staff_type='fortune_teller',
    )


@pytest.fixture
def shift_period_a(db, store_a, cast):
    return ShiftPeriod.objects.create(
        store=store_a,
        year_month=date.today().replace(day=1),
        status='approved',
        created_by=cast,
    )


class TestShiftAssignmentGetStore:

    @pytest.mark.django_db
    def test_get_store_returns_explicit_store(self, shift_period_a, cast, store_b):
        assignment = ShiftAssignment.objects.create(
            period=shift_period_a, staff=cast, date=date.today(),
            start_hour=10, end_hour=18, store=store_b,
        )
        assert assignment.get_store() == store_b

    @pytest.mark.django_db
    def test_get_store_returns_primary_when_null(self, shift_period_a, cast, store_a):
        assignment = ShiftAssignment.objects.create(
            period=shift_period_a, staff=cast, date=date.today(),
            start_hour=10, end_hour=18,
        )
        assert assignment.get_store() == store_a


class TestScheduleGetStore:

    @pytest.mark.django_db
    def test_get_store_returns_explicit_store(self, cast, store_b):
        now = timezone.now()
        schedule = Schedule.objects.create(
            start=now + timedelta(hours=1),
            end=now + timedelta(hours=2),
            staff=cast, store=store_b, price=0,
        )
        assert schedule.get_store() == store_b

    @pytest.mark.django_db
    def test_get_store_returns_primary_when_null(self, cast, store_a):
        now = timezone.now()
        schedule = Schedule.objects.create(
            start=now + timedelta(hours=1),
            end=now + timedelta(hours=2),
            staff=cast, price=0,
        )
        assert schedule.get_store() == store_a


class TestStaffListMultiStore:

    @pytest.mark.django_db
    def test_shift_at_store_b_shows_in_store_b_list(
        self, client, cast, store_a, store_b, shift_period_a,
    ):
        """今日のシフトがB店舗に入っているキャストはB店舗の一覧に表示される"""
        ShiftAssignment.objects.create(
            period=shift_period_a, staff=cast, date=date.today(),
            start_hour=10, end_hour=18, store=store_b,
        )
        from django.test import RequestFactory
        from booking.views import StaffList
        factory = RequestFactory()
        request = factory.get(f'/store/{store_b.pk}/staff/')
        view = StaffList()
        view.kwargs = {'pk': store_b.pk}
        view.request = request
        qs = view.get_queryset()
        assert cast in qs

    @pytest.mark.django_db
    def test_shift_at_store_b_excludes_from_store_a_list(
        self, client, cast, store_a, store_b, shift_period_a,
    ):
        """今日のシフトがB店舗に入っているキャストはA店舗の一覧から除外される"""
        ShiftAssignment.objects.create(
            period=shift_period_a, staff=cast, date=date.today(),
            start_hour=10, end_hour=18, store=store_b,
        )
        from django.test import RequestFactory
        from booking.views import StaffList
        factory = RequestFactory()
        request = factory.get(f'/store/{store_a.pk}/staff/')
        view = StaffList()
        view.kwargs = {'pk': store_a.pk}
        view.request = request
        qs = view.get_queryset()
        assert cast not in qs

    @pytest.mark.django_db
    def test_no_shift_shows_in_primary_store(
        self, client, cast, store_a,
    ):
        """シフトなしの日は主店舗の一覧に表示される"""
        from django.test import RequestFactory
        from booking.views import StaffList
        factory = RequestFactory()
        request = factory.get(f'/store/{store_a.pk}/staff/')
        view = StaffList()
        view.kwargs = {'pk': store_a.pk}
        view.request = request
        qs = view.get_queryset()
        assert cast in qs
