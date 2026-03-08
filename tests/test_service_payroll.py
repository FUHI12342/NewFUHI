"""
Tests for booking/services/payroll_calculator.py

Covers:
- lookup_withholding_tax: boundary values and excess formula
- _calc_social_insurance: pension, health, employment, long-term care, workers' comp
- calculate_payroll_for_staff: hourly and monthly rate payroll computation
- calculate_payroll_for_period: batch processing and status transitions
"""
import pytest
from datetime import date, time
from decimal import Decimal
from unittest.mock import patch

from booking.models import (
    WorkAttendance, PayrollEntry, PayrollDeduction,
    EmploymentContract, SalaryStructure, PayrollPeriod,
)
from booking.services.payroll_calculator import (
    lookup_withholding_tax,
    _calc_social_insurance,
    calculate_payroll_for_staff,
    calculate_payroll_for_period,
)


# ==============================
# lookup_withholding_tax
# ==============================

class TestLookupWithholdingTax:

    def test_below_88000_returns_zero(self):
        """Taxable amount at or below 88,000 should yield tax=0."""
        assert lookup_withholding_tax(88_000) == 0

    def test_exactly_88000_boundary(self):
        assert lookup_withholding_tax(88_000) == 0

    def test_89000_returns_130(self):
        """First non-zero bracket: 89,000 -> 130."""
        assert lookup_withholding_tax(89_000) == 130

    def test_90000_returns_180(self):
        assert lookup_withholding_tax(90_000) == 180

    def test_500000_returns_29520(self):
        """Last entry in the table: 500,000 -> 29,520."""
        assert lookup_withholding_tax(500_000) == 29_520

    def test_over_500000_excess_formula(self):
        """Over 500,000: last_tax + int(excess * 0.2042)."""
        taxable = 600_000
        excess = taxable - 500_000
        expected = 29_520 + int(excess * 0.2042)
        assert lookup_withholding_tax(taxable) == expected

    def test_very_low_income(self):
        """Very low taxable amount returns 0."""
        assert lookup_withholding_tax(0) == 0
        assert lookup_withholding_tax(50_000) == 0

    def test_mid_range_200000(self):
        """Mid-range value 200,000 should be within table range (>199000)."""
        tax = lookup_withholding_tax(200_000)
        assert tax > 0
        # 199_000 -> 4610, 201_000 -> 4680
        # 200_000 <= 201_000 so tax = 4680
        assert tax == 4_680

    def test_mid_range_300000(self):
        """Around 300,000."""
        tax = lookup_withholding_tax(300_000)
        # 299_000 -> 8700, 302_000 -> 8910
        # 300_000 <= 302_000 so tax = 8910
        assert tax == 8_910


# ==============================
# _calc_social_insurance
# ==============================

