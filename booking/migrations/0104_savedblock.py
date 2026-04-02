"""Add SavedBlock model for reusable GrapesJS blocks."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0103_custompage_seo_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedBlock',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=100, verbose_name='ブロック名')),
                ('category', models.CharField(default='保存済み', max_length=50, verbose_name='カテゴリ')),
                ('html_content', models.TextField(verbose_name='HTML')),
                ('css_content', models.TextField(blank=True, default='', verbose_name='CSS')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='作成日時')),
                ('store', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saved_blocks',
                    to='booking.store',
                    verbose_name='店舗',
                )),
            ],
            options={
                'verbose_name': '保存済みブロック',
                'verbose_name_plural': '保存済みブロック',
                'ordering': ['-created_at'],
            },
        ),
    ]
