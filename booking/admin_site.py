from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
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
GROUPS = [
    {'slug': 'reservation', 'name': _('予約管理'), 'models': ['schedule']},
    {'slug': 'shift', 'name': _('シフト管理'), 'models': ['shiftperiod', 'shiftrequest', 'shiftassignment', 'shifttemplate', 'shiftpublishhistory']},
    {'slug': 'cast', 'name': _('キャスト管理'), 'models': ['staff', 'storescheduleconfig']},
    {'slug': 'payroll', 'name': _('給与管理'), 'models': ['payrollperiod', 'payrollentry', 'employmentcontract', 'salarystructure'], 'hidden': True},
    {'slug': 'attendance', 'name': _('勤怠管理'), 'models': ['workattendance', 'attendancetotpconfig', 'attendancestamp'], 'hidden': True},
    {'slug': 'inventory', 'name': _('在庫管理'), 'models': ['category', 'product'], 'hidden': True},
    {'slug': 'order', 'name': _('注文管理'), 'models': ['order', 'postransaction']},
    {'slug': 'table_order', 'name': _('店舗管理'), 'models': ['store', 'tableseat']},
    {'slug': 'iot', 'name': _('IoT管理'), 'models': ['iotdevice']},
    {'slug': 'payment', 'name': _('決済'), 'models': ['paymentmethod'], 'hidden': True},
    {'slug': 'property', 'name': _('物件管理'), 'models': ['property'], 'hidden': True},
    {'slug': 'analytics', 'name': _('分析'), 'models': ['visitorcount', 'visitoranalyticsconfig', 'staffrecommendationmodel', 'staffrecommendationresult'], 'hidden': True},
    {'slug': 'page_settings', 'name': _('ページ設定'), 'models': ['sitesettings']},
    {'slug': 'page_settings_sub', 'name': _('ページ設定(サブ)'), 'models': ['company', 'notice', 'media', 'homepagecustomblock', 'herobanner', 'bannerad', 'externallink'], 'hidden': True},
    {'slug': 'system', 'name': _('システム'), 'models': ['systemconfig', 'admintheme', 'dashboardlayout', 'adminmenuconfig']},
    {'slug': 'security', 'name': _('セキュリティ'), 'models': ['securityaudit', 'securitylog', 'costreport']},
    {'slug': 'user_account', 'name': _('ユーザーアカウント管理'), 'models': ['user', 'group']},
]

# slug ベースのルックアップ（gettext_lazy のハッシュはロケールで変わるため）
_GROUP_BY_SLUG = {g['slug']: g for g in GROUPS}
HIDDEN_SLUGS = {g['slug'] for g in GROUPS if g.get('hidden')}
HIDDEN_MODELS = set()
for g in GROUPS:
    if g.get('hidden'):
        HIDDEN_MODELS.update(g['models'])

# 後方互換: forms.py / admin.py から参照される GROUP_MAP（slug→models）
GROUP_MAP = {g['slug']: g['models'] for g in GROUPS}

# サイドバーに注入するカスタムリンク（slug → リンクリスト）
SIDEBAR_CUSTOM_LINKS = {
    'reservation': [
        {'name': _('売上ダッシュボード'), 'admin_url': '/admin/dashboard/sales/', 'icon': 'fas fa-chart-line'},
        {'name': _('顧客分析'), 'admin_url': '/admin/analytics/visitors/', 'icon': 'fas fa-chart-bar'},
        {'name': _('AI推薦'), 'admin_url': '/admin/ai/recommendation/', 'icon': 'fas fa-robot'},
    ],
    'shift': [
        {'name': _('シフトカレンダー'), 'admin_url': '/admin/shift/calendar/', 'icon': 'fas fa-calendar-alt'},
        {'name': _('PIN打刻'), 'admin_url': '/admin/attendance/pin/', 'icon': 'fas fa-key'},
        {'name': _('出退勤ボード'), 'admin_url': '/admin/attendance/board/', 'icon': 'fas fa-clipboard-check'},
    ],
    'order': [
        {'name': _('POS'), 'admin_url': '/admin/pos/', 'icon': 'fas fa-cash-register'},
        {'name': _('オーダー履歴'), 'admin_url': '/admin/pos/kitchen/', 'icon': 'fas fa-utensils'},
    ],
    'system': [
        {'name': _('デバッグパネル'), 'admin_url': '/admin/debug/', 'icon': 'fas fa-bug'},
    ],
}


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
        'shifttemplate', 'shiftpublishhistory',
        'storescheduleconfig', 'admintheme',
        'sitesettings', 'homepagecustomblock',
        'herobanner', 'bannerad', 'externallink',
        'payrollperiod', 'payrollentry', 'employmentcontract',
        'salarystructure', 'workattendance',
        'attendancetotpconfig', 'attendancestamp',
        'tableseat', 'paymentmethod', 'postransaction',
        'visitorcount', 'visitoranalyticsconfig',
        'staffrecommendationmodel', 'staffrecommendationresult',
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
    enable_nav_sidebar = False  # Django 4.x のダークサイドバーを無効化

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
        """フラットなモデルリストを仮想アプリグループに再構成（slug ベース）"""
        # 全モデルをフラットに収集
        all_models = {}
        for app in raw_app_list:
            for model in app.get('models', []):
                key = model['object_name'].lower()
                all_models[key] = model

        # GROUPS の定義順に slug ベースで再グループ化
        result = []
        used_keys = set()
        for g in GROUPS:
            slug = g['slug']
            model_keys = g['models']
            # 非表示グループはスキップ
            if slug in HIDDEN_SLUGS:
                used_keys.update(k for k in model_keys if k in all_models)
                continue
            group_models = []
            for key in model_keys:
                if key in all_models:
                    group_models.append(all_models[key])
                    used_keys.add(key)
            # カスタムリンクをモデルエントリとして追加
            for link in SIDEBAR_CUSTOM_LINKS.get(slug, []):
                group_models.append({
                    'name': str(link['name']),
                    'object_name': '',
                    'perms': {'view': True},
                    'admin_url': link['admin_url'],
                    'view_only': True,
                })
            if group_models:
                result.append({
                    'name': g['name'],
                    'slug': slug,
                    'app_label': slug,
                    'app_url': f'/admin/{slug}/',
                    'has_module_perms': True,
                    'models': group_models,
                })

        # GROUPS に含まれないモデルは「その他」グループに
        other_models = []
        for key, model in all_models.items():
            if key not in used_keys:
                other_models.append(model)
                used_keys.add(key)
        if other_models:
            result.append({
                'name': _('その他'),
                'slug': 'other',
                'app_label': 'other',
                'app_url': '/admin/other/',
                'has_module_perms': True,
                'models': other_models,
            })

        return result


custom_site = RoleBasedAdminSite(name="admin")
