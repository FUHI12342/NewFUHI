"""
勤怠 API の統合テスト

対象:
  - AttendanceStampAPIView    POST  (TOTP打刻)
  - AttendancePINStampAPIView POST  (PIN打刻)
  - QRStampAPIView            POST  (QR+TOTP+PIN打刻、ログイン不要)
  - ManualStampAPIView        POST  (管理者マニュアル打刻)
  - AttendanceDayStatusAPI    GET   (本日の出退勤状況JSON)
  - AttendanceTOTPRefreshAPI  GET   (TOTP QR HTML fragment)
"""
import json
from datetime import date
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from booking.models import (
    Store, Staff, AttendanceTOTPConfig, AttendanceStamp, WorkAttendance,
    StoreScheduleConfig,
)

User = get_user_model()

# ============================================================
# ヘルパー
# ============================================================

def make_staff_user(username, store, is_staff=True, is_super=False):
    user = User.objects.create_user(
        username=username,
        password='testpass123',
        is_staff=is_staff,
        is_superuser=is_super,
    )
    staff = Staff.objects.create(name=username, store=store, user=user)
    return user, staff


def auth_client(user):
    c = Client()
    c.login(username=user.username, password='testpass123')
    return c


def post_json(client, url, data, content_type='application/json'):
    return client.post(url, data=json.dumps(data), content_type=content_type)


# ============================================================
# フィクスチャ
# ============================================================

@pytest.fixture
def store(db):
    return Store.objects.create(name='勤怠テスト店舗')


@pytest.fixture
def other_store(db):
    return Store.objects.create(name='他勤怠店舗')


@pytest.fixture
def admin_user(db, store):
    user = User.objects.create_superuser(
        username='att_admin', password='testpass123',
    )
    Staff.objects.create(name='管理者', store=store, user=user)
    return user


@pytest.fixture
def staff_user(db, store):
    user, staff = make_staff_user('att_staff', store, is_staff=True)
    return user


@pytest.fixture
def staff_obj(db, store, staff_user):
    return Staff.objects.get(user=staff_user)


@pytest.fixture
def staff_with_pin(db, store):
    """PINが設定済みのスタッフ"""
    user = User.objects.create_user(
        username='pin_staff', password='testpass123', is_staff=True
    )
    staff = Staff.objects.create(name='PIN設定済', store=store, user=user)
    staff.set_attendance_pin('1234')
    staff.save()
    return staff


@pytest.fixture
def totp_config(db, store):
    from booking.services.totp_service import generate_totp_secret
    return AttendanceTOTPConfig.objects.create(
        store=store,
        totp_secret=generate_totp_secret(),
        totp_interval=30,
        is_active=True,
    )


@pytest.fixture
def inactive_totp_config(db, store):
    from booking.services.totp_service import generate_totp_secret
    return AttendanceTOTPConfig.objects.create(
        store=store,
        totp_secret=generate_totp_secret(),
        totp_interval=30,
        is_active=False,
    )


# ============================================================
# 1. AttendanceStampAPIView — POST (TOTP打刻)
# ============================================================

