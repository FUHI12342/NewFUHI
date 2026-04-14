"""SNS自動投稿 Django Admin 登録"""
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from ..admin_site import custom_site
from ..models import SocialAccount, PostTemplate, PostHistory, KnowledgeEntry, DraftPost


class SocialAccountAdmin(admin.ModelAdmin):
    list_display = (
        'store', 'platform', 'account_name',
        'is_active', 'token_status', 'updated_at',
    )
    list_filter = ('is_active', 'platform', 'store')
    list_editable = ('is_active',)
    search_fields = ('account_name', 'store__name')
    readonly_fields = ('created_at', 'updated_at', 'token_expires_at')
    list_per_page = 10
    ordering = ('store', 'platform')

    fieldsets = (
        (None, {
            'fields': ('store', 'platform', 'account_name', 'is_active'),
        }),
        (_('トークン情報'), {
            'fields': ('token_expires_at', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def token_status(self, obj):
        """トークン有効期限の状態表示"""
        from django.utils import timezone
        if not obj.token_expires_at:
            return format_html('<span style="color:gray;">未設定</span>')
        if obj.token_expires_at < timezone.now():
            return format_html('<span style="color:red;">期限切れ</span>')
        return format_html('<span style="color:green;">有効</span>')
    token_status.short_description = _('トークン状態')
    token_status.admin_order_field = 'token_expires_at'


class PostTemplateAdmin(admin.ModelAdmin):
    list_display = ('store', 'trigger_type', 'platform', 'is_active', 'updated_at')
    list_filter = ('trigger_type', 'platform', 'is_active', 'store')
    list_editable = ('is_active',)
    search_fields = ('store__name', 'body_template')
    list_per_page = 10
    ordering = ('store', 'trigger_type')

    fieldsets = (
        (None, {
            'fields': ('store', 'platform', 'trigger_type', 'is_active'),
        }),
        (_('テンプレート'), {
            'fields': ('body_template',),
            'description': _(
                '変数: {store_name}, {date}, {staff_list}, '
                '{business_hours}, {month}'
            ),
        }),
    )


class PostHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'store', 'trigger_type', 'status_badge',
        'retry_count', 'created_at', 'posted_at',
    )
    list_filter = ('status', 'trigger_type', 'platform', 'store')
    search_fields = ('store__name', 'content', 'external_post_id')
    readonly_fields = (
        'store', 'platform', 'trigger_type', 'content',
        'status', 'external_post_id', 'error_message',
        'retry_count', 'created_at', 'posted_at',
    )
    ordering = ('-created_at',)
    list_per_page = 10
    actions = ['retry_failed_posts']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'posted': 'green',
            'failed': 'red',
            'skipped': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = _('ステータス')
    status_badge.admin_order_field = 'status'

    @admin.action(description=_('失敗した投稿をリトライ'))
    def retry_failed_posts(self, request, queryset):
        from booking.services.post_dispatcher import retry_failed_post
        retried = 0
        for history in queryset.filter(status='failed'):
            retry_failed_post(history.id)
            retried += 1
        self.message_user(request, f'{retried}件のリトライを実行しました。')


class KnowledgeEntryAdmin(admin.ModelAdmin):
    list_display = ('store', 'category', 'title', 'staff', 'is_active', 'updated_at')
    list_filter = ('category', 'is_active', 'store')
    list_editable = ('is_active',)
    search_fields = ('title', 'content', 'store__name')
    list_per_page = 10
    ordering = ('store', 'category', 'title')
    actions = ['generate_from_staff']

    fieldsets = (
        (None, {'fields': ('store', 'category', 'staff', 'title', 'is_active')}),
        (_('内容'), {'fields': ('content',)}),
    )

    @admin.action(description=_('Staffから自動生成'))
    def generate_from_staff(self, request, queryset):
        """選択した KnowledgeEntry の store から Staff 情報を一括生成"""
        from ..models import Staff
        created = 0
        stores_done = set()
        for entry in queryset:
            if entry.store_id in stores_done:
                continue
            stores_done.add(entry.store_id)
            staffs = Staff.objects.filter(
                store=entry.store, staff_type='fortune_teller',
            )
            for staff in staffs:
                _, was_created = KnowledgeEntry.objects.get_or_create(
                    store=entry.store,
                    category='cast_profile',
                    staff=staff,
                    defaults={
                        'title': f'{staff.name}プロフィール',
                        'content': f'名前: {staff.name}\n紹介: {staff.introduction or "未設定"}',
                    },
                )
                if was_created:
                    created += 1
        self.message_user(request, _(f'{created}件のナレッジを自動生成しました。'), messages.SUCCESS)


class DraftPostAdmin(admin.ModelAdmin):
    list_display = ('store', 'status_badge', 'quality_display', 'platform_display',
                    'has_image', 'target_date', 'content_preview', 'created_at')
    list_filter = ('status', 'store')
    search_fields = ('content', 'store__name')
    readonly_fields = ('ai_generated_content', 'quality_score', 'quality_feedback',
                       'image_preview', 'posted_at', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    list_per_page = 10
    actions = ['generate_draft_action', 'post_now_action']

    fieldsets = (
        (None, {
            'fields': ('store', 'status', 'platforms', 'target_date', 'scheduled_at'),
        }),
        (_('投稿内容'), {
            'fields': ('content', 'image', 'image_preview'),
        }),
        (_('AI生成情報'), {
            'fields': ('ai_generated_content', 'quality_score', 'quality_feedback'),
            'classes': ('collapse',),
        }),
        (_('メタ情報'), {
            'fields': ('created_by', 'posted_at', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'generated': 'blue', 'reviewed': 'orange', 'approved': 'green',
            'rejected': 'red', 'posted': 'gray', 'scheduled': '#f59e0b',
        }
        color = colors.get(obj.status, 'gray')
        return format_html('<span style="color:{}; font-weight:bold;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = _('ステータス')
    status_badge.admin_order_field = 'status'

    def quality_display(self, obj):
        if obj.quality_score is None:
            return '-'
        if obj.quality_score >= 0.7:
            color = 'green'
        elif obj.quality_score >= 0.4:
            color = 'orange'
        else:
            color = 'red'
        pct = f'{obj.quality_score:.0%}'
        return format_html('<span style="color:{};">{}</span>', color, pct)
    quality_display.short_description = _('品質')
    quality_display.admin_order_field = 'quality_score'

    def platform_display(self, obj):
        platforms = obj.platforms or []
        if not isinstance(platforms, list):
            return str(platforms)
        return ', '.join(str(p) for p in platforms) if platforms else '-'
    platform_display.short_description = _('プラットフォーム')

    def has_image(self, obj):
        if obj.image:
            return format_html('<span style="color:green;">&#10003;</span>')
        return format_html('<span style="color:gray;">-</span>')
    has_image.short_description = _('画像')
    has_image.admin_order_field = 'image'

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:200px; border-radius:8px;" />',
                obj.image.url,
            )
        return _('画像なし')
    image_preview.short_description = _('画像プレビュー')

    def content_preview(self, obj):
        content = obj.content or ''
        return content[:60] + '...' if len(content) > 60 else content
    content_preview.short_description = _('内容')
    content_preview.admin_order_field = 'content'

    @admin.action(description=_('AI下書きを生成'))
    def generate_draft_action(self, request, queryset):
        from booking.services.sns_draft_service import generate_daily_draft
        generated = 0
        for draft in queryset:
            result = generate_daily_draft(draft.store, target_date=draft.target_date)
            if result:
                generated += 1
        self.message_user(request, _('%(count)d件の下書きを生成しました。') % {'count': generated})

    @admin.action(description=_('即時投稿'))
    def post_now_action(self, request, queryset):
        from booking.services.post_dispatcher import dispatch_post
        posted = 0
        for draft in queryset.filter(status__in=['generated', 'approved']):
            for platform in (draft.platforms or ['x']):
                result = dispatch_post(draft, platform)
                if result:
                    posted += 1
        self.message_user(request, _('%(count)d件を投稿しました。') % {'count': posted})


custom_site.register(SocialAccount, SocialAccountAdmin)
custom_site.register(PostTemplate, PostTemplateAdmin)
custom_site.register(PostHistory, PostHistoryAdmin)
custom_site.register(KnowledgeEntry, KnowledgeEntryAdmin)
custom_site.register(DraftPost, DraftPostAdmin)
