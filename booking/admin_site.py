from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from .models import Staff
import logging

logger = logging.getLogger(__name__)

def get_user_role(request):
    if not request.user.is_authenticated:
        return 'none'
    if request.user.is_superuser:
        return 'superuser'
    staff = Staff.objects.filter(user=request.user).select_related("store").first()
    if staff:
        if staff.is_developer:
            return 'developer'
        elif staff.is_owner:
            return 'owner'
        elif staff.is_store_manager:
            return 'manager'
        else:
            return 'staff'
    return 'none'


# 仮想アプリグループ定義 (superuser/developer/owner 向け)
GROUP_MAP = {
    '予約管理': ['schedule'],
    'シフト管理': ['shiftperiod', 'shiftrequest', 'shiftassignment'],
    'スタッフ管理': ['staff', 'store', 'storescheduleconfig'],
    '在庫管理': ['category', 'product'],
    '注文管理': ['order'],
    'IoT管理': ['iotdevice'],
    '物件管理': ['property'],
    '予約ページ情報': ['company', 'notice', 'media'],
    'システム': ['systemconfig', 'admintheme', 'dashboardlayout'],
    'ユーザーアカウント管理': ['user', 'group'],
}

# グループの表示順序
GROUP_ORDER = list(GROUP_MAP.keys())


class RoleBasedAdminSite(AdminSite):
    def get_app_list(self, request, app_label=None):
        role = get_user_role(request)
        logger.info(
            "get_app_list: user=%s, role=%s, app_label=%s",
            request.user.username if request.user.is_authenticated else 'anon',
            role, app_label,
        )

        if role in ('superuser', 'developer', 'owner'):
            raw = super().get_app_list(request, app_label)
            return self._regroup_apps(raw)

        app_list = super().get_app_list(request, app_label)

        if role == 'manager':
            allowed_models = [
                'schedule', 'order', 'staff', 'store',
                'iotdevice', 'category', 'product', 'producttranslation',
                'property', 'propertydevice',
                'systemconfig',
                # シフト管理
                'shiftperiod', 'shiftrequest', 'shiftassignment',
                'storescheduleconfig', 'admintheme',
            ]
        elif role == 'staff':
            allowed_models = [
                'schedule', 'order', 'staff',
                'iotdevice', 'product',
                # スタッフはシフト希望のみ
                'shiftrequest',
            ]
        else:
            allowed_models = ['schedule', 'order']

        filtered = []
        for app in app_list:
            models = [m for m in app['models'] if m['object_name'].lower() in allowed_models]
            if models:
                app_copy = app.copy()
                app_copy['models'] = models
                filtered.append(app_copy)

        # manager/staff もグループ化
        if role in ('manager', 'staff'):
            return self._regroup_apps(filtered)

        return filtered

    def _regroup_apps(self, raw_app_list):
        """フラットなモデルリストを仮想アプリグループに再構成"""
        # 全モデルをフラットに収集
        all_models = {}
        for app in raw_app_list:
            for model in app.get('models', []):
                key = model['object_name'].lower()
                all_models[key] = model

        # GROUP_MAP に従って再グループ化
        result = []
        used_keys = set()
        for group_name in GROUP_ORDER:
            model_keys = GROUP_MAP[group_name]
            group_models = []
            for key in model_keys:
                if key in all_models:
                    group_models.append(all_models[key])
                    used_keys.add(key)
            if group_models:
                result.append({
                    'name': group_name,
                    'app_label': 'booking',
                    'app_url': '/admin/booking/',
                    'has_module_perms': True,
                    'models': group_models,
                })

        # GROUP_MAP に含まれないモデルは「その他」グループに
        other_models = []
        for key, model in all_models.items():
            if key not in used_keys:
                other_models.append(model)
                used_keys.add(key)
        if other_models:
            result.append({
                'name': 'その他',
                'app_label': 'booking',
                'app_url': '/admin/booking/',
                'has_module_perms': True,
                'models': other_models,
            })

        return result


custom_site = RoleBasedAdminSite(name="admin")