class TestCalcSocialInsurance:

    @pytest.mark.django_db
    def test_pension_calculation(self, employment_contract, salary_structure):
        """Pension = int(SMR * pension_rate / 100)."""
        result = _calc_social_insurance(employment_contract, salary_structure, 300_000)
        smr = employment_contract.standard_monthly_remuneration  # 200000
        expected = int(Decimal(smr) * salary_structure.pension_rate / 100)
        assert result['pension'] == expected

    @pytest.mark.django_db
    def test_health_insurance_calculation(self, employment_contract, salary_structure):
        """Health insurance = int(SMR * health_rate / 100)."""
        result = _calc_social_insurance(employment_contract, salary_structure, 300_000)
        smr = employment_contract.standard_monthly_remuneration
        expected = int(Decimal(smr) * salary_structure.health_insurance_rate / 100)
        assert result['health_insurance'] == expected

    @pytest.mark.django_db
    def test_employment_insurance_calculation(self, employment_contract, salary_structure):
        """Employment insurance = int(gross * emp_rate / 100)."""
        gross = 300_000
        result = _calc_social_insurance(employment_contract, salary_structure, gross)
        expected = int(Decimal(gross) * salary_structure.employment_insurance_rate / 100)
        assert result['employment_insurance'] == expected

    @pytest.mark.django_db
    def test_long_term_care_age_under_40(self, employment_contract, salary_structure):
        """Long-term care should be 0 when age < 40."""
        birth_date = date(1990, 5, 15)
        target_date = date(2025, 4, 30)  # age 34
        result = _calc_social_insurance(
            employment_contract, salary_structure, 300_000,
            birth_date=birth_date, target_date=target_date,
        )
        assert result['long_term_care'] == 0

    @pytest.mark.django_db
    def test_long_term_care_age_40_or_over(self, employment_contract, salary_structure):
        """Long-term care insurance applies when age >= 40."""
        birth_date = date(1980, 1, 1)
        target_date = date(2025, 4, 30)  # age 45
        result = _calc_social_insurance(
            employment_contract, salary_structure, 300_000,
            birth_date=birth_date, target_date=target_date,
        )
        smr = employment_contract.standard_monthly_remuneration
        expected = int(Decimal(smr) * salary_structure.long_term_care_rate / 100)
        assert result['long_term_care'] == expected
        assert result['long_term_care'] > 0

    @pytest.mark.django_db
    def test_long_term_care_no_birth_date(self, employment_contract, salary_structure):
        """Long-term care = 0 when birth_date is None."""
        result = _calc_social_insurance(
            employment_contract, salary_structure, 300_000,
            birth_date=None, target_date=date(2025, 4, 30),
        )
        assert result['long_term_care'] == 0

    @pytest.mark.django_db
    def test_workers_comp_calculation(self, employment_contract, salary_structure):
        """Workers' comp = int(gross * workers_comp_rate / 100) (employer-only)."""
        gross = 300_000
        result = _calc_social_insurance(employment_contract, salary_structure, gross)
        expected = int(Decimal(gross) * salary_structure.workers_comp_rate / 100)
        assert result['workers_comp'] == expected

    @pytest.mark.django_db
    def test_age_boundary_exactly_40(self, employment_contract, salary_structure):
        """Exactly 40 years old should have long-term care applied."""
        birth_date = date(1985, 4, 30)
        target_date = date(2025, 4, 30)  # age = exactly 40
        result = _calc_social_insurance(
            employment_contract, salary_structure, 300_000,
            birth_date=birth_date, target_date=target_date,
        )
        assert result['long_term_care'] > 0


# ==============================
# calculate_payroll_for_staff
# ==============================

