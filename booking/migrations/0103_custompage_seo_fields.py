"""Add SEO fields to CustomPage."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0102_custompage_layout'),
    ]

    operations = [
        migrations.AddField(
            model_name='custompage',
            name='meta_title',
            field=models.CharField(
                blank=True, default='',
                help_text='検索結果に表示されるタイトル（未設定時はページタイトルを使用）',
                max_length=70, verbose_name='メタタイトル',
            ),
        ),
        migrations.AddField(
            model_name='custompage',
            name='meta_description',
            field=models.TextField(
                blank=True, default='',
                help_text='検索結果に表示される説明文（160文字以内推奨）',
                max_length=160, verbose_name='メタディスクリプション',
            ),
        ),
        migrations.AddField(
            model_name='custompage',
            name='og_image_url',
            field=models.URLField(
                blank=True, default='',
                help_text='SNSシェア時に表示される画像のURL',
                max_length=500, verbose_name='OGP画像URL',
            ),
        ),
    ]
