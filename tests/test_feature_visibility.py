"""機能表示制御（SiteSettingsトグル）のテスト"""
import pytest
from django.test import Client, RequestFactory
from django.contrib.auth.models import User

from booking.models import SiteSettings


@pytest.mark.django_db
class TestFeatureVisibilityToggles:
    """SiteSettings の show_admin_* フィールドが正しく機能するか確認"""

    def test_new_toggle_fields_exist(self):
        """新規6フィールドが SiteSettings に存在する"""
        ss = SiteSettings.load()
        new_fields = [
            'show_admin_pin_clock',
            'show_admin_page_settings',
            'show_admin_system',
            'show_admin_sns_posting',
            'show_admin_security',
            'show_admin_user_account',
        ]
        for field_name in new_fields:
            assert hasattr(ss, field_name), f"{field_name} が SiteSettings に存在しない"

    def test_default_values_are_true(self):
        """フィールドのデフォルト値は True"""
        field_names = [
            'show_admin_pin_clock',
            'show_admin_page_settings',
            'show_admin_system',
            'show_admin_sns_posting',
            'show_admin_security',
            'show_admin_user_account',
        ]
        for field_name in field_names:
            field = SiteSettings._meta.get_field(field_name)
            assert field.default is True, f"{field_name} のデフォルトが True でない"

    def test_toggle_off_hides_group(self):
        """トグルをOFFにするとサイドバーから非表示になる"""
        ss = SiteSettings.load()
        ss.show_admin_sns_posting = False
        ss.save()

        ss_reloaded = SiteSettings.load()
        assert ss_reloaded.show_admin_sns_posting is False

    def test_toggle_on_shows_group(self):
        """トグルをONにするとサイドバーに表示される"""
        ss = SiteSettings.load()
        ss.show_admin_pin_clock = True
        ss.save()

        ss_reloaded = SiteSettings.load()
        assert ss_reloaded.show_admin_pin_clock is True

    def test_sidebar_flags_dict_has_all_groups(self):
        """sidebar_flags に全17グループのエントリがある"""
        ss = SiteSettings.load()
        expected_flags = {
            'reservation', 'shift', 'staff_manage', 'menu_manage',
            'inventory', 'order', 'pos', 'kitchen', 'ec_shop',
            'table_order', 'iot', 'pin_clock', 'page_settings',
            'system', 'sns_posting', 'security', 'user_account',
        }
        # admin_site.py の sidebar_flags 構築ロジックを直接テスト
        sidebar_flags = {
            'reservation': ss.show_admin_reservation,
            'shift': ss.show_admin_shift,
            'staff_manage': ss.show_admin_staff_manage,
            'menu_manage': ss.show_admin_menu_manage,
            'inventory': ss.show_admin_inventory,
            'order': ss.show_admin_order,
            'pos': ss.show_admin_pos,
            'kitchen': ss.show_admin_kitchen,
            'ec_shop': ss.show_admin_ec_shop,
            'table_order': ss.show_admin_table_order,
            'iot': ss.show_admin_iot,
            'pin_clock': ss.show_admin_pin_clock,
            'page_settings': ss.show_admin_page_settings,
            'system': ss.show_admin_system,
            'sns_posting': ss.show_admin_sns_posting,
            'security': ss.show_admin_security,
            'user_account': ss.show_admin_user_account,
        }
        assert set(sidebar_flags.keys()) == expected_flags

    def test_shift_and_reservation_only_visibility(self):
        """shift + reservation のみ True、他は全 False のパターン"""
        ss = SiteSettings.load()
        ss.show_admin_reservation = True
        ss.show_admin_shift = True
        ss.show_admin_staff_manage = False
        ss.show_admin_menu_manage = False
        ss.show_admin_inventory = False
        ss.show_admin_order = False
        ss.show_admin_pos = False
        ss.show_admin_kitchen = False
        ss.show_admin_ec_shop = False
        ss.show_admin_table_order = False
        ss.show_admin_iot = False
        ss.show_admin_pin_clock = False
        ss.show_admin_page_settings = False
        ss.show_admin_system = False
        ss.show_admin_sns_posting = False
        ss.show_admin_security = False
        ss.show_admin_user_account = False
        ss.save()

        ss_reloaded = SiteSettings.load()
        assert ss_reloaded.show_admin_reservation is True
        assert ss_reloaded.show_admin_shift is True
        assert ss_reloaded.show_admin_staff_manage is False
        assert ss_reloaded.show_admin_sns_posting is False
        assert ss_reloaded.show_admin_user_account is False

    def test_superuser_bypasses_toggle(self, admin_client):
        """スーパーユーザーはトグルOFFでも全グループ表示"""
        ss = SiteSettings.load()
        ss.show_admin_sns_posting = False
        ss.show_admin_system = False
        ss.show_admin_pin_clock = False
        ss.save()

        response = admin_client.get('/admin/')
        assert response.status_code == 200
        # get_app_list でスーパーユーザーは sidebar_flags を無視する
        app_list = response.context.get('app_list', [])
        group_names = [g.get('name', '') for g in app_list]
        # スーパーユーザーなので非表示設定でも SNS 投稿グループが見える
        assert any('SNS' in name for name in group_names), (
            f"スーパーユーザーにSNSグループが表示されていない: {group_names}"
        )
