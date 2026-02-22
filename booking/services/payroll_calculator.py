"""
給与計算エンジン

処理フロー:
1. 期間内の WorkAttendance 集計（通常/残業/深夜/休日）
2. 総支給額計算（基本給 + 割増 + 手当）
3. 社会保険料計算（標準報酬月額 × 各料率）
4. 源泉徴収税計算（課税対象額から月額表参照）
5. 住民税加算（固定月額）
6. PayrollEntry + PayrollDeduction レコード生成
"""
import logging
from datetime import date
from decimal import Decimal, ROUND_DOWN

from django.db import transaction
from django.db.models import Sum

logger = logging.getLogger(__name__)


# ==============================
# 源泉徴収税額表（月額表・甲欄・扶養0人）簡易版
# 課税対象額（千円未満切捨て）→ 税額
# 国税庁 令和6年分以降を参考にした簡易テーブル
# Phase 2 で完全版CSV読み込みに置換予定
# ==============================
WITHHOLDING_TAX_TABLE = [
    # (課税対象額上限, 税額)
    (88_000, 0),
    (89_000, 130),
    (90_000, 180),
    (91_000, 230),
    (92_000, 290),
    (93_000, 340),
    (94_000, 390),
    (95_000, 440),
    (96_000, 500),
    (97_000, 550),
    (98_000, 600),
    (99_000, 650),
    (101_000, 720),
    (103_000, 830),
    (105_000, 930),
    (107_000, 1_030),
    (109_000, 1_130),
    (111_000, 1_240),
    (113_000, 1_340),
    (115_000, 1_440),
    (117_000, 1_540),
    (119_000, 1_640),
    (121_000, 1_750),
    (123_000, 1_850),
    (125_000, 1_950),
    (127_000, 2_050),
    (129_000, 2_150),
    (131_000, 2_260),
    (133_000, 2_360),
    (135_000, 2_460),
    (137_000, 2_550),
    (139_000, 2_610),
    (141_000, 2_680),
    (143_000, 2_740),
    (145_000, 2_810),
    (147_000, 2_870),
    (149_000, 2_940),
    (151_000, 3_000),
    (153_000, 3_070),
    (155_000, 3_140),
    (157_000, 3_200),
    (159_000, 3_270),
    (161_000, 3_340),
    (163_000, 3_400),
    (165_000, 3_470),
    (167_000, 3_540),
    (169_000, 3_600),
    (171_000, 3_670),
    (173_000, 3_740),
    (175_000, 3_810),
    (177_000, 3_870),
    (179_000, 3_940),
    (181_000, 4_010),
    (183_000, 4_070),
    (185_000, 4_140),
    (187_000, 4_210),
    (189_000, 4_280),
    (191_000, 4_340),
    (193_000, 4_410),
    (195_000, 4_480),
    (197_000, 4_550),
    (199_000, 4_610),
    (201_000, 4_680),
    (203_000, 4_750),
    (205_000, 4_820),
    (207_000, 4_890),
    (209_000, 4_950),
    (211_000, 5_020),
    (213_000, 5_090),
    (215_000, 5_160),
    (217_000, 5_220),
    (219_000, 5_290),
    (221_000, 5_360),
    (224_000, 5_460),
    (227_000, 5_600),
    (230_000, 5_730),
    (233_000, 5_860),
    (236_000, 5_990),
    (239_000, 6_110),
    (242_000, 6_240),
    (245_000, 6_370),
    (248_000, 6_500),
    (251_000, 6_630),
    (254_000, 6_750),
    (257_000, 6_880),
    (260_000, 7_010),
    (263_000, 7_140),
    (266_000, 7_270),
    (269_000, 7_400),
    (272_000, 7_530),
    (275_000, 7_660),
    (278_000, 7_790),
    (281_000, 7_920),
    (284_000, 8_040),
    (287_000, 8_170),
    (290_000, 8_300),
    (293_000, 8_430),
    (296_000, 8_560),
    (299_000, 8_700),
    (302_000, 8_910),
    (305_000, 9_190),
    (308_000, 9_470),
    (311_000, 9_750),
    (314_000, 10_030),
    (317_000, 10_310),
    (320_000, 10_590),
    (323_000, 10_870),
    (326_000, 11_150),
    (329_000, 11_430),
    (332_000, 11_710),
    (335_000, 11_990),
    (338_000, 12_270),
    (341_000, 12_550),
    (344_000, 12_830),
    (347_000, 13_110),
    (350_000, 13_390),
    (353_000, 13_670),
    (356_000, 13_950),
    (359_000, 14_230),
    (362_000, 14_510),
    (365_000, 14_790),
    (368_000, 15_070),
    (371_000, 15_350),
    (374_000, 15_630),
    (377_000, 15_910),
    (380_000, 16_190),
    (383_000, 16_470),
    (386_000, 16_750),
    (389_000, 17_030),
    (392_000, 17_310),
    (395_000, 17_590),
    (398_000, 17_870),
    (401_000, 18_150),
    (404_000, 18_480),
    (407_000, 18_830),
    (410_000, 19_170),
    (413_000, 19_520),
    (416_000, 19_860),
    (419_000, 20_210),
    (422_000, 20_550),
    (425_000, 20_900),
    (428_000, 21_240),
    (431_000, 21_590),
    (434_000, 21_930),
    (437_000, 22_280),
    (440_000, 22_620),
    (443_000, 22_970),
    (446_000, 23_310),
    (449_000, 23_660),
    (452_000, 24_000),
    (455_000, 24_350),
    (458_000, 24_690),
    (461_000, 25_040),
    (464_000, 25_380),
    (467_000, 25_730),
    (470_000, 26_070),
    (473_000, 26_420),
    (476_000, 26_760),
    (479_000, 27_110),
    (482_000, 27_450),
    (485_000, 27_800),
    (488_000, 28_140),
    (491_000, 28_490),
    (494_000, 28_830),
    (497_000, 29_180),
    (500_000, 29_520),
]


