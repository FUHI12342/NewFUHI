"""
Tests for payroll-related models:
EmploymentContract, WorkAttendance, PayrollPeriod, PayrollEntry, PayrollDeduction, SalaryStructure.
"""
import pytest
from datetime import date, time
from decimal import Decimal

from django.db import IntegrityError

from booking.models import (
    EmploymentContract,
    WorkAttendance,
    PayrollPeriod,
    PayrollEntry,
    PayrollDeduction,
    SalaryStructure,
    Staff,
    Store,
)


# ==============================
# EmploymentContract
# ==============================


@pytest.mark.django_db
class TestEmploymentContract:
    """EmploymentContract モデルテスト"""

    def test_str_format(self, employment_contract):
        """__str__ が 'スタッフ名 (雇用形態 / 給与形態)' 形式"""
        s = str(employment_contract)
        assert employment_contract.staff.name in s
        assert 'パート・アルバイト' in s
        assert '時給' in s

    def test_employment_type_choices(self, employment_contract):
        """employment_type が有効な選択肢の一つ"""
        valid_types = ['full_time', 'part_time', 'contract']
        assert employment_contract.employment_type in valid_types

    def test_pay_type_choices(self, employment_contract):
        """pay_type が有効な選択肢の一つ"""
        valid_types = ['hourly', 'monthly']
        assert employment_contract.pay_type in valid_types

    def test_one_to_one_with_staff(self, employment_contract, staff):
        """Staff との 1:1 関係が正しく設定されている"""
        assert staff.employment_contract == employment_contract

    def test_duplicate_staff_raises_error(self, employment_contract, staff):
        """同じ Staff に2つの EmploymentContract を作成するとエラー"""
        with pytest.raises(IntegrityError):
            EmploymentContract.objects.create(
                staff=staff,
                employment_type='full_time',
                pay_type='monthly',
                monthly_salary=300000,
            )


# ==============================
# WorkAttendance
# ==============================


@pytest.mark.django_db
class TestWorkAttendance:
    """WorkAttendance モデルテスト"""

    def test_total_work_minutes_property(self, work_attendance):
        """total_work_minutes が regular + overtime + late_night + holiday の合計"""
        expected = (
            work_attendance.regular_minutes
            + work_attendance.overtime_minutes
            + work_attendance.late_night_minutes
            + work_attendance.holiday_minutes
        )
        assert work_attendance.total_work_minutes == expected

    def test_total_work_minutes_value(self, work_attendance):
        """fixture の値: 420 + 60 + 0 + 0 = 480"""
        assert work_attendance.total_work_minutes == 480

    def test_unique_together_staff_date(self, work_attendance, staff):
        """同じスタッフ・同じ日付の重複はエラー"""
        with pytest.raises(IntegrityError):
            WorkAttendance.objects.create(
                staff=staff,
                date=work_attendance.date,
                clock_in=time(10, 0),
                clock_out=time(18, 0),
            )

    def test_str_format(self, work_attendance):
        """__str__ が 'スタッフ名 日付 (ソース表示)' 形式"""
        s = str(work_attendance)
        assert work_attendance.staff.name in s
        assert str(work_attendance.date) in s


# ==============================
# PayrollPeriod
# ==============================


@pytest.mark.django_db
class TestPayrollPeriod:
    """PayrollPeriod モデルテスト"""

    def test_unique_together_store_year_month(self, payroll_period, store):
        """同じ store + year_month の重複はエラー"""
        with pytest.raises(IntegrityError):
            PayrollPeriod.objects.create(
                store=store,
                year_month='2025-04',
                period_start=date(2025, 4, 1),
                period_end=date(2025, 4, 30),
            )

    def test_status_choices(self, payroll_period):
        """status が有効な選択肢の一つ"""
        valid = ['draft', 'calculating', 'confirmed', 'paid']
        assert payroll_period.status in valid

    def test_str_format(self, payroll_period):
        """__str__ が '店舗名 YYYY-MM (ステータス表示)' 形式"""
        s = str(payroll_period)
        assert payroll_period.store.name in s
        assert '2025-04' in s


# ==============================
# PayrollEntry
# ==============================


@pytest.mark.django_db
class TestPayrollEntry:
    """PayrollEntry モデルテスト"""

    def test_str_with_formatted_gross_pay(self, payroll_period, staff):
        """__str__ に gross_pay がカンマ区切りで含まれる"""
        entry = PayrollEntry.objects.create(
            period=payroll_period,
            staff=staff,
            gross_pay=250000,
            net_pay=200000,
        )
        s = str(entry)
        assert '250,000' in s
        assert staff.name in s

    def test_unique_together_period_staff(self, payroll_period, staff):
        """同じ period + staff の重複はエラー"""
        PayrollEntry.objects.create(
            period=payroll_period, staff=staff,
            gross_pay=100000, net_pay=80000,
        )
        with pytest.raises(IntegrityError):
            PayrollEntry.objects.create(
                period=payroll_period, staff=staff,
                gross_pay=200000, net_pay=160000,
            )


# ==============================
# PayrollDeduction
# ==============================


@pytest.mark.django_db
class TestPayrollDeduction:
    """PayrollDeduction モデルテスト"""

    @pytest.fixture
    def payroll_entry(self, payroll_period, staff):
        return PayrollEntry.objects.create(
            period=payroll_period, staff=staff,
            gross_pay=250000, net_pay=200000,
        )

    def test_deduction_type_choices(self, payroll_entry):
        """deduction_type が有効な選択肢を受け付ける"""
        d = PayrollDeduction.objects.create(
            entry=payroll_entry,
            deduction_type='pension',
            amount=18300,
        )
        valid = [
            'income_tax', 'resident_tax', 'pension',
            'health_insurance', 'employment_insurance',
            'long_term_care', 'workers_comp', 'other',
        ]
        assert d.deduction_type in valid

    def test_is_employer_only_flag(self, payroll_entry):
        """is_employer_only のデフォルトは False、設定すれば True"""
        d = PayrollDeduction.objects.create(
            entry=payroll_entry,
            deduction_type='workers_comp',
            amount=600,
            is_employer_only=True,
        )
        assert d.is_employer_only is True

    def test_str_format(self, payroll_entry):
        """__str__ が '控除種別表示: 金額円' 形式"""
        d = PayrollDeduction.objects.create(
            entry=payroll_entry,
            deduction_type='income_tax',
            amount=12000,
        )
        s = str(d)
        assert '所得税' in s
        assert '12,000' in s


# ==============================
# SalaryStructure
# ==============================


@pytest.mark.django_db
class TestSalaryStructure:
    """SalaryStructure モデルテスト"""

    def test_defaults(self, salary_structure):
        """デフォルトの料率が正しく設定されている"""
        assert salary_structure.pension_rate == Decimal('9.150')
        assert salary_structure.overtime_multiplier == Decimal('1.25')

    def test_one_to_one_with_store(self, salary_structure, store):
        """Store との 1:1 関係が正しく設定されている"""
        assert store.salary_structure == salary_structure

    def test_str_format(self, salary_structure):
        """__str__ が '店舗名 給与体系' 形式"""
        s = str(salary_structure)
        assert salary_structure.store.name in s
        assert '給与体系' in s
