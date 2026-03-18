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


# 仮想アプリグループ定義
GROUPS = [
    {'slug': 'pin_clock', 'name': _('タイムカード打刻'), 'models': []},
    {'slug': 'reservation', 'name': _('予約管理'), 'models': ['schedule']},
    {'slug': 'shift', 'name': _('シフト'), 'models': ['shiftperiod', 'shiftrequest', 'shiftassignment', 'shifttemplate', 'shiftpublishhistory', 'storecloseddate'], 'hidden_models': ['shiftperiod', 'shiftrequest', 'shiftassignment', 'shifttemplate', 'shiftpublishhistory', 'storecloseddate']},
    {'slug': 'staff_manage', 'name': _('従業員管理'), 'models': ['staff', 'employmentcontract', 'storescheduleconfig', 'staffevaluation', 'evaluationcriteria'], 'hidden_models': ['staff', 'employmentcontract', 'storescheduleconfig', 'evaluationcriteria']},
    {'slug': 'payroll', 'name': _('給与管理'), 'models': ['payrollperiod', 'payrollentry', 'employmentcontract', 'salarystructure'], 'hidden': True},
    {'slug': 'attendance', 'name': _('勤怠管理'), 'models': ['workattendance', 'attendancetotpconfig', 'attendancestamp'], 'hidden': True},
    {'slug': 'menu_manage', 'name': _('店内メニュー'), 'models': ['category', 'product']},
    {'slug': 'inventory', 'name': _('在庫管理'), 'models': ['stockmovement']},
    {'slug': 'order', 'name': _('注文管理'), 'models': ['order']},
    {'slug': 'pos', 'name': _('レジ（POS）'), 'models': ['postransaction', 'taxservicecharge']},
    {'slug': 'kitchen', 'name': _('キッチンディスプレイ'), 'models': []},
    {'slug': 'ec_shop', 'name': _('オンラインショップ'), 'models': []},
    {'slug': 'table_order', 'name': _('店舗管理'), 'models': ['store', 'tableseat']},
    {'slug': 'iot', 'name': _('IoT管理'), 'models': ['iotdevice', 'ventilationautocontrol'], 'hidden_models': ['iotdevice']},
    {'slug': 'payment', 'name': _('決済'), 'models': ['paymentmethod'], 'hidden': True},
    {'slug': 'property', 'name': _('物件管理'), 'models': ['property'], 'hidden': True},
    {'slug': 'analytics', 'name': _('分析'), 'models': ['visitorcount', 'visitoranalyticsconfig', 'staffrecommendationmodel', 'staffrecommendationresult', 'businessinsight', 'customerfeedback'], 'hidden': True},
    {'slug': 'page_settings', 'name': _('メインページ設定'), 'models': ['sitesettings', 'notice']},
    {'slug': 'page_settings_sub', 'name': _('ページ設定(サブ)'), 'models': ['company', 'media', 'homepagecustomblock', 'herobanner', 'bannerad', 'externallink'], 'hidden': True},
    {'slug': 'system', 'name': _('システム'), 'models': ['systemconfig', 'admintheme', 'dashboardlayout', 'adminmenuconfig', 'adminsidebarsettings']},
    {'slug': 'security', 'name': _('セキュリティ'), 'models': ['securityaudit', 'securitylog', 'costreport']},
    {'slug': 'user_account', 'name': _('ユーザーアカウント管理'), 'models': ['user', 'group']},
]

# ロール別に表示するサイドバーグループ（None = 全グループ表示）
ROLE_VISIBLE_GROUPS = {
    'superuser': None,  # 全表示
    'developer': [
        'pin_clock', 'reservation', 'staff_manage',
        'menu_manage', 'inventory', 'order', 'pos', 'kitchen',
        'ec_shop', 'iot', 'system',
    ],
    'owner': None,      # 全表示
    'manager': [
        'pin_clock', 'reservation', 'shift', 'staff_manage',
        'menu_manage', 'inventory', 'order', 'pos', 'kitchen',
        'ec_shop', 'table_order', 'page_settings',
        'user_account', 'security',
    ],
    'staff': [
        'pin_clock', 'shift', 'staff_manage',
    ],
}