def lookup_withholding_tax(taxable_amount: int) -> int:
    """源泉徴収税額を月額表（甲欄・扶養0人）から参照する。"""
    for upper, tax in WITHHOLDING_TAX_TABLE:
        if taxable_amount <= upper:
            return tax
    # テーブル上限を超える場合: 超過分の20.42% + テーブル最終税額
    last_upper, last_tax = WITHHOLDING_TAX_TABLE[-1]
    excess = taxable_amount - last_upper
    return last_tax + int(excess * 0.2042)


def _calc_social_insurance(contract, salary_structure, gross_pay, birth_date=None, target_date=None):
    """社会保険料を計算して dict で返す。

    Returns:
        dict with keys: pension, health_insurance, employment_insurance,
                        long_term_care, workers_comp (employer-only)
    """
    smr = contract.standard_monthly_remuneration or 0

    # 厚生年金: 標準報酬月額 × 料率
    pension = int(Decimal(smr) * salary_structure.pension_rate / 100)

    # 健康保険: 標準報酬月額 × 料率
    health = int(Decimal(smr) * salary_structure.health_insurance_rate / 100)

    # 雇用保険: 総支給額 × 料率
    emp_ins = int(Decimal(gross_pay) * salary_structure.employment_insurance_rate / 100)

    # 介護保険: 40歳以上のみ
    ltc = 0
    if birth_date and target_date:
        age = target_date.year - birth_date.year
        if (target_date.month, target_date.day) < (birth_date.month, birth_date.day):
            age -= 1
        if age >= 40:
            ltc = int(Decimal(smr) * salary_structure.long_term_care_rate / 100)

    # 労災保険: 事業主全額負担（従業員控除なし、記録のみ）
    workers_comp = int(Decimal(gross_pay) * salary_structure.workers_comp_rate / 100)

    return {
        'pension': pension,
        'health_insurance': health,
        'employment_insurance': emp_ins,
        'long_term_care': ltc,
        'workers_comp': workers_comp,
    }


