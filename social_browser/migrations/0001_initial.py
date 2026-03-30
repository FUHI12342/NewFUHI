import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('booking', '0098_sns_drafts_knowledge'),
    ]

    operations = [
        migrations.CreateModel(
            name='BrowserSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(choices=[('x', 'X (Twitter)'), ('instagram', 'Instagram'), ('gbp', 'Google Business Profile')], max_length=20, verbose_name='プラットフォーム')),
                ('profile_dir', models.CharField(help_text='MEDIA_ROOT/browser_profiles/<store>/<platform>/', max_length=500, verbose_name='プロファイルディレクトリ')),
                ('status', models.CharField(choices=[('active', '有効'), ('expired', '期限切れ'), ('setup_required', 'セットアップ必要')], default='setup_required', max_length=20, verbose_name='状態')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='browser_sessions', to='booking.store', verbose_name='店舗')),
            ],
            options={
                'verbose_name': 'ブラウザセッション',
                'verbose_name_plural': 'ブラウザセッション',
                'unique_together': {('store', 'platform')},
            },
        ),
        migrations.CreateModel(
            name='BrowserPostLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(verbose_name='投稿内容')),
                ('success', models.BooleanField(default=False, verbose_name='成功')),
                ('error_message', models.TextField(blank=True, verbose_name='エラーメッセージ')),
                ('screenshot', models.ImageField(blank=True, upload_to='browser_screenshots/', verbose_name='スクリーンショット')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='post_logs', to='social_browser.browsersession', verbose_name='セッション')),
                ('draft_post', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='browser_post_logs', to='booking.draftpost', verbose_name='元下書き')),
            ],
            options={
                'verbose_name': 'ブラウザ投稿ログ',
                'verbose_name_plural': 'ブラウザ投稿ログ',
                'ordering': ['-created_at'],
            },
        ),
    ]
