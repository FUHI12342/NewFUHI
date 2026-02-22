"""
全銀フォーマットCSV生成

PayrollPeriod から全銀フォーマットの振込データCSVを生成する。
Phase 1: スタッフ名のみ（口座情報はPhase 3のEmployeeSensitiveInfoで対応）
"""
import csv
import io
import logging
from datetime import date

logger = logging.getLogger(__name__)


def generate_zengin_csv(period):
    """給与計算期間から全銀フォーマットCSVを生成する。

    全銀フォーマット（総合振込）の簡易版:
    - ヘッダーレコード (1行目)
    - データレコード (従業員ごと1行)
    - トレーラーレコード (最終行)
    - エンドレコード

    Phase 1 では口座情報が未実装のため、ダミー口座番号を使用。

    Args:
        period: PayrollPeriod instance

    Returns:
        str: CSV文字列
    """
    from booking.models import PayrollEntry

    entries = PayrollEntry.objects.filter(
        period=period,
        net_pay__gt=0,
    ).select_related('staff').order_by('staff__name')

    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')

    payment_date = period.payment_date or date.today()
    payment_date_str = payment_date.strftime('%m%d')

    # ヘッダーレコード
    # 種別(1), 種別コード(2:21=総合振込), 依頼日(4桁MMDD), 振込指定日(4桁MMDD),
    # 依頼人コード(10), 依頼人名(40), 振込元銀行(4), 振込元支店(3),
    # 口座種別(1:1=普通), 口座番号(7), ダミー(17)
    header = [
        '1',                          # データ区分: ヘッダー
        '21',                         # 種別コード: 総合振込
        '0',                          # コード区分
        payment_date_str,             # 振込指定日
        '0000000000',                 # 依頼人コード (要設定)
        _pad_right(period.store.name, 40),  # 依頼人名
        '0000',                       # 振込元銀行コード (要設定)
        '000',                        # 振込元支店コード (要設定)
        '1',                          # 口座種別: 普通
        '0000000',                    # 口座番号 (要設定)
        '',                           # ダミー
    ]
    writer.writerow(header)

    # データレコード
    total_amount = 0
    total_count = 0

    for entry in entries:
        staff_name = _to_zenkaku_kana(entry.staff.name)
        amount = entry.net_pay

        data = [
            '2',                      # データ区分: データ
            '0000',                   # 振込先銀行コード (Phase 3で実装)
            _pad_right('', 15),       # 振込先銀行名
            '000',                    # 振込先支店コード (Phase 3で実装)
            _pad_right('', 15),       # 振込先支店名
            '0',                      # 手形交換所番号
            '1',                      # 口座種別: 普通
            '0000000',                # 口座番号 (Phase 3で実装)
            _pad_right(staff_name, 30),  # 受取人名
            str(amount).zfill(10),    # 振込金額
            '0',                      # 新規コード
            '',                       # EDI情報
            '',                       # 振込区分
            '',                       # ダミー
        ]
        writer.writerow(data)
        total_amount += amount
        total_count += 1

    # トレーラーレコード
    trailer = [
        '8',                          # データ区分: トレーラー
        str(total_count).zfill(6),    # 合計件数
        str(total_amount).zfill(12),  # 合計金額
        '',                           # ダミー
    ]
    writer.writerow(trailer)

    # エンドレコード
    end = [
        '9',                          # データ区分: エンド
    ]
    writer.writerow(end)

    result = output.getvalue()
    output.close()

    logger.info(
        "Generated Zengin CSV for %s %s: %d entries, total=%d",
        period.store.name, period.year_month, total_count, total_amount,
    )

    return result


def _pad_right(s: str, length: int) -> str:
    """文字列を指定長まで半角スペースで右パディングする。"""
    encoded = s.encode('shift_jis', errors='replace')[:length]
    return encoded.decode('shift_jis', errors='replace').ljust(length)


def _to_zenkaku_kana(text: str) -> str:
    """カタカナの半角→全角変換（簡易版）。

    全銀フォーマットでは半角カナが使われるが、
    Phase 1 ではスタッフ名をそのまま使用する。
    """
    return text
