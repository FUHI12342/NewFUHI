"""ブラウザ自動投稿 Admin"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import BrowserSession, BrowserPostLog

try:
    from booking.admin_site import custom_site
except ImportError:
    custom_site = admin.site


class BrowserSessionAdmin(admin.ModelAdmin):
    list_display = ('store', 'platform', 'status_badge', 'updated_at')
    list_filter = ('platform', 'status', 'store')
    readonly_fields = ('created_at', 'updated_at')

    def status_badge(self, obj):
        colors = {'active': 'green', 'expired': 'red', 'setup_required': 'orange'}
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = _('状態')


class BrowserPostLogAdmin(admin.ModelAdmin):
    list_display = ('session', 'success_badge', 'content_preview', 'created_at')
    list_filter = ('success', 'session__platform')
    readonly_fields = (
        'session', 'draft_post', 'content', 'success',
        'error_message', 'screenshot', 'created_at',
    )
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def success_badge(self, obj):
        if obj.success:
            return format_html('<span style="color:green;">成功</span>')
        return format_html('<span style="color:red;">失敗</span>')
    success_badge.short_description = _('結果')

    def content_preview(self, obj):
        return obj.content[:60] + '...' if len(obj.content) > 60 else obj.content
    content_preview.short_description = _('内容')


custom_site.register(BrowserSession, BrowserSessionAdmin)
custom_site.register(BrowserPostLog, BrowserPostLogAdmin)
