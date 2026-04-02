"""CMS admin: Notice, Company, Media, SiteSettings, AdminSidebar,
HomepageCustomBlock, HeroBanner, BannerAd, ExternalLink, AdminMenuConfig,
SecurityAudit, SecurityLog, CostReport, POSTransaction, VisitorCount,
VisitorAnalyticsConfig, StaffRecommendationModel, StaffRecommendationResult,
BusinessInsight, CustomerFeedback, EvaluationCriteria, StaffEvaluation."""
import json

from django import forms
from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from ..admin_site import custom_site
from ..models import (
    Staff,
    Company, Notice, Media,
    SiteSettings, AdminSidebarSettings,
    HomepageCustomBlock, HeroBanner, BannerAd, ExternalLink,
    AdminMenuConfig,
    SecurityAudit, SecurityLog, CostReport,
    POSTransaction,
    VisitorCount, VisitorAnalyticsConfig,
    StaffRecommendationModel, StaffRecommendationResult,
    BusinessInsight, CustomerFeedback,
    EvaluationCriteria, StaffEvaluation,
    ErrorReport,
)
from .helpers import _is_owner_or_super


# ==============================
# お知らせ / 会社 / メディア
# ==============================
class TinyMCEWidget(forms.Textarea):
    """TinyMCE CDN を読み込むカスタムウィジェット"""
    class Media:
        js = ('https://cdnjs.cloudflare.com/ajax/libs/tinymce/6.8.2/tinymce.min.js',)

    def __init__(self, attrs=None):
        default_attrs = {'class': 'tinymce-editor', 'rows': 20, 'cols': 80}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    template_name = 'django/forms/widgets/textarea.html'


class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_published', 'updated_at', 'link')
    list_filter = ('is_published',)
    list_editable = ('is_published',)
    search_fields = ('title', 'content', 'link')
    date_hierarchy = 'updated_at'
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'is_published', 'thumbnail')}),
        (_('本文'), {'fields': ('content',)}),
        (_('外部リンク'), {'fields': ('link',), 'classes': ('collapse',)}),
        (_('日時'), {'fields': ('created_at',)}),
    )

    formfield_overrides = {
        models.TextField: {'widget': TinyMCEWidget},
    }

    class Media:
        js = ('admin/js/tinymce_init.js',)
        css = {'all': ('admin/css/tinymce_admin.css',)}


class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'tel')
    search_fields = ('name', 'address', 'tel')


class MediaAdmin(admin.ModelAdmin):
    list_display = ('link', 'title', 'created_at')
    search_fields = ('title', 'link')
    date_hierarchy = 'created_at'