def calculate_payroll_for_staff(period, staff, contract, salary_structure):
    """個別スタッフの給与計算を行い PayrollEntry + PayrollDeduction を生成する。

    Args:
        period: PayrollPeriod instance
        staff: Staff instance
        contract: EmploymentContract instance
        salary_structure: SalaryStructure instance

    Returns:
        PayrollEntry instance (saved)
    """
    from booking.models import WorkAttendance, PayrollEntry, PayrollDeduction

    # 1. 期間内の WorkAttendance 集計
    attendances = WorkAttendance.objects.filter(
        staff=staff,
        date__gte=period.period_start,
        date__lte=period.period_end,
    )

    agg = attendances.aggregate(
        total_regular=Sum('regular_minutes'),
        total_overtime=Sum('overtime_minutes'),
        total_late_night=Sum('late_night_minutes'),
        total_holiday=Sum('holiday_minutes'),
    )

    regular_min = agg['total_regular'] or 0
    overtime_min = agg['total_overtime'] or 0
    late_night_min = agg['total_late_night'] or 0
    holiday_min = agg['total_holiday'] or 0

    work_days = attendances.count()

    regular_hours = Decimal(regular_min) / 60
    overtime_hours = Decimal(overtime_min) / 60
    late_night_hours = Decimal(late_night_min) / 60
    holiday_hours = Decimal(holiday_min) / 60

    # 2. 総支給額計算
    if contract.pay_type == 'hourly':
        rate = Decimal(contract.hourly_rate)
        base_pay = int(rate * regular_hours)
        overtime_pay = int(rate * salary_structure.overtime_multiplier * overtime_hours)
        late_night_pay = int(rate * salary_structure.late_night_multiplier * late_night_hours)
        holiday_pay = int(rate * salary_structure.holiday_multiplier * holiday_hours)
    else:
        # 月給制: 基本給固定、割増は月給÷所定労働時間(160h)で時間単価算出
        base_pay = contract.monthly_salary
        hourly_equiv = Decimal(contract.monthly_salary) / 160
        overtime_pay = int(hourly_equiv * salary_structure.overtime_multiplier * overtime_hours)
        late_night_pay = int(hourly_equiv * salary_structure.late_night_multiplier * late_night_hours)
        holiday_pay = int(hourly_equiv * salary_structure.holiday_multiplier * holiday_hours)

    allowances = contract.commute_allowance + contract.housing_allowance + contract.family_allowance
    gross_pay = base_pay + overtime_pay + late_night_pay + holiday_pay + allowances

    # 3. 社会保険料計算
    target_date = period.period_end
    insurance = _calc_social_insurance(
        contract, salary_structure, gross_pay,
        birth_date=contract.birth_date,
        target_date=target_date,
    )

    # 4. 源泉徴収税（課税対象額 = 総支給 - 社会保険料（従業員負担分）- 非課税通勤手当）
    employee_insurance = (
        insurance['pension'] + insurance['health_insurance'] +
        insurance['employment_insurance'] + insurance['long_term_care']
    )
    # 通勤手当は月15万円まで非課税（簡易処理: 全額非課税として扱う）
    non_taxable_commute = min(contract.commute_allowance, 150_000)
    taxable_amount = max(0, gross_pay - employee_insurance - non_taxable_commute)
    income_tax = lookup_withholding_tax(taxable_amount)

    # 5. 住民税
    resident_tax = contract.resident_tax_monthly

    # 6. 控除合計 & 差引支給額
    total_deductions = employee_insurance + income_tax + resident_tax
    net_pay = gross_pay - total_deductions

    # レコード生成
    with transaction.atomic():
        entry, created = PayrollEntry.objects.update_or_create(
            period=period,
            staff=staff,
            defaults={
                'contract': contract,
                'total_work_days': work_days,
                'total_regular_hours': regular_hours.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'total_overtime_hours': overtime_hours.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'total_late_night_hours': late_night_hours.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'total_holiday_hours': holiday_hours.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
                'base_pay': base_pay,
                'overtime_pay': overtime_pay,
                'late_night_pay': late_night_pay,
                'holiday_pay': holiday_pay,
                'allowances': allowances,
                'gross_pay': gross_pay,
                'total_deductions': total_deductions,
                'net_pay': net_pay,
            }
        )

        # 既存の控除を削除して再作成
        entry.deductions.all().delete()

        deduction_rows = [
            ('income_tax', income_tax, False),
            ('resident_tax', resident_tax, False),
            ('pension', insurance['pension'], False),
            ('health_insurance', insurance['health_insurance'], False),
            ('employment_insurance', insurance['employment_insurance'], False),
        ]
        if insurance['long_term_care'] > 0:
            deduction_rows.append(('long_term_care', insurance['long_term_care'], False))
        # 労災保険は事業主のみ
        if insurance['workers_comp'] > 0:
            deduction_rows.append(('workers_comp', insurance['workers_comp'], True))

        for dtype, amount, employer_only in deduction_rows:
            PayrollDeduction.objects.create(
                entry=entry,
                deduction_type=dtype,
                amount=amount,
                is_employer_only=employer_only,
            )

    logger.info(
        "Payroll calculated: %s %s gross=%d net=%d",
        staff.name, period.year_month, gross_pay, net_pay,
    )
    return entry


def calculate_payroll_for_period(period):
    """給与計算期間内の全スタッフの給与を一括計算する。

    Args:
        period: PayrollPeriod instance

    Returns:
        list of PayrollEntry instances
    """
    from booking.models import EmploymentContract, SalaryStructure

    try:
        salary_structure = SalaryStructure.objects.get(store=period.store)
    except SalaryStructure.DoesNotExist:
        logger.warning("SalaryStructure not found for store %s, using defaults", period.store.name)
        salary_structure = SalaryStructure(store=period.store)

    contracts = EmploymentContract.objects.filter(
        staff__store=period.store,
        is_active=True,
    ).select_related('staff')

    period.status = 'calculating'
    period.save(update_fields=['status'])

    entries = []
    for contract in contracts:
        try:
            entry = calculate_payroll_for_staff(period, contract.staff, contract, salary_structure)
            entries.append(entry)
        except Exception:
            logger.exception("Failed to calculate payroll for %s", contract.staff.name)

    period.status = 'confirmed'
    period.save(update_fields=['status'])

    return entries
