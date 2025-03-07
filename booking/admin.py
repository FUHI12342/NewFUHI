from django.contrib import admin
from .models import Staff, Store, Schedule, Company, Notice, Media
from django.utils.html import format_html
from social_django.models import Association, Nonce, UserSocialAuth
from django.urls import path
from django.utils.safestring import mark_safe
from django.shortcuts import render
""" Django 管理サイト名変更 """
admin.site.site_header = '占いサロンチャンス管理ページ'
admin.site.site_title = '占いサロンチャンス管理ページ'
from django.db.models import Count
from django.contrib import admin
from .models import Schedule
from django.urls import reverse
from django.utils.html import format_html

class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('hashed_id_link', 'customer_name', 'start', 'end', 'staff', 'is_temporary', 'price', 'memo','reservation_number' )
    search_fields = ('customer_name', 'reservation_number')  # 顧客名と予約番号で検索可能にする
    ordering = ('-start',)  # 新しい予約から表示

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('history/<str:hashed_id>/', self.admin_site.admin_view(self.view_history), name='schedule-history'),
        ]
        return custom_urls + urls

    def view_history(self, request, hashed_id):
        schedules = Schedule.objects.filter(hashed_id=hashed_id)
        context = dict(
            self.admin_site.each_context(request),
            schedules=schedules,
            hashed_id=hashed_id,
        )
        return render(request, 'admin/schedule_history.html', context)

    def hashed_id_link(self, obj):
        url = reverse('admin:schedule-history', args=[obj.hashed_id])
        return format_html('<a href="{}">{}</a>', url, obj.hashed_id[:10] if obj.hashed_id else "No ID")
    hashed_id_link.short_description = 'Hashed ID'  # 管理画面での列名

admin.site.register(Schedule, ScheduleAdmin)
# 管理画面のデフォルトページを予約スケジュールに設定
admin.site.index_template = 'admin/custom_index.html'

class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_thumbnail')  # 'name'と'display_thumbnail'を表示する

    def display_thumbnail(self, obj):
        return format_html('<img src="{}" width="50" height="50" />', obj.thumbnail.url)
    display_thumbnail.short_description = 'サムネイル'

    # フィールドのラベルを変更
    def formfield_for_dbfield(self, db_field, **kwargs):
        field = super().formfield_for_dbfield(db_field, **kwargs)
        if db_field.name == 'name':
            field.label = 'スタッフ名'
        return field

class SuperUserOnlyAdmin(admin.ModelAdmin):
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

# 自分のモデルだけを登録
admin.site.register(Staff, StaffAdmin)
admin.site.register(Store)

# Python Social Authのモデルを登録から除外
admin.site.unregister(Association)
admin.site.unregister(Nonce)
admin.site.unregister(UserSocialAuth)


class CustomAdminSite(admin.AdminSite):
    site_header = "カスタム管理サイト"
    site_title = "カスタム管理サイト"
    index_title = "ホーム"
    
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('<str:app_label>/', self.app_index, name='app_list'),
        ]
        return my_urls + urls

custom_site = CustomAdminSite(name='custom_admin')

class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'updated_at', 'link')  # 'content'を適切なフィールド名に変更 # 適切なフィールド名に変更してください

custom_site.register(Notice, NoticeAdmin)


class MediaAdmin(admin.ModelAdmin):
    list_display = ('link')  # display_thumbnailメソッドを追加
    exclude = ('title')  # titleフィールドを非表示にする
    def display_thumbnail(self, obj):
        return mark_safe('<img src="{}" width="50" height="50" />'.format(obj.thumbnail.url))
    display_thumbnail.short_description = 'Thumbnail'

admin.site.register(Media)


class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'tel')  # 適切なフィールド名に変更してください

custom_site.register(Company, CompanyAdmin)

admin.site.register(Notice)
#admin.site.register(Media)
admin.site.register(Company)