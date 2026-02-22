from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from .models import Staff
import logging
import time

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
    '給与管理': ['payrollperiod', 'payrollentry', 'employmentcontract', 'salarystructure'],
    '勤怠管理': ['workattendance'],
    '在庫管理': ['category', 'product'],
    '注文管理': ['order'],
    'IoT管理': ['iotdevice'],
    '物件管理': ['property'],
    '予約ページ情報': ['company', 'notice', 'media'],
    'ページ設定': ['sitesettings', 'homepagecustomblock', 'herobanner', 'bannerad', 'externallink'],
    'システム': ['systemconfig', 'admintheme', 'dashboardlayout', 'adminmenuconfig'],
    'ユーザーアカウント管理': ['user', 'group'],
}

# グループの表示順序
GROUP_ORDER = list(GROUP_MAP.keys())


# ==============================
# デフォルト許可モデル定数（DB未設定時のフォールバック）
# None = 全モデル表示
# ==============================
DEFAULT_ALLOWED_MODELS = {
    'developer': None,  # 全モデル表示
    'owner': None,      # 全モデル表示
    'manager': [
        'schedule', 'order', 'staff', 'store',
        'iotdevice', 'category', 'product', 'producttranslation',
        'property', 'propertydevice',
        'systemconfig',
        'shiftperiod', 'shiftrequest', 'shiftassignment',
        'storescheduleconfig', 'admintheme',
        'sitesettings', 'homepagecustomblock',
        'herobanner', 'bannerad', 'externallink',
        'payrollperiod', 'payrollentry', 'employmentcontract',
        'salarystructure', 'workattendance',
    ],
    'staff': [
        'schedule', 'order', 'staff',
        'iotdevice', 'product',
        'shiftrequest',
    ],
}


# ==============================
# メニュー設定キャッシュ（5分TTL）
# ==============================
_menu_config_cache = {}
_menu_config_cache_time = 0.0
_MENU_CACHE_TTL = 300  # 5分


def _refresh_menu_config_cache():
    """AdminMenuConfig を読み込みキャッシュを更新する（lazy import で循環回避）"""
    global _menu_config_cache, _menu_config_cache_time
    try:
        from .models import AdminMenuConfig
        configs = AdminMenuConfig.objects.all()
        _menu_config_cache = {c.role: c.allowed_models for c in configs}
    except Exception:
        _menu_config_cache = {}
    _menu_config_cache_time = time.time()


def invalidate_menu_config_cache():
    """admin 保存時にキャッシュを即時無効化する"""
    global _menu_config_cache, _menu_config_cache_time
    _menu_config_cache = {}
    _menu_config_cache_time = 0.0


def _get_allowed_models_for_role(role):
    """ロールに対応する許可モデルリストを返す。DB設定優先、未設定時はデフォルト。"""
    global _menu_config_cache_time
    now = time.time()
    if now - _menu_config_cache_time > _MENU_CACHE_TTL:
        _refresh_menu_config_cache()

    if role in _menu_config_cache:
        db_value = _menu_config_cache[role]
        if isinstance(db_value, list) and len(db_value) > 0:
            return db_value
        # DB行はあるが空リスト → デフォルトにフォールバック

    return DEFAULT_ALLOWED_MODELS.get(role)


class RoleBasedAdminSite(AdminSite):
    def get_app_list(self, request, app_label=None):
        role = get_user_role(request)
        logger.info(
            "get_app_list: user=%s, role=%s, app_label=%s",
            request.user.username if request.user.is_authenticated else 'anon',
            role, app_label,
        )

        raw = super().get_app_list(request, app_label)

        # superuser は常に全モデル表示
        if role == 'superuser':
            return self._regroup_apps(raw)

        # それ以外は _get_allowed_models_for_role() で判定
        allowed = _get_allowed_models_for_role(role)

        # None = 全モデル表示（developer / owner のデフォルト）
        if allowed is None:
            return self._regroup_apps(raw)

        # リストでフィルタ
        filtered = []
        for app in raw:
            models = [m for m in app['models'] if m['object_name'].lower() in allowed]
            if models:
                app_copy = app.copy()
                app_copy['models'] = models
                filtered.append(app_copy)

        return self._regroup_apps(filtered)

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
