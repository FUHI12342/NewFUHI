"""
Tests for booking.services.zengin_export — 全銀フォーマットCSV生成.
"""
import csv
import io
import pytest
from datetime import date
from decimal import Decimal

from booking.models import PayrollEntry, PayrollPeriod
from booking.services.zengin_export import generate_zengin_csv, _pad_right, _to_zenkaku_kana


@pytest.mark.django_db
class TestGenerateZenginCsv:
    """generate_zengin_csv: PayrollPeriod → 全銀フォーマットCSV"""

    @pytest.fixture
    def payroll_entry(self, payroll_period, staff, employment_contract):
        """net_pay > 0 の PayrollEntry を作成"""
        return PayrollEntry.objects.create(
            period=payroll_period,
            staff=staff,
            contract=employment_contract,
            gross_pay=250000,
            total_deductions=50000,
            net_pay=200000,
        )

    def _parse_csv(self, csv_text):
        """CSV文字列を行リストにパースする"""
        reader = csv.reader(io.StringIO(csv_text))
        return list(reader)

    def test_header_record_starts_with_1(self, payroll_period, payroll_entry):
        """ヘッダーレコードの先頭が '1' である"""
        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        assert rows[0][0] == '1'

    def test_header_type_code_21(self, payroll_period, payroll_entry):
        """ヘッダーの種別コードが '21'（総合振込）"""
        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        assert rows[0][1] == '21'

    def test_data_record_has_2_prefix(self, payroll_period, payroll_entry):
        """データレコードの先頭が '2' である"""
        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        # rows[1] がデータレコード
        assert rows[1][0] == '2'

    def test_trailer_record_has_8_prefix(self, payroll_period, payroll_entry):
        """トレーラーレコードの先頭が '8' である"""
        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        # header(1) + data(1) + trailer + end
        trailer = rows[-2]
        assert trailer[0] == '8'

    def test_end_record_has_9(self, payroll_period, payroll_entry):
        """エンドレコードの先頭が '9' である"""
        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        assert rows[-1][0] == '9'

    def test_trailer_correct_count_and_total(self, payroll_period, payroll_entry):
        """トレーラーの件数と合計金額が正しい"""
        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        trailer = rows[-2]
        assert int(trailer[1]) == 1  # 1件
        assert int(trailer[2]) == 200000  # 合計金額

    def test_staff_name_in_data_record(self, payroll_period, payroll_entry, staff):
        """データレコードにスタッフ名が含まれる"""
        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        data_row = rows[1]
        # 受取人名は index 8
        assert staff.name in data_row[8]

    def test_net_pay_10_digit_zero_padded(self, payroll_period, payroll_entry):
        """振込金額が10桁ゼロパディングされている"""
        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        data_row = rows[1]
        # 振込金額は index 9
        amount_str = data_row[9]
        assert amount_str == '0000200000'
        assert len(amount_str) == 10

    def test_empty_entries_zero_count_total(self, payroll_period):
        """net_pay > 0 のエントリが無い場合、件数・合計ともにゼロ"""
        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        trailer = rows[-2]
        assert int(trailer[1]) == 0  # 件数
        assert int(trailer[2]) == 0  # 合計

    def test_multiple_entries_correct_totals(
        self, payroll_period, staff, employment_contract, store,
    ):
        """複数エントリの件数・合計が正しい"""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        PayrollEntry.objects.create(
            period=payroll_period, staff=staff,
            gross_pay=300000, total_deductions=50000, net_pay=250000,
        )
        # 2人目のスタッフ
        user2 = User.objects.create_user(username='staff2', password='pass123')
        from booking.models import Staff
        staff2 = Staff.objects.create(name='スタッフ2', store=store, user=user2)
        PayrollEntry.objects.create(
            period=payroll_period, staff=staff2,
            gross_pay=200000, total_deductions=30000, net_pay=170000,
        )

        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        trailer = rows[-2]
        assert int(trailer[1]) == 2
        assert int(trailer[2]) == 250000 + 170000

    def test_payment_date_formatting(self, payroll_period, payroll_entry):
        """payment_date がヘッダーに MMDD 形式で含まれる"""
        # payroll_period.payment_date = date(2025, 5, 25) → '0525'
        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        header = rows[0]
        # 振込指定日は index 3
        assert header[3] == '0525'

    def test_store_name_in_header(self, payroll_period, payroll_entry):
        """ヘッダーの依頼人名に店舗名が含まれる"""
        result = generate_zengin_csv(payroll_period)
        rows = self._parse_csv(result)
        header = rows[0]
        # 依頼人名は index 5
        assert payroll_period.store.name in header[5]


class TestPadRight:
    """_pad_right ユーティリティ"""

    def test_pads_short_string(self):
        result = _pad_right('ABC', 10)
        assert len(result) == 10
        assert result.startswith('ABC')

    def test_truncates_long_string(self):
        result = _pad_right('A' * 50, 10)
        assert len(result) == 10


class TestToZenkakuKana:
    """_to_zenkaku_kana: Phase 1 ではそのまま返す"""

    def test_returns_same_text(self):
        assert _to_zenkaku_kana('テスト') == 'テスト'
