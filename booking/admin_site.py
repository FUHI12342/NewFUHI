from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.urls import reverse
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
    'キャスト管理': ['staff', 'store', 'storescheduleconfig'],
    '給与管理': ['payrollperiod', 'payrollentry', 'employmentcontract', 'salarystructure'],
    '勤怠管理': ['workattendance'],
    '在庫管理': ['category', 'product'],
    '注文管理': ['order'],
    'テーブル注文': ['tableseat', 'paymentmethod'],
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
        'tableseat', 'paymentmethod',
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

        # superuser は Django 標準の権限システムで全モデル表示
        if role == 'superuser':
            raw = super().get_app_list(request, app_label)
            return self._regroup_apps(raw)

        # 未認証 / Staff なしユーザー
        if role == 'none':
            return []

        # role-based ユーザー (developer/owner/manager/staff):
        # Django の権限システムを迂回し、レジストリから全モデルを取得。
        # 表示制御は独自のロールベースフィルタで行う。
        raw = self._build_full_app_list(app_label)

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

    def _build_full_app_list(self, app_label=None):
        """レジストリから全モデルのリストを構築（Django の権限チェックを迂回）"""
        app_dict = {}
        for model, model_admin in self._registry.items():
            lbl = model._meta.app_label
            if app_label and lbl != app_label:
                continue
            info = (self.name, lbl, model._meta.model_name)
            model_dict = {
                'model': model,
                'name': str(model._meta.verbose_name_plural),
                'object_name': model._meta.object_name,
                'perms': {'add': True, 'change': True, 'delete': True, 'view': True},
                'admin_url': reverse('%s:%s_%s_changelist' % info),
                'add_url': reverse('%s:%s_%s_add' % info),
                'view_only': False,
            }
            if lbl in app_dict:
                app_dict[lbl]['models'].append(model_dict)
            else:
                app_dict[lbl] = {
                    'name': lbl.title(),
                    'app_label': lbl,
                    'app_url': reverse('%s:app_list' % self.name, kwargs={'app_label': lbl}),
                    'has_module_perms': True,
                    'models': [model_dict],
                }
        app_list = sorted(app_dict.values(), key=lambda x: x['name'].lower())
        for app in app_list:
            app['models'].sort(key=lambda x: x['name'])
        return app_list

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
