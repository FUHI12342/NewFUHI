from django.db import migrations, models


def set_default_visibility(apps, schema_editor):
    """shift + reservation のみ表示、他は全 False"""
    SiteSettings = apps.get_model('booking', 'SiteSettings')
    for ss in SiteSettings.objects.all():
        # 既存11フィールド: shift と reservation のみ True、他は False
        ss.show_admin_staff_manage = False
        ss.show_admin_menu_manage = False
        ss.show_admin_inventory = False
        ss.show_admin_order = False
        ss.show_admin_pos = False
        ss.show_admin_kitchen = False
        ss.show_admin_ec_shop = False
        ss.show_admin_table_order = False
        ss.show_admin_iot = False
        # 新規6フィールド: 全 False
        ss.show_admin_pin_clock = False
        ss.show_admin_page_settings = False
        ss.show_admin_system = False
        ss.show_admin_sns_posting = False
        ss.show_admin_security = False
        ss.show_admin_user_account = False
        ss.save()


def reverse_visibility(apps, schema_editor):
    """Reverse: 全て True に戻す"""
    SiteSettings = apps.get_model('booking', 'SiteSettings')
    for ss in SiteSettings.objects.all():
        ss.show_admin_staff_manage = True
        ss.show_admin_menu_manage = True
        ss.show_admin_inventory = True
        ss.show_admin_order = True
        ss.show_admin_pos = True
        ss.show_admin_kitchen = True
        ss.show_admin_ec_shop = True
        ss.show_admin_table_order = True
        ss.show_admin_iot = True
        ss.show_admin_pin_clock = True
        ss.show_admin_page_settings = True
        ss.show_admin_system = True
        ss.show_admin_sns_posting = True
        ss.show_admin_security = True
        ss.show_admin_user_account = True
        ss.save()


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0095_social_posting'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='show_admin_pin_clock',
            field=models.BooleanField(default=True, help_text='管理サイドバーに「タイムカード打刻」を表示するかどうか', verbose_name='タイムカードを表示'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='show_admin_page_settings',
            field=models.BooleanField(default=True, help_text='管理サイドバーに「メインページ設定」を表示するかどうか', verbose_name='ページ設定を表示'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='show_admin_system',
            field=models.BooleanField(default=True, help_text='管理サイドバーに「システム」を表示するかどうか', verbose_name='システムを表示'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='show_admin_sns_posting',
            field=models.BooleanField(default=True, help_text='管理サイドバーに「SNS自動投稿」を表示するかどうか', verbose_name='SNS投稿を表示'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='show_admin_security',
            field=models.BooleanField(default=True, help_text='管理サイドバーに「セキュリティ」を表示するかどうか', verbose_name='セキュリティを表示'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='show_admin_user_account',
            field=models.BooleanField(default=True, help_text='管理サイドバーに「ユーザーアカウント管理」を表示するかどうか', verbose_name='ユーザー管理を表示'),
        ),
        migrations.RunPython(set_default_visibility, reverse_visibility),
    ]
