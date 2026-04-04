"""Backup admin: BackupConfig (singleton), BackupHistory (read-only log)."""
from django.contrib import admin
from django.shortcuts import redirect
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from ..admin_site import custom_site
from ..models import BackupConfig, BackupHistory
from .helpers import _is_owner_or_super


class BackupConfigAdmin(admin.ModelAdmin):
    """バックアップ設定（シングルトン）"""
    fieldsets = (
        (_('スケジュール設定'), {
            'fields': ('interval', 'is_active'),
            'description': _('バックアップの実行間隔を設定します。「毎分」はテスト用、本番は「毎時」か「毎日」推奨'),
        }),
        (_('S3設定'), {
            'fields': ('s3_enabled', 's3_bucket', 's3_retention_days'),
        }),
        (_('ローカル保持'), {
            'fields': ('local_retention_count',),
        }),
        (_('オプション'), {
            'fields': ('exclude_demo_data', 'line_notify_enabled'),
        }),
    )

    def has_add_permission(self, request):
        return not BackupConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return _is_owner_or_super(request)

    def has_change_permission(self, request, obj=None):
        return _is_owner_or_super(request)

    def changelist_view(self, request, extra_context=None):
        obj = BackupConfig.load()
        return redirect(f'/admin/booking/backupconfig/{obj.pk}/change/')

    actions = ['run_manual_backup']

    @admin.action(description=_('手動バックアップを実行'))
    def run_manual_backup(self, request, queryset):
        from booking.services.backup_service import create_backup
        history = create_backup(trigger='manual')
        if history.status == 'success':
            size_kb = history.file_size_bytes / 1024
            self.message_user(
                request,
                f'バックアップ完了: {size_kb:.1f} KB ({history.duration_seconds:.1f}秒)',
            )
        else:
            self.message_user(
                request,
                f'バックアップ失敗: {history.error_message[:200]}',
                level='error',
            )


class BackupHistoryAdmin(admin.ModelAdmin):
    """バックアップ履歴（読み取り専用）"""
    list_display = (
        'started_at', 'status_badge', 'trigger', 'file_size_display',
        'duration_seconds', 's3_uploaded',
    )
    list_filter = ('status', 'trigger', 's3_uploaded')
    readonly_fields = (
        'backup_file', 'file_size_bytes', 'status', 'trigger',
        's3_uploaded', 's3_key', 'error_message',
        'duration_seconds', 'started_at', 'completed_at',
    )
    ordering = ('-started_at',)
    list_per_page = 20
    date_hierarchy = 'started_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return _is_owner_or_super(request)

    def status_badge(self, obj):
        colors = {
            'running': '#2196F3',
            'success': '#4CAF50',
            'failed': '#F44336',
        }
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="color:{}; font-weight:bold">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = _('ステータス')
    status_badge.admin_order_field = 'status'

    def file_size_display(self, obj):
        if obj.file_size_bytes == 0:
            return '-'
        kb = obj.file_size_bytes / 1024
        if kb >= 1024:
            return f'{kb / 1024:.1f} MB'
        return f'{kb:.1f} KB'
    file_size_display.short_description = _('サイズ')


custom_site.register(BackupConfig, BackupConfigAdmin)
custom_site.register(BackupHistory, BackupHistoryAdmin)