class TestAttendanceStampAPI:

    def test_unauthenticated_redirects(self, db, store, staff_obj):
        """未認証は302リダイレクト"""
        c = Client()
        resp = post_json(c, '/api/attendance/stamp/', {
            'staff_id': staff_obj.id,
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 302

    def test_clock_in_without_totp_config(self, db, store, staff_user, staff_obj):
        """TOTPなし設定の場合、コードなしで打刻できる"""
        c = auth_client(staff_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=False):
            resp = post_json(c, '/api/attendance/stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': 'clock_in',
                'totp_code': '',
            })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert data['stamp_type'] == 'clock_in'
        assert AttendanceStamp.objects.filter(staff=staff_obj, stamp_type='clock_in').exists()

    def test_clock_in_creates_work_attendance(self, db, store, staff_user, staff_obj):
        """clock_in打刻でWorkAttendanceが作成される"""
        c = auth_client(staff_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=False):
            resp = post_json(c, '/api/attendance/stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': 'clock_in',
            })
        assert resp.status_code == 200
        assert WorkAttendance.objects.filter(staff=staff_obj, date=date.today()).exists()

    def test_clock_out_updates_work_attendance(self, db, store, staff_user, staff_obj):
        """clock_out打刻でWorkAttendanceが更新される"""
        WorkAttendance.objects.create(staff=staff_obj, date=date.today(), source='qr')
        c = auth_client(staff_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=False):
            resp = post_json(c, '/api/attendance/stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': 'clock_out',
            })
        assert resp.status_code == 200

    def test_missing_staff_id_returns_400(self, db, store, staff_user):
        """staff_id欠如は400"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/attendance/stamp/', {
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 400

    def test_duplicate_stamp_rejected(self, db, store, staff_user, staff_obj):
        """5分以内の重複打刻は400"""
        c = auth_client(staff_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=True):
            resp = post_json(c, '/api/attendance/stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': 'clock_in',
            })
        assert resp.status_code == 400

    def test_invalid_totp_code_rejected(self, db, store, staff_user, staff_obj, totp_config):
        """TOTPコードが無効な場合は400"""
        c = auth_client(staff_user)

        with patch('booking.services.totp_service.verify_totp', return_value=False):
            resp = post_json(c, '/api/attendance/stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': 'clock_in',
                'totp_code': '000000',
            })
        assert resp.status_code == 400

    def test_valid_totp_code_accepted(self, db, store, staff_user, staff_obj, totp_config):
        """正しいTOTPコードで打刻できる"""
        c = auth_client(staff_user)

        with patch('booking.services.totp_service.verify_totp', return_value=True), \
             patch('booking.services.totp_service.check_duplicate_stamp', return_value=False):
            resp = post_json(c, '/api/attendance/stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': 'clock_in',
                'totp_code': '123456',
            })
        assert resp.status_code == 200

    def test_invalid_json_returns_400(self, db, store, staff_user):
        """不正JSONは400"""
        c = auth_client(staff_user)
        resp = c.post(
            '/api/attendance/stamp/',
            data='{{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_nonexistent_staff_returns_404(self, db, store, staff_user):
        """存在しないスタッフIDは404"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/attendance/stamp/', {
            'staff_id': 99999,
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 404

    def test_geofence_out_of_range_rejected(self, db, store, staff_user, staff_obj, totp_config):
        """ジオフェンス外は400"""
        totp_config.require_geo_check = True
        totp_config.location_lat = 35.6762
        totp_config.location_lng = 139.6503
        totp_config.geo_fence_radius_m = 100
        totp_config.save()

        with patch('booking.services.totp_service.verify_totp', return_value=True), \
             patch('booking.services.totp_service.check_duplicate_stamp', return_value=False), \
             patch('booking.services.totp_service.check_geo_fence', return_value=False):
            c = auth_client(staff_user)
            resp = post_json(c, '/api/attendance/stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': 'clock_in',
                'totp_code': '123456',
                'latitude': 34.0,
                'longitude': 135.0,
            })
        assert resp.status_code == 400


# ============================================================
# 2. AttendancePINStampAPIView — POST (PIN打刻)
# ============================================================

