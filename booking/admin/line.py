"""LINE customer admin."""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from ..admin_site import custom_site
from ..models import LineCustomer, LineMessageLog


class LineCustomerAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'segment', 'store', 'visit_count', 'total_spent', 'is_friend', 'last_visit_at')
    list_filter = ('segment', 'is_friend', 'store')
    search_fields = ('display_name', 'line_user_hash')
    readonly_fields = ('line_user_hash', 'line_user_enc', 'first_visit_at', 'last_visit_at')
    list_per_page = 20
    ordering = ('-last_visit_at',)

    fieldsets = (
        (None, {'fields': ('display_name', 'line_user_hash', 'is_friend', 'store')}),
        (_('統計'), {'fields': ('visit_count', 'total_spent', 'segment', 'tags')}),
        (_('日時'), {'fields': ('first_visit_at', 'last_visit_at', 'blocked_at')}),
    )


class LineMessageLogAdmin(admin.ModelAdmin):
    list_display = ('sent_at', 'message_type', 'customer', 'content_preview', 'status')
    list_filter = ('message_type', 'status')
    search_fields = ('content_preview',)
    readonly_fields = ('customer', 'message_type', 'content_preview', 'sent_at', 'status', 'error_detail')
    list_per_page = 20
    ordering = ('-sent_at',)
    date_hierarchy = 'sent_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


custom_site.register(LineCustomer, LineCustomerAdmin)
custom_site.register(LineMessageLog, LineMessageLogAdmin)