# ==============================
# ページ設定 (CMS)
# ==============================
class SiteSettingsAdmin(admin.ModelAdmin):
    """シングルトン設定 — 一覧は常にpk=1へリダイレクト"""
    change_form_template = 'admin/booking/sitesettings/change_form.html'
    save_on_top = True

    fieldsets = (
        (_('基本設定'), {'fields': ('site_name', 'staff_label', 'staff_label_i18n', 'price_label')}),
        (_('ホームページカード表示'), {'fields': (
            'show_card_store', 'show_card_fortune_teller',
            'show_card_calendar', 'show_card_shop',
        )}),
        (_('ヒーローバナー / ランキング'), {'fields': (
            'show_hero_banner', 'show_ranking', 'ranking_limit',
        )}),
        (_('サイドバー表示'), {
            'fields': (
                'show_sidebar_notice', 'show_sidebar_company',
                'show_sidebar_media', 'show_sidebar_social',
                'show_sidebar_external_links',
                'sidebar_order',
            ),
            'description': _('並び順はセクションキーのリスト: notice, company, sns, media, external_links（空の場合はデフォルト順）'),
        }),
        (_('SNS連携'), {'fields': ('twitter_url', 'instagram_url', 'threads_url', 'tiktok_url', 'instagram_embed_html')}),
        (_('法定ページ'), {
            'fields': ('privacy_policy_html', 'tokushoho_html'),
            'description': _('HTMLで記述できます。空の場合はデフォルトの内容が表示されます。'),
        }),
        (_('通知設定'), {
            'fields': (
                'notification_enabled', 'notification_emails',
                'notification_rate_limit',
                'shanon_notification_enabled', 'shanon_api_url',
            ),
            'description': _('エラー報告やセキュリティイベント発生時のメール・SHANON通知設定'),
        }),
        (_('メンテナンスモード'), {
            'fields': ('maintenance_mode', 'maintenance_message'),
            'description': _('ONにするとログイン済みスタッフ以外にメンテナンス画面を表示します'),
        }),
        (_('外部埋め込み'), {
            'fields': ('embed_enabled',),
            'description': _('WordPress等の外部サイトからiframeで予約カレンダー・シフト表示を埋め込む機能'),
            'classes': ('collapse',),
        }),
    )

    def has_view_permission(self, request, obj=None):
        if _is_owner_or_super(request):
            return True
        try:
            return request.user.staff.is_store_manager or request.user.staff.is_developer
        except Staff.DoesNotExist:
            return False

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        from django.shortcuts import redirect
        return redirect(f'/admin/booking/sitesettings/{obj.pk}/change/')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        sub_models = [
            {'name': '運営会社', 'model': Company, 'key': 'company'},
            {'name': 'お知らせ', 'model': Notice, 'key': 'notice'},
            {'name': 'メディア掲載', 'model': Media, 'key': 'media'},
            {'name': 'カスタムブロック', 'model': HomepageCustomBlock, 'key': 'homepagecustomblock'},
            {'name': 'ヒーローバナー', 'model': HeroBanner, 'key': 'herobanner'},
            {'name': 'バナー広告', 'model': BannerAd, 'key': 'bannerad'},
            {'name': '外部リンク', 'model': ExternalLink, 'key': 'externallink'},
        ]
        sub_model_tabs = []
        for sm in sub_models:
            model = sm['model']
            meta = model._meta
            sub_model_tabs.append({
                'name': sm['name'],
                'count': model.objects.count(),
                'changelist_url': f'/admin/{meta.app_label}/{meta.model_name}/',
                'add_url': f'/admin/{meta.app_label}/{meta.model_name}/add/',
            })
        extra_context['sub_model_tabs'] = sub_model_tabs
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if change and 'maintenance_mode' in form.changed_data:
            event_type = 'maintenance_on' if obj.maintenance_mode else 'maintenance_off'
            detail = 'メンテナンスモードON（管理画面）' if obj.maintenance_mode else 'メンテナンスモードOFF（管理画面）'
            SecurityLog.objects.create(
                event_type=event_type,
                severity='info',
                user=request.user,
                username=request.user.username,
                ip_address=request.META.get('REMOTE_ADDR', ''),
                path=request.path,
                method='POST',
                detail=detail,
            )
        super().save_model(request, obj, form, change)


class AdminSidebarSettingsAdmin(admin.ModelAdmin):
    """管理画面サイドバー設定 — スーパーアカウントのみ編集可能"""

    fieldsets = (
        (_('管理サイドバー機能ON/OFF'), {
            'fields': (
                'show_admin_reservation', 'show_admin_shift', 'show_admin_staff_manage',
                'show_admin_menu_manage', 'show_admin_inventory',
                'show_admin_order', 'show_admin_pos', 'show_admin_kitchen',
                'show_admin_ec_shop', 'show_admin_table_order', 'show_admin_iot',
                'show_admin_pin_clock', 'show_admin_page_settings', 'show_admin_system',
                'show_admin_sns_posting', 'show_admin_security', 'show_admin_user_account',
            ),
            'description': _('管理画面サイドバーに表示する機能を選択します。業態に合わせて使わない機能はOFFにして非表示にできます。'),
        }),
    )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        from django.shortcuts import redirect
        return redirect(f'/admin/booking/adminsidebarsettings/{obj.pk}/change/')


class HomepageCustomBlockAdmin(admin.ModelAdmin):
    list_display = ('title', 'position', 'sort_order', 'is_active', 'updated_at')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('title',)


class HeroBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'sort_order', 'is_active', 'image_position', 'link_type', 'updated_at')
    list_editable = ('sort_order', 'is_active', 'image_position', 'link_type')
    search_fields = ('title',)
    fieldsets = (
        (None, {'fields': ('title', 'image', 'image_position', 'sort_order', 'is_active')}),
        (_('リンク設定'), {'fields': ('link_type', 'linked_store', 'linked_staff', 'link_url')}),
    )


class BannerAdAdmin(admin.ModelAdmin):
    list_display = ('title', 'position', 'sort_order', 'is_active', 'link_url', 'updated_at')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('title',)


class ExternalLinkAdmin(admin.ModelAdmin):
    list_display = ('title', 'url', 'sort_order', 'is_active', 'open_in_new_tab')
    list_editable = ('sort_order', 'is_active', 'open_in_new_tab')
    search_fields = ('title', 'url')


# ==============================
# メニュー権限設定 (superuser のみ)
# ==============================
from ..forms import AdminMenuConfigForm
from ..admin_site import GROUP_MAP, invalidate_menu_config_cache


class AdminMenuConfigAdmin(admin.ModelAdmin):
    form = AdminMenuConfigForm
    list_display = ('role', 'get_role_display', 'model_count', 'updated_at', 'updated_by')
    readonly_fields = ('updated_at', 'updated_by')
    change_form_template = 'admin/booking/adminmenuconfig/change_form.html'

    def get_role_display(self, obj):
        return obj.get_role_display()
    get_role_display.short_description = _('ロール名')

    def model_count(self, obj):
        if isinstance(obj.allowed_models, list):
            return len(obj.allowed_models)
        return 0
    model_count.short_description = _('許可モデル数')

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        obj.allowed_models = form.cleaned_data.get('allowed_models', [])
        super().save_model(request, obj, form, change)
        invalidate_menu_config_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        invalidate_menu_config_cache()

    def _get_group_map_json(self):
        from ..admin_site import GROUPS
        result = {str(g['name']): g['models'] for g in GROUPS}
        return json.dumps(result, ensure_ascii=False)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['group_map_json'] = self._get_group_map_json()
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['group_map_json'] = self._get_group_map_json()
        return super().add_view(request, form_url, extra_context)


# ==============================
# セキュリティ監査・監視ログ・AWSコスト
# ==============================
class SecurityAuditAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'severity', 'status', 'check_name', 'category', 'message')
    list_filter = ('severity', 'status', 'category')
    search_fields = ('check_name', 'message')
    readonly_fields = ('run_id', 'check_name', 'category', 'severity', 'status', 'message', 'recommendation', 'created_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    actions = ['run_security_audit']

    @admin.action(description=_('セキュリティ監査を実行'))
    def run_security_audit(self, request, queryset):
        from django.core.management import call_command
        call_command('security_audit')
        self.message_user(request, 'セキュリティ監査を実行しました。ページを更新して結果を確認してください。')


class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'event_type', 'severity', 'username', 'ip_address', 'path')
    list_filter = ('event_type', 'severity')
    search_fields = ('username', 'ip_address', 'path', 'detail')
    readonly_fields = ('event_type', 'severity', 'user', 'username', 'ip_address', 'user_agent', 'path', 'method', 'detail', 'created_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class CostReportAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'status', 'check_name', 'resource_type', 'estimated_monthly_cost')
    list_filter = ('status', 'resource_type')
    search_fields = ('check_name', 'resource_id', 'detail')
    readonly_fields = ('run_id', 'check_name', 'resource_type', 'resource_id', 'status', 'estimated_monthly_cost', 'detail', 'recommendation', 'created_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    actions = ['run_aws_cost_check']

    @admin.action(description=_('AWSコストチェックを実行'))
    def run_aws_cost_check(self, request, queryset):
        from django.core.management import call_command
        call_command('check_aws_costs')
        self.message_user(request, 'AWSコストチェックを実行しました。ページを更新して結果を確認してください。')


# ==============================
# POS決済
# ==============================
class POSTransactionAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'order', 'total_amount', 'payment_method', 'staff', 'completed_at', 'receipt_link')
    search_fields = ('receipt_number',)
    readonly_fields = ('completed_at',)
    date_hierarchy = 'completed_at'

    def receipt_link(self, obj):
        url = f'/admin/pos/receipt/{obj.receipt_number}/'
        return format_html('<a href="{}" target="_blank">レシート</a>', url)
    receipt_link.short_description = _('レシート')


# ==============================
# 来客分析
# ==============================
class VisitorCountAdmin(admin.ModelAdmin):
    list_display = ('store', 'date', 'hour', 'estimated_visitors', 'order_count', 'pir_count')
    list_filter = ('store',)
    date_hierarchy = 'date'


class VisitorAnalyticsConfigAdmin(admin.ModelAdmin):
    list_display = ('store', 'session_gap_seconds', 'pir_device')


# ==============================
# AI推薦
# ==============================
class StaffRecommendationModelAdmin(admin.ModelAdmin):
    list_display = ('store', 'model_type', 'mae_score', 'training_samples', 'trained_at', 'is_active')
    list_filter = ('is_active', 'model_type')
    readonly_fields = ('trained_at',)


class StaffRecommendationResultAdmin(admin.ModelAdmin):
    list_display = ('store', 'date', 'hour', 'recommended_staff_count', 'confidence')
    list_filter = ('store',)
    date_hierarchy = 'date'


# ==============================
# ビジネスインサイト
# ==============================
class BusinessInsightAdmin(admin.ModelAdmin):
    list_display = ('severity', 'category', 'title', 'store', 'is_read', 'created_at')
    list_filter = ('severity', 'category', 'is_read', 'store')
    search_fields = ('title', 'message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 50


class CustomerFeedbackAdmin(admin.ModelAdmin):
    list_display = ('store', 'nps_score', 'food_rating', 'service_rating', 'ambiance_rating', 'sentiment', 'created_at')
    list_filter = ('store', 'sentiment', 'nps_score')
    search_fields = ('comment',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 50


# ==============================
# スタッフ評価
# ==============================
class EvaluationCriteriaAdmin(admin.ModelAdmin):
    list_display = ('store', 'name', 'category', 'weight', 'is_auto', 'is_active', 'sort_order')
    list_editable = ('sort_order', 'is_active', 'weight')
    list_filter = ('store', 'category', 'is_auto', 'is_active')
    search_fields = ('name',)


class StaffEvaluationAdmin(admin.ModelAdmin):
    list_display = (
        'staff', 'period_start', 'period_end',
        'attendance_rate', 'punctuality_score', 'overall_score',
        'grade', 'source', 'is_published',
    )
    list_filter = ('grade', 'source', 'is_published', 'staff__store')
    search_fields = ('staff__name', 'comment')
    readonly_fields = (
        'attendance_rate', 'punctuality_score', 'total_work_hours',
        'created_at', 'updated_at',
    )
    date_hierarchy = 'period_end'
    save_on_top = True

    fieldsets = (
        (None, {'fields': ('staff', 'evaluator', 'period_start', 'period_end')}),
        (_('自動評価（勤怠データより）'), {
            'fields': ('attendance_rate', 'punctuality_score', 'total_work_hours'),
        }),
        (_('手動評価'), {
            'fields': ('scores', 'comment'),
        }),
        (_('総合'), {
            'fields': ('overall_score', 'grade', 'source'),
        }),
        (_('スタッフコメント'), {
            'fields': ('staff_comment',),
        }),
        (_('公開設定'), {
            'fields': ('is_published', 'created_at', 'updated_at'),
        }),
    )

    actions = ['auto_evaluate', 'publish_evaluations']

    def auto_evaluate(self, request, queryset):
        """選択した評価の自動評価フィールドを更新"""
        from ..services.staff_evaluation import (
            calculate_attendance_rate, calculate_punctuality_score,
            calculate_total_work_hours,
        )
        updated = 0
        for ev in queryset:
            ev.attendance_rate = calculate_attendance_rate(
                ev.staff, ev.period_start, ev.period_end)
            ev.punctuality_score = calculate_punctuality_score(
                ev.staff, ev.period_start, ev.period_end)
            ev.total_work_hours = calculate_total_work_hours(
                ev.staff, ev.period_start, ev.period_end)
            # 総合スコア再計算
            parts = []
            if ev.attendance_rate is not None:
                parts.append(min(ev.attendance_rate / 100.0, 1.0) * 5.0 * 0.5)
            if ev.punctuality_score is not None:
                parts.append(ev.punctuality_score * 0.5)
            if parts:
                ev.overall_score = round(sum(parts) / (len(parts) * 0.5), 1)
                ev.grade = ev.calculate_grade()
            ev.source = 'auto' if not ev.scores else 'mixed'
            ev.save()
            updated += 1
        self.message_user(request, f'{updated}件の自動評価を更新しました。')

    auto_evaluate.short_description = _('自動評価を実行')

    def publish_evaluations(self, request, queryset):
        """選択した評価を公開"""
        count = queryset.update(is_published=True)
        self.message_user(request, f'{count}件を公開しました。')

    publish_evaluations.short_description = _('選択した評価を公開')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        try:
            staff = request.user.staff
            if staff.is_store_manager or staff.is_owner or staff.is_developer:
                return qs.filter(staff__store=staff.store)
            return qs.filter(staff=staff, is_published=True)
        except Staff.DoesNotExist:
            return qs.none()


# ==============================
# エラー報告
# ==============================
class ErrorReportAdmin(admin.ModelAdmin):
    list_display = ('severity', 'title', 'status', 'reporter', 'assigned_to', 'created_at')
    list_filter = ('severity', 'status')
    search_fields = ('title', 'description')
    readonly_fields = ('reporter', 'created_at', 'updated_at', 'resolved_at')
    date_hierarchy = 'created_at'
    list_per_page = 50

    fieldsets = (
        (None, {'fields': ('title', 'description', 'severity', 'status')}),
        (_('再現情報'), {
            'fields': ('steps_to_reproduce', 'page_url', 'browser_info', 'screenshot'),
            'classes': ('collapse',),
        }),
        (_('対応'), {
            'fields': ('assigned_to', 'resolution_note', 'resolved_at'),
        }),
        (_('メタ情報'), {
            'fields': ('reporter', 'created_at', 'updated_at'),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.reporter = request.user
        if obj.status == 'resolved' and not obj.resolved_at:
            from django.utils import timezone
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)
        # Trigger notification for new error reports
        if not change:
            try:
                from booking.tasks import send_event_notification
                admin_url = f'/admin/booking/errorreport/{obj.pk}/change/'
                send_event_notification.delay(
                    'error_report', obj.severity, obj.title,
                    obj.description[:500], admin_url,
                )
            except Exception:
                pass


# Registration
custom_site.register(Notice, NoticeAdmin)
custom_site.register(Company, CompanyAdmin)
custom_site.register(Media, MediaAdmin)
custom_site.register(SiteSettings, SiteSettingsAdmin)
custom_site.register(AdminSidebarSettings, AdminSidebarSettingsAdmin)
custom_site.register(HomepageCustomBlock, HomepageCustomBlockAdmin)
custom_site.register(HeroBanner, HeroBannerAdmin)
custom_site.register(BannerAd, BannerAdAdmin)
custom_site.register(ExternalLink, ExternalLinkAdmin)
custom_site.register(AdminMenuConfig, AdminMenuConfigAdmin)
custom_site.register(SecurityAudit, SecurityAuditAdmin)
custom_site.register(SecurityLog, SecurityLogAdmin)
custom_site.register(CostReport, CostReportAdmin)
custom_site.register(POSTransaction, POSTransactionAdmin)
custom_site.register(VisitorCount, VisitorCountAdmin)
custom_site.register(VisitorAnalyticsConfig, VisitorAnalyticsConfigAdmin)
custom_site.register(StaffRecommendationModel, StaffRecommendationModelAdmin)
custom_site.register(StaffRecommendationResult, StaffRecommendationResultAdmin)
custom_site.register(BusinessInsight, BusinessInsightAdmin)
custom_site.register(CustomerFeedback, CustomerFeedbackAdmin)
custom_site.register(EvaluationCriteria, EvaluationCriteriaAdmin)
custom_site.register(StaffEvaluation, StaffEvaluationAdmin)
custom_site.register(ErrorReport, ErrorReportAdmin)