# slug ベースのルックアップ（gettext_lazy のハッシュはロケールで変わるため）
_GROUP_BY_SLUG = {g['slug']: g for g in GROUPS}
HIDDEN_SLUGS = {g['slug'] for g in GROUPS if g.get('hidden')}
HIDDEN_MODELS = set()
for g in GROUPS:
    if g.get('hidden'):
        HIDDEN_MODELS.update(g['models'])
    # グループは表示するがモデル単位で非表示にする
    for m in g.get('hidden_models', []):
        HIDDEN_MODELS.add(m)

# 後方互換: forms.py / admin.py から参照される GROUP_MAP（slug→models）
GROUP_MAP = {g['slug']: g['models'] for g in GROUPS}

# サイドバーに注入するカスタムリンク（slug → リンクリスト）
SIDEBAR_CUSTOM_LINKS = {
    'pin_clock': [
        {'name': _('タイムカード打刻'), 'admin_url': '/admin/attendance/pin/', 'icon': 'fas fa-key'},
        {'name': _('出退勤ボード'), 'admin_url': '/admin/attendance/board/', 'icon': 'fas fa-clipboard-check'},
    ],
    'reservation': [
        {'name': _('売上ダッシュボード'), 'admin_url': '/admin/dashboard/sales/', 'icon': 'fas fa-chart-line'},
        {'name': _('顧客分析'), 'admin_url': '/admin/analytics/visitors/', 'icon': 'fas fa-chart-bar'},
        {'name': _('AI推薦'), 'admin_url': '/admin/ai/recommendation/', 'icon': 'fas fa-robot'},
    ],
    'shift': [
        {'name': _('シフトカレンダー'), 'admin_url': '/admin/shift/calendar/', 'icon': 'fas fa-calendar-alt'},
        {'name': _('本日のシフト'), 'admin_url': '/admin/shift/today/', 'icon': 'fas fa-clock'},
    ],
    'staff_manage': [
        {'name': _('従業員一覧'), 'admin_url': '/admin/booking/staff/', 'icon': 'fas fa-users'},
        {'name': _('キャスト一覧'), 'admin_url': '/admin/booking/staff/?staff_type__exact=fortune_teller', 'icon': 'fas fa-star'},
        {'name': _('スタッフ一覧'), 'admin_url': '/admin/booking/staff/?staff_type__exact=store_staff', 'icon': 'fas fa-user'},
        {'name': _('勤怠実績'), 'admin_url': '/admin/attendance/performance/', 'icon': 'fas fa-chart-bar'},
    ],
    'order': [
        {'name': _('店内注文一覧'), 'admin_url': '/admin/booking/order/?channel__in=pos,table,reservation', 'icon': 'fas fa-utensils'},
        {'name': _('EC注文一覧'), 'admin_url': '/admin/booking/order/?channel=ec', 'icon': 'fas fa-shopping-cart'},
    ],
    'pos': [
        {'name': _('レジ画面'), 'admin_url': '/admin/pos/', 'icon': 'fas fa-cash-register'},
    ],
    'kitchen': [
        {'name': _('キッチンディスプレイ'), 'admin_url': '/admin/pos/kitchen/', 'icon': 'fas fa-utensils'},
    ],
    'menu_manage': [
        {'name': _('メニュープレビュー'), 'admin_url': '/admin/menu/preview/', 'icon': 'fas fa-eye'},
    ],
    'ec_shop': [
        {'name': _('EC注文管理'), 'admin_url': '/admin/ec/orders/', 'icon': 'fas fa-shipping-fast'},
        {'name': _('EC商品管理'), 'admin_url': '/admin/booking/product/?is_ec_visible__exact=1', 'icon': 'fas fa-boxes'},
    ],
    'inventory': [
        {'name': _('在庫ダッシュボード'), 'admin_url': '/admin/inventory/', 'icon': 'fas fa-boxes'},
    ],
    'iot': [
        {'name': _('センサーグラフ'), 'admin_url': '/admin/iot/sensors/', 'icon': 'fas fa-chart-area'},
    ],
    'system': [
        {'name': _('デバッグパネル'), 'admin_url': '/admin/debug/', 'icon': 'fas fa-bug'},
    ],
}