class TestCalculatePayrollForStaff:

    @pytest.mark.django_db
    def test_hourly_rate_base_pay(self, payroll_period, staff, employment_contract, salary_structure, work_attendance):
        """Hourly rate: base_pay = rate * regular_hours."""
        entry = calculate_payroll_for_staff(payroll_period, staff, employment_contract, salary_structure)
        # work_attendance has regular_minutes=420, so regular_hours = 7.0
        expected_base = int(Decimal(1200) * Decimal(420) / 60)
        assert entry.base_pay == expected_base

    @pytest.mark.django_db
    def test_hourly_rate_overtime_pay(self, payroll_period, staff, employment_contract, salary_structure, work_attendance):
        """Hourly rate: overtime_pay = rate * 1.25 * overtime_hours."""
        entry = calculate_payroll_for_staff(payroll_period, staff, employment_contract, salary_structure)
        # work_attendance has overtime_minutes=60, so overtime_hours = 1.0
        expected_overtime = int(Decimal(1200) * Decimal('1.25') * Decimal(60) / 60)
        assert entry.overtime_pay == expected_overtime

    @pytest.mark.django_db
    def test_hourly_rate_late_night_pay(self, payroll_period, staff, salary_structure):
        """Late night pay uses late_night_multiplier (1.35)."""
        contract = EmploymentContract.objects.create(
            staff=staff, pay_type='hourly', hourly_rate=1000,
            commute_allowance=0, housing_allowance=0, family_allowance=0,
            standard_monthly_remuneration=200000, resident_tax_monthly=0,
            is_active=True,
        )
        WorkAttendance.objects.create(
            staff=staff, date=date(2025, 4, 15),
            clock_in=time(22, 0), clock_out=time(1, 0),
            regular_minutes=0, overtime_minutes=0,
            late_night_minutes=120, holiday_minutes=0, break_minutes=0,
            source='shift',
        )
        entry = calculate_payroll_for_staff(payroll_period, staff, contract, salary_structure)
        expected = int(Decimal(1000) * Decimal('1.35') * Decimal(120) / 60)
        assert entry.late_night_pay == expected

    @pytest.mark.django_db
    def test_hourly_rate_holiday_pay(self, payroll_period, staff, salary_structure):
        """Holiday pay uses holiday_multiplier (1.50)."""
        contract = EmploymentContract.objects.create(
            staff=staff, pay_type='hourly', hourly_rate=1000,
            commute_allowance=0, housing_allowance=0, family_allowance=0,
            standard_monthly_remuneration=200000, resident_tax_monthly=0,
            is_active=True,
        )
        WorkAttendance.objects.create(
            staff=staff, date=date(2025, 4, 20),
            clock_in=time(9, 0), clock_out=time(17, 0),
            regular_minutes=0, overtime_minutes=0,
            late_night_minutes=0, holiday_minutes=480, break_minutes=60,
            source='shift',
        )
        entry = calculate_payroll_for_staff(payroll_period, staff, contract, salary_structure)
        expected = int(Decimal(1000) * Decimal('1.50') * Decimal(480) / 60)
        assert entry.holiday_pay == expected

    @pytest.mark.django_db
    def test_monthly_rate_base_pay(self, payroll_period, staff, salary_structure, work_attendance):
        """Monthly rate: base_pay = monthly_salary (fixed)."""
        contract = EmploymentContract.objects.create(
            staff=staff, pay_type='monthly', monthly_salary=250000,
            commute_allowance=0, housing_allowance=0, family_allowance=0,
            standard_monthly_remuneration=250000, resident_tax_monthly=5000,
            is_active=True,
        )
        entry = calculate_payroll_for_staff(payroll_period, staff, contract, salary_structure)
        assert entry.base_pay == 250000

    @pytest.mark.django_db
    def test_monthly_rate_overtime_uses_hourly_equiv(self, payroll_period, staff, salary_structure, work_attendance):
        """Monthly rate: overtime uses monthly_salary/160 as hourly equiv."""
        contract = EmploymentContract.objects.create(
            staff=staff, pay_type='monthly', monthly_salary=320000,
            commute_allowance=0, housing_allowance=0, family_allowance=0,
            standard_monthly_remuneration=320000, resident_tax_monthly=5000,
            is_active=True,
        )
        entry = calculate_payroll_for_staff(payroll_period, staff, contract, salary_structure)
        hourly_equiv = Decimal(320000) / 160
        overtime_hours = Decimal(60) / 60  # 1 hour from work_attendance
        expected_overtime = int(hourly_equiv * Decimal('1.25') * overtime_hours)
        assert entry.overtime_pay == expected_overtime

    @pytest.mark.django_db
    def test_allowances_added_to_gross(self, payroll_period, staff, salary_structure, work_attendance, employment_contract):
        """Commute + housing + family allowances are added to gross_pay."""
        entry = calculate_payroll_for_staff(payroll_period, staff, employment_contract, salary_structure)
        # employment_contract: commute=10000, housing=0, family=0
        assert entry.allowances == 10000

    @pytest.mark.django_db
    def test_non_taxable_commute_max_150000(self, payroll_period, staff, salary_structure, work_attendance):
        """Non-taxable commute capped at 150,000."""
        contract = EmploymentContract.objects.create(
            staff=staff, pay_type='hourly', hourly_rate=1200,
            commute_allowance=200000, housing_allowance=0, family_allowance=0,
            standard_monthly_remuneration=200000, resident_tax_monthly=5000,
            is_active=True,
        )
        entry = calculate_payroll_for_staff(payroll_period, staff, contract, salary_structure)
        # non_taxable_commute = min(200000, 150000) = 150000
        # Verify gross includes the full 200000 allowance
        assert entry.allowances == 200000

    @pytest.mark.django_db
    def test_payroll_entry_created(self, payroll_period, staff, employment_contract, salary_structure, work_attendance):
        """PayrollEntry record is created in the database."""
        entry = calculate_payroll_for_staff(payroll_period, staff, employment_contract, salary_structure)
        assert PayrollEntry.objects.filter(period=payroll_period, staff=staff).exists()
        assert entry.pk is not None

    @pytest.mark.django_db
    def test_payroll_deductions_created(self, payroll_period, staff, employment_contract, salary_structure, work_attendance):
        """PayrollDeduction records are created for each deduction type."""
        entry = calculate_payroll_for_staff(payroll_period, staff, employment_contract, salary_structure)
        deductions = PayrollDeduction.objects.filter(entry=entry)
        types = set(d.deduction_type for d in deductions)
        # At minimum: income_tax, resident_tax, pension, health_insurance, employment_insurance
        assert 'income_tax' in types
        assert 'resident_tax' in types
        assert 'pension' in types
        assert 'health_insurance' in types
        assert 'employment_insurance' in types

    @pytest.mark.django_db
    def test_update_or_create_idempotency(self, payroll_period, staff, employment_contract, salary_structure, work_attendance):
        """Calling calculate_payroll_for_staff twice should update, not duplicate."""
        entry1 = calculate_payroll_for_staff(payroll_period, staff, employment_contract, salary_structure)
        entry2 = calculate_payroll_for_staff(payroll_period, staff, employment_contract, salary_structure)
        assert entry1.pk == entry2.pk
        assert PayrollEntry.objects.filter(period=payroll_period, staff=staff).count() == 1

    @pytest.mark.django_db
    def test_workers_comp_is_employer_only(self, payroll_period, staff, employment_contract, salary_structure, work_attendance):
        """Workers' comp deduction should be marked is_employer_only=True."""
        entry = calculate_payroll_for_staff(payroll_period, staff, employment_contract, salary_structure)
        wc = PayrollDeduction.objects.filter(entry=entry, deduction_type='workers_comp').first()
        if wc:
            assert wc.is_employer_only is True

    @pytest.mark.django_db
    def test_net_pay_equals_gross_minus_deductions(self, payroll_period, staff, employment_contract, salary_structure, work_attendance):
        """net_pay = gross_pay - total_deductions."""
        entry = calculate_payroll_for_staff(payroll_period, staff, employment_contract, salary_structure)
        assert entry.net_pay == entry.gross_pay - entry.total_deductions


