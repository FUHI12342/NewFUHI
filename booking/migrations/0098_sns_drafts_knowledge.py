import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('booking', '0097_embed_support'),
    ]

    operations = [
        migrations.CreateModel(
            name='KnowledgeEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('cast_profile', 'キャストプロフィール'), ('store_info', '店舗情報'), ('service_info', 'サービス情報'), ('campaign', 'キャンペーン'), ('custom', 'カスタム')], max_length=20, verbose_name='カテゴリ')),
                ('title', models.CharField(max_length=200, verbose_name='タイトル')),
                ('content', models.TextField(help_text='AI生成の参照情報', verbose_name='内容')),
                ('is_active', models.BooleanField(default=True, verbose_name='有効')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='knowledge_entries', to='booking.store', verbose_name='店舗')),
                ('staff', models.ForeignKey(blank=True, help_text='cast_profile の場合のみ指定', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='knowledge_entries', to='booking.staff', verbose_name='スタッフ')),
            ],
            options={
                'verbose_name': 'SNSナレッジ',
                'verbose_name_plural': 'SNSナレッジ',
                'ordering': ['store', 'category', 'title'],
                'app_label': 'booking',
            },
        ),
        migrations.CreateModel(
            name='DraftPost',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(help_text='編集可能', verbose_name='投稿内容')),
                ('ai_generated_content', models.TextField(blank=True, help_text='編集前の原文（監査用）', verbose_name='AI生成原文')),
                ('platforms', models.JSONField(default=list, help_text='例: ["x", "instagram", "gbp"]', verbose_name='投稿先プラットフォーム')),
                ('status', models.CharField(choices=[('generated', 'AI生成済み'), ('reviewed', 'レビュー中'), ('approved', '承認済み'), ('rejected', '却下'), ('posted', '投稿済み'), ('scheduled', '予約投稿')], default='generated', max_length=20, verbose_name='ステータス')),
                ('target_date', models.DateField(blank=True, help_text='出勤情報の対象日', null=True, verbose_name='対象日')),
                ('scheduled_at', models.DateTimeField(blank=True, null=True, verbose_name='予約投稿日時')),
                ('quality_score', models.FloatField(blank=True, help_text='LLM Judge スコア (0.0-1.0)', null=True, verbose_name='品質スコア')),
                ('quality_feedback', models.TextField(blank=True, verbose_name='品質フィードバック')),
                ('image', models.ImageField(blank=True, null=True, upload_to='draft_images/', verbose_name='画像')),
                ('posted_at', models.DateTimeField(blank=True, null=True, verbose_name='投稿日時')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='draft_posts', to='booking.store', verbose_name='店舗')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='作成者')),
            ],
            options={
                'verbose_name': 'SNS下書き',
                'verbose_name_plural': 'SNS下書き',
                'ordering': ['-created_at'],
                'app_label': 'booking',
            },
        ),
    ]