# ロール別カスタムリンク（指定があればSIDEBAR_CUSTOM_LINKSより優先）
SIDEBAR_CUSTOM_LINKS_BY_ROLE = {
    'shift': {
        'manager': [
            {'name': _('シフトカレンダー'), 'admin_url': '/admin/shift/calendar/', 'icon': 'fas fa-calendar-alt'},
            {'name': _('本日のシフト'), 'admin_url': '/admin/shift/today/', 'icon': 'fas fa-clock'},
        ],
        'staff': [
            {'name': _('シフトカレンダー'), 'admin_url': '/admin/shift/calendar/', 'icon': 'fas fa-calendar-alt'},
            {'name': _('本日のシフト'), 'admin_url': '/admin/shift/today/', 'icon': 'fas fa-clock'},
        ],
    },
}
# manager以上はシフトカレンダー + 本日のシフト
for _role in ('owner', 'developer', 'superuser'):
    SIDEBAR_CUSTOM_LINKS_BY_ROLE['shift'][_role] = SIDEBAR_CUSTOM_LINKS_BY_ROLE['shift']['manager']

# スタッフ管理: manager以上はフルメニュー、一般スタッフはマイページのみ
SIDEBAR_CUSTOM_LINKS_BY_ROLE['staff_manage'] = {
    'manager': [
        {'name': _('従業員一覧'), 'admin_url': '/admin/booking/staff/', 'icon': 'fas fa-users'},
        {'name': _('勤怠実績'), 'admin_url': '/admin/attendance/performance/', 'icon': 'fas fa-chart-bar'},
    ],
    'staff': [
        {'name': _('マイページ'), 'admin_url': '/admin/booking/staff/', 'icon': 'fas fa-id-card'},
    ],
}
for _role in ('owner', 'developer', 'superuser'):
    SIDEBAR_CUSTOM_LINKS_BY_ROLE['staff_manage'][_role] = SIDEBAR_CUSTOM_LINKS_BY_ROLE['staff_manage']['manager']


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
        'shifttemplate', 'shiftpublishhistory', 'shiftchangelog', 'storecloseddate',
        'storescheduleconfig', 'admintheme',
        'sitesettings', 'homepagecustomblock',
        'herobanner', 'bannerad', 'externallink',
        'payrollperiod', 'payrollentry', 'employmentcontract',
        'salarystructure', 'workattendance',
        'attendancetotpconfig', 'attendancestamp',
        'tableseat', 'paymentmethod', 'postransaction', 'producttranslation',
        'visitorcount', 'visitoranalyticsconfig',
        'staffrecommendationmodel', 'staffrecommendationresult',
        'staffevaluation', 'evaluationcriteria',
    ],
    'staff': [
        'schedule', 'order', 'staff',
        'iotdevice', 'product',
        'shiftrequest',
        'stockmovement',
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
    except Exception:  # DB not ready during startup
        _menu_config_cache = {}
    _menu_config_cache_time = time.time()


def invalidate_menu_config_cache():
    """admin 保存時にキャッシュを即時無効化する"""
    global _menu_config_cache, _menu_config_cache_time
    _menu_config_cache = {}
    _menu_config_cache_time = 0.0


def _get_allowed_models_for_role(role):
    """ロールに対応する許可モデルリストを返す。

    DB設定とコード側デフォルトをマージして返す。
    これにより、新モデル追加時にDB側の更新漏れがあっても
    DEFAULT_ALLOWED_MODELS に追加すれば自動的に反映される。
    """
    global _menu_config_cache_time
    now = time.time()
    if now - _menu_config_cache_time > _MENU_CACHE_TTL:
        _refresh_menu_config_cache()

    defaults = DEFAULT_ALLOWED_MODELS.get(role)
    # None = 全モデル表示（developer/owner のデフォルト）
    if defaults is None:
        # DB で明示的にリストが設定されていても、デフォルトが None なら None を返す
        # （全モデル表示の意図を尊重）
        if role not in _menu_config_cache:
            return None
        db_value = _menu_config_cache[role]
        if isinstance(db_value, list) and len(db_value) > 0:
            return db_value
        return None

    # DB値とデフォルトをマージ（和集合）
    if role in _menu_config_cache:
        db_value = _menu_config_cache[role]
        if isinstance(db_value, list) and len(db_value) > 0:
            merged = list(set(defaults) | set(db_value))
            return merged

    return defaults


class RoleBasedAdminSite(AdminSite):
    enable_nav_sidebar = False  # Django 4.x のダークサイドバーを無効化

    def has_permission(self, request):
        """role-basedユーザーにも管理画面アクセスを許可"""
        if super().has_permission(request):
            return True
        if not request.user.is_authenticated:
            return False
        role = get_user_role(request)
        return role not in ('none',)

    def register(self, model_or_iterable, admin_class=None, **options):
        """登録時にrole-basedのpermissionを自動適用"""
        super().register(model_or_iterable, admin_class, **options)
        models = model_or_iterable if hasattr(model_or_iterable, '__iter__') else [model_or_iterable]
        for model in models:
            model_admin = self._registry.get(model)
            if model_admin and not getattr(model_admin, '_role_perms_patched', False):
                self._patch_role_perms(model_admin)

    def _patch_role_perms(self, model_admin):
        """ModelAdminにrole-basedのpermissionチェックを注入（既存の独自permissionは優先）"""
        # 既に独自のpermissionメソッドを持つ場合はスキップ
        cls = type(model_admin)
        has_custom_perms = any(
            name in cls.__dict__
            for name in ('has_view_permission', 'has_change_permission',
                         'has_add_permission', 'has_delete_permission',
                         'has_module_permission')
        )
        if has_custom_perms:
            model_admin._role_perms_patched = True
            return

        role_perms = self._ROLE_PERMS
        model_name = model_admin.model._meta.object_name.lower()

        def _is_allowed_model(role):
            """DEFAULT_ALLOWED_MODELSでそのロールにモデルが許可されているか"""
            allowed = _get_allowed_models_for_role(role)
            if allowed is None:
                return True  # None = 全モデル許可
            return model_name in allowed

        def patched_has_module_permission(self_ma, request):
            if request.user.is_superuser:
                return True
            role = get_user_role(request)
            perms = role_perms.get(role)
            return perms is not None and _is_allowed_model(role)

        def patched_has_view_permission(self_ma, request, obj=None):
            if request.user.is_superuser:
                return True
            role = get_user_role(request)
            perms = role_perms.get(role)
            return perms is not None and perms.get('view', False) and _is_allowed_model(role)

        def patched_has_add_permission(self_ma, request):
            if request.user.is_superuser:
                return True
            role = get_user_role(request)
            perms = role_perms.get(role)
            return perms is not None and perms.get('add', False) and _is_allowed_model(role)

        def patched_has_change_permission(self_ma, request, obj=None):
            if request.user.is_superuser:
                return True
            role = get_user_role(request)
            perms = role_perms.get(role)
            return perms is not None and perms.get('change', False) and _is_allowed_model(role)

        def patched_has_delete_permission(self_ma, request, obj=None):
            if request.user.is_superuser:
                return True
            role = get_user_role(request)
            perms = role_perms.get(role)
            return perms is not None and perms.get('delete', False) and _is_allowed_model(role)

        import types
        model_admin.has_module_permission = types.MethodType(patched_has_module_permission, model_admin)
        model_admin.has_view_permission = types.MethodType(patched_has_view_permission, model_admin)
        model_admin.has_add_permission = types.MethodType(patched_has_add_permission, model_admin)
        model_admin.has_change_permission = types.MethodType(patched_has_change_permission, model_admin)
        model_admin.has_delete_permission = types.MethodType(patched_has_delete_permission, model_admin)
        model_admin._role_perms_patched = True

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
            return self._regroup_apps(raw, role=role, request=request)

        # 未認証 / Staff なしユーザー
        if role == 'none':
            return []

        # role-based ユーザー (developer/owner/manager/staff):
        # Django の権限システムを迂回し、レジストリから全モデルを取得。
        # 表示制御は独自のロールベースフィルタで行う。
        raw = self._build_full_app_list(app_label, role=role)

        allowed = _get_allowed_models_for_role(role)

        # None = 全モデル表示（developer / owner のデフォルト）
        if allowed is None:
            return self._regroup_apps(raw, role=role, request=request)

        # リストでフィルタ
        filtered = []
        for app in raw:
            models = [m for m in app['models'] if m['object_name'].lower() in allowed]
            if models:
                app_copy = app.copy()
                app_copy['models'] = models
                filtered.append(app_copy)

        return self._regroup_apps(filtered, role=role, request=request)

    # Role-based permission mapping for admin sidebar display.
    # staff: view only. manager: add/change/view. owner/developer: all.
    _ROLE_PERMS = {
        'staff':     {'add': False, 'change': False, 'delete': False, 'view': True},
        'manager':   {'add': True,  'change': True,  'delete': False, 'view': True},
        'owner':     {'add': True,  'change': True,  'delete': True,  'view': True},
        'developer': {'add': True,  'change': True,  'delete': True,  'view': True},
    }

    def _build_full_app_list(self, app_label=None, role=None):
        """レジストリから全モデルのリストを構築（Django の権限チェックを迂回）"""
        perms = self._ROLE_PERMS.get(role, {'add': False, 'change': False, 'delete': False, 'view': True})
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
                'perms': perms.copy(),
                'admin_url': reverse('%s:%s_%s_changelist' % info),
                'add_url': reverse('%s:%s_%s_add' % info),
                'view_only': not perms.get('change', False),
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

    def _regroup_apps(self, raw_app_list, role=None, request=None):
        """フラットなモデルリストを仮想アプリグループに再構成（slug ベース）"""
        # 全モデルをフラットに収集
        all_models = {}
        for app in raw_app_list:
            for model in app.get('models', []):
                key = model['object_name'].lower()
                all_models[key] = model

        # EC有効判定
        try:
            from .models import SystemConfig
            ec_enabled = SystemConfig.get('ec_enabled', '')
        except Exception:
            ec_enabled = ''

        # SiteSettings サイドバー表示フラグ
        try:
            from .models import SiteSettings
            site_cfg = SiteSettings.load()
            sidebar_flags = {
                'reservation': site_cfg.show_admin_reservation,
                'shift': site_cfg.show_admin_shift,
                'staff_manage': site_cfg.show_admin_staff_manage,
                'menu_manage': site_cfg.show_admin_menu_manage,
                'inventory': site_cfg.show_admin_inventory,
                'order': site_cfg.show_admin_order,
                'pos': site_cfg.show_admin_pos,
                'kitchen': site_cfg.show_admin_kitchen,
                'ec_shop': site_cfg.show_admin_ec_shop,
                'table_order': site_cfg.show_admin_table_order,
                'iot': site_cfg.show_admin_iot,
            }
        except Exception:
            sidebar_flags = {}

        # ロール別グループフィルタ
        visible_groups = ROLE_VISIBLE_GROUPS.get(role)

        # Per-staff 動的グループ拡張（在庫/注文表示制御）
        if role == 'staff' and visible_groups is not None and request is not None:
            try:
                staff = request.user.staff
                extra = []
                if staff.can_see_inventory:
                    extra.append('inventory')
                if staff.can_see_orders:
                    extra.append('order')
                if extra:
                    visible_groups = list(visible_groups) + extra
            except (Staff.DoesNotExist, AttributeError):
                pass

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
            # ロール別グループフィルタ: visible_groups が指定されていれば制限
            if visible_groups is not None and slug not in visible_groups:
                used_keys.update(k for k in model_keys if k in all_models)
                continue
            # EC未有効時はスキップ
            if slug == 'ec_shop' and not ec_enabled:
                continue
            # SiteSettings トグルでサイドバー非表示
            if slug in sidebar_flags and not sidebar_flags[slug]:
                continue
            hidden_in_group = set(g.get('hidden_models', []))
            group_models = []
            for key in model_keys:
                if key in all_models:
                    used_keys.add(key)
                    if key not in hidden_in_group:
                        group_models.append(all_models[key])
            # カスタムリンクをモデルエントリとして追加（ロール別がある場合は優先）
            role_links = SIDEBAR_CUSTOM_LINKS_BY_ROLE.get(slug, {})
            if role and role in role_links:
                custom_links = role_links[role]
            else:
                custom_links = SIDEBAR_CUSTOM_LINKS.get(slug, [])
            for link in custom_links:
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