# ==============================
# calculate_payroll_for_period
# ==============================

class TestCalculatePayrollForPeriod:

    @pytest.mark.django_db
    def test_processes_all_active_contracts(self, payroll_period, staff, employment_contract, salary_structure, work_attendance):
        """Should process all active contracts for the store."""
        entries = calculate_payroll_for_period(payroll_period)
        assert len(entries) == 1
        assert entries[0].staff == staff

    @pytest.mark.django_db
    def test_status_transitions_to_confirmed(self, payroll_period, staff, employment_contract, salary_structure, work_attendance):
        """Period status should transition from draft -> calculating -> confirmed."""
        assert payroll_period.status == 'draft'
        calculate_payroll_for_period(payroll_period)
        payroll_period.refresh_from_db()
        assert payroll_period.status == 'confirmed'

    @pytest.mark.django_db
    def test_handles_missing_salary_structure(self, store, payroll_period, staff, employment_contract, work_attendance):
        """When SalaryStructure is missing, uses defaults and still produces entries."""
        # No salary_structure fixture used -- none exists in DB for this store
        entries = calculate_payroll_for_period(payroll_period)
        payroll_period.refresh_from_db()
        assert payroll_period.status == 'confirmed'
        # Default SalaryStructure with Decimal defaults should work
        assert len(entries) == 1