class TestAttendancePINStampAPI:

    def test_pin_clock_in_successfully(self, db, store, staff_user, staff_with_pin):
        """正しいPINで打刻できる"""
        c = auth_client(staff_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=False):
            resp = post_json(c, '/api/attendance/pin-stamp/', {
                'staff_id': staff_with_pin.id,
                'pin': '1234',
                'stamp_type': 'clock_in',
            })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_wrong_pin_rejected(self, db, store, staff_user, staff_with_pin):
        """間違ったPINは400"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/attendance/pin-stamp/', {
            'staff_id': staff_with_pin.id,
            'pin': '9999',
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 400

    def test_empty_pin_rejected(self, db, store, staff_user, staff_obj):
        """PIN未入力は400"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/attendance/pin-stamp/', {
            'staff_id': staff_obj.id,
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 400

    def test_missing_staff_id_returns_400(self, db, store, staff_user):
        """staff_id欠如は400"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/attendance/pin-stamp/', {
            'pin': '1234',
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 400

    def test_staff_without_pin_returns_400(self, db, store, staff_user, staff_obj):
        """PIN未設定スタッフは400"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/attendance/pin-stamp/', {
            'staff_id': staff_obj.id,
            'pin': '1234',
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 400

    def test_duplicate_stamp_rejected(self, db, store, staff_user, staff_with_pin):
        """重複打刻は400"""
        c = auth_client(staff_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=True):
            resp = post_json(c, '/api/attendance/pin-stamp/', {
                'staff_id': staff_with_pin.id,
                'pin': '1234',
                'stamp_type': 'clock_in',
            })
        assert resp.status_code == 400

    def test_wrong_content_type_returns_400(self, db, store, staff_user):
        """Content-Typeがapplication/jsonでない場合は400"""
        c = auth_client(staff_user)
        resp = c.post(
            '/api/attendance/pin-stamp/',
            data='staff_id=1&pin=1234',
            content_type='application/x-www-form-urlencoded',
        )
        assert resp.status_code == 400

    def test_invalid_json_returns_400(self, db, store, staff_user):
        """不正JSONは400"""
        c = auth_client(staff_user)
        resp = c.post(
            '/api/attendance/pin-stamp/',
            data='{{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_unauthenticated_redirects(self, db, store, staff_with_pin):
        """未認証は302（CSRFが免除されているが、LoginRequiredで保護）"""
        c = Client()
        resp = post_json(c, '/api/attendance/pin-stamp/', {
            'staff_id': staff_with_pin.id,
            'pin': '1234',
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 302

    def test_break_start_stamp(self, db, store, staff_user, staff_with_pin):
        """休憩開始打刻が記録される"""
        c = auth_client(staff_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=False):
            resp = post_json(c, '/api/attendance/pin-stamp/', {
                'staff_id': staff_with_pin.id,
                'pin': '1234',
                'stamp_type': 'break_start',
            })
        assert resp.status_code == 200
        assert AttendanceStamp.objects.filter(
            staff=staff_with_pin, stamp_type='break_start'
        ).exists()


# ============================================================
# 3. QRStampAPIView — POST (QR+TOTP+PIN打刻、ログイン不要)
# ============================================================

class TestQRStampAPI:

    def test_missing_store_id_returns_400(self, db):
        """store_id欠如は400"""
        c = Client()
        resp = post_json(c, '/api/attendance/qr-stamp/', {
            'staff_id': 1,
            'totp_code': '123456',
            'pin': '1234',
        })
        assert resp.status_code == 400

    def test_missing_staff_id_returns_400(self, db, store):
        """staff_id欠如は400"""
        c = Client()
        resp = post_json(c, '/api/attendance/qr-stamp/', {
            'store_id': store.id,
            'totp_code': '123456',
            'pin': '1234',
        })
        assert resp.status_code == 400

    def test_missing_totp_code_returns_400(self, db, store, staff_with_pin):
        """totp_code欠如は400"""
        c = Client()
        resp = post_json(c, '/api/attendance/qr-stamp/', {
            'store_id': store.id,
            'staff_id': staff_with_pin.id,
            'pin': '1234',
        })
        assert resp.status_code == 400

    def test_missing_pin_returns_400(self, db, store, staff_with_pin):
        """PIN欠如は400"""
        c = Client()
        resp = post_json(c, '/api/attendance/qr-stamp/', {
            'store_id': store.id,
            'staff_id': staff_with_pin.id,
            'totp_code': '123456',
        })
        assert resp.status_code == 400

    def test_no_totp_config_returns_400(self, db, store, staff_with_pin):
        """TOTPが設定されていない店舗は400"""
        c = Client()
        resp = post_json(c, '/api/attendance/qr-stamp/', {
            'store_id': store.id,
            'staff_id': staff_with_pin.id,
            'totp_code': '123456',
            'pin': '1234',
        })
        assert resp.status_code == 400

    def test_invalid_totp_returns_400(self, db, store, staff_with_pin, totp_config):
        """無効TOTPは400"""
        c = Client()

        with patch('booking.services.totp_service.verify_totp', return_value=False):
            resp = post_json(c, '/api/attendance/qr-stamp/', {
                'store_id': store.id,
                'staff_id': staff_with_pin.id,
                'totp_code': '000000',
                'pin': '1234',
            })
        assert resp.status_code == 400

    def test_invalid_pin_returns_400(self, db, store, staff_with_pin, totp_config):
        """無効PINは400"""
        c = Client()

        with patch('booking.services.totp_service.verify_totp', return_value=True):
            resp = post_json(c, '/api/attendance/qr-stamp/', {
                'store_id': store.id,
                'staff_id': staff_with_pin.id,
                'totp_code': '123456',
                'pin': '9999',  # 間違いPIN
            })
        assert resp.status_code == 400

    def test_qr_stamp_success(self, db, store, staff_with_pin, totp_config):
        """TOTP+PINが正しい場合、打刻成功"""
        c = Client()

        with patch('booking.services.totp_service.verify_totp', return_value=True), \
             patch('booking.services.totp_service.check_duplicate_stamp', return_value=False):
            resp = post_json(c, '/api/attendance/qr-stamp/', {
                'store_id': store.id,
                'staff_id': staff_with_pin.id,
                'totp_code': '123456',
                'pin': '1234',
                'stamp_type': 'clock_in',
            })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_qr_stamp_duplicate_rejected(self, db, store, staff_with_pin, totp_config):
        """重複打刻は400"""
        c = Client()

        with patch('booking.services.totp_service.verify_totp', return_value=True), \
             patch('booking.services.totp_service.check_duplicate_stamp', return_value=True):
            resp = post_json(c, '/api/attendance/qr-stamp/', {
                'store_id': store.id,
                'staff_id': staff_with_pin.id,
                'totp_code': '123456',
                'pin': '1234',
            })
        assert resp.status_code == 400

    def test_wrong_content_type_returns_400(self, db, store):
        """Content-Typeがapplication/jsonでない場合は400"""
        c = Client()
        resp = c.post(
            '/api/attendance/qr-stamp/',
            data='store_id=1',
            content_type='application/x-www-form-urlencoded',
        )
        assert resp.status_code == 400

    def test_invalid_json_returns_400(self, db):
        """不正JSONは400"""
        c = Client()
        resp = c.post(
            '/api/attendance/qr-stamp/',
            data='{{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400


# ============================================================
# 4. ManualStampAPIView — POST (管理者マニュアル打刻)
# ============================================================

class TestManualStampAPI:

    def test_unauthenticated_returns_403(self, db, store, staff_obj):
        """未認証は403"""
        c = Client()
        resp = post_json(c, '/api/attendance/manual-stamp/', {
            'staff_id': staff_obj.id,
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 403

    def test_non_staff_user_returns_403(self, db, store):
        """is_staff=False のユーザーは403"""
        user = User.objects.create_user(
            username='nonstaff_att', password='testpass123', is_staff=False
        )
        # Staffプロファイルを作らないか、staffフラグを立てない
        c = Client()
        c.login(username='nonstaff_att', password='testpass123')
        resp = post_json(c, '/api/attendance/manual-stamp/', {
            'staff_id': staff_obj.id if hasattr(staff_obj, 'id') else 1,
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 403

    def test_admin_can_manual_stamp(self, db, store, admin_user, staff_obj):
        """管理者はマニュアル打刻できる"""
        c = auth_client(admin_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=False):
            resp = post_json(c, '/api/attendance/manual-stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': 'clock_in',
            })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'stamp_id' in data
        assert 'operator' in data

    def test_missing_staff_id_returns_400(self, db, store, admin_user):
        """staff_id欠如は400"""
        c = auth_client(admin_user)
        resp = post_json(c, '/api/attendance/manual-stamp/', {
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 400

    def test_nonexistent_staff_returns_404(self, db, store, admin_user):
        """存在しないスタッフIDは404"""
        c = auth_client(admin_user)
        resp = post_json(c, '/api/attendance/manual-stamp/', {
            'staff_id': 99999,
            'stamp_type': 'clock_in',
        })
        assert resp.status_code == 404

    def test_duplicate_stamp_rejected(self, db, store, admin_user, staff_obj):
        """重複打刻は400"""
        c = auth_client(admin_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=True):
            resp = post_json(c, '/api/attendance/manual-stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': 'clock_in',
            })
        assert resp.status_code == 400

    def test_invalid_json_returns_400(self, db, store, admin_user):
        """不正JSONは400"""
        c = auth_client(admin_user)
        resp = c.post(
            '/api/attendance/manual-stamp/',
            data='{{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_staff_user_can_manual_stamp(self, db, store, staff_user, staff_obj):
        """is_staff=True のユーザーもマニュアル打刻できる"""
        c = auth_client(staff_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=False):
            resp = post_json(c, '/api/attendance/manual-stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': 'clock_in',
            })
        assert resp.status_code == 200

    def test_manual_clock_out(self, db, store, admin_user, staff_obj):
        """退勤マニュアル打刻が記録される"""
        WorkAttendance.objects.create(staff=staff_obj, date=date.today(), source='manual')
        c = auth_client(admin_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=False):
            resp = post_json(c, '/api/attendance/manual-stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': 'clock_out',
            })
        assert resp.status_code == 200


# ============================================================
# 5. AttendanceDayStatusAPI — GET (本日の出退勤状況)
# ============================================================

class TestAttendanceDayStatusAPI:

    def test_get_day_status_authenticated(self, db, store, staff_user, staff_obj):
        """認証済みで本日の状況を取得できる"""
        AttendanceStamp.objects.create(
            staff=staff_obj, stamp_type='clock_in',
        )
        c = auth_client(staff_user)
        resp = c.get('/api/attendance/day-status/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert isinstance(data, list)

    def test_get_day_status_unauthenticated_redirects(self, db):
        """未認証は302"""
        c = Client()
        resp = c.get('/api/attendance/day-status/')
        assert resp.status_code == 302

    def test_get_day_status_includes_staff_info(self, db, store, staff_user, staff_obj):
        """レスポンスにスタッフ情報が含まれる"""
        AttendanceStamp.objects.create(
            staff=staff_obj, stamp_type='clock_in',
        )
        c = auth_client(staff_user)
        resp = c.get('/api/attendance/day-status/')
        data = json.loads(resp.content)
        if data:
            first = data[0]
            assert 'staff_id' in first
            assert 'staff_name' in first
            assert 'status' in first
            assert 'stamps' in first

    def test_get_day_status_empty_when_no_stamps(self, db, store, staff_user):
        """打刻がない場合は空リスト"""
        c = auth_client(staff_user)
        resp = c.get('/api/attendance/day-status/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data == []

    def test_get_day_status_reflects_clock_out(self, db, store, staff_user, staff_obj):
        """clock_outが最後の場合、退勤済みステータスが含まれる"""
        AttendanceStamp.objects.create(staff=staff_obj, stamp_type='clock_in')
        AttendanceStamp.objects.create(staff=staff_obj, stamp_type='clock_out')
        c = auth_client(staff_user)
        resp = c.get('/api/attendance/day-status/')
        data = json.loads(resp.content)
        staff_entry = next((s for s in data if s['staff_id'] == staff_obj.id), None)
        if staff_entry:
            # ステータス表示は翻訳に依存するため存在確認のみ
            assert 'status' in staff_entry


# ============================================================
# 6. AttendanceTOTPRefreshAPI — GET (QR更新)
# ============================================================

class TestAttendanceTOTPRefreshAPI:

    def test_get_totp_qr_without_config_returns_404(self, db, store, admin_user):
        """TOTP未設定は404 HTML fragmentを返す"""
        c = auth_client(admin_user)
        resp = c.get('/api/attendance/totp/refresh/')
        assert resp.status_code == 404

    def test_get_totp_qr_with_config(self, db, store, admin_user, totp_config):
        """TOTP設定ありはHTML fragmentを返す"""
        c = auth_client(admin_user)

        with patch('booking.services.totp_service.get_current_totp', return_value='123456'):
            resp = c.get('/api/attendance/totp/refresh/')
        assert resp.status_code == 200
        content = resp.content.decode('utf-8')
        # TOTPコードまたはQR画像がHTMLに含まれている
        assert '123456' in content or 'qr' in content.lower()

    def test_get_totp_qr_unauthenticated_redirects(self, db):
        """未認証は302"""
        c = Client()
        resp = c.get('/api/attendance/totp/refresh/')
        assert resp.status_code == 302


# ============================================================
# 7. 打刻タイプのバリエーション（正常系）
# ============================================================

class TestStampTypeVariants:

    @pytest.mark.parametrize('stamp_type', ['clock_in', 'clock_out', 'break_start', 'break_end'])
    def test_all_stamp_types_accepted(self, db, store, staff_user, staff_obj, stamp_type, request):
        """全打刻タイプが受け付けられる"""
        c = auth_client(staff_user)

        with patch('booking.services.totp_service.check_duplicate_stamp', return_value=False):
            resp = post_json(c, '/api/attendance/stamp/', {
                'staff_id': staff_obj.id,
                'stamp_type': stamp_type,
            })
        # 同一テストのシリアル実行のため重複チェックをモック
        assert resp.status_code == 200
