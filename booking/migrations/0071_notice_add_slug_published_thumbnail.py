"""Add slug, is_published, thumbnail, created_at to Notice. Populate slugs for existing rows."""

import uuid
from django.db import migrations, models
from django.utils.text import slugify


def populate_notice_slugs(apps, schema_editor):
    Notice = apps.get_model('booking', 'Notice')
    for notice in Notice.objects.all():
        base = slugify(notice.title, allow_unicode=True) or 'notice'
        notice.slug = f'{base}-{uuid.uuid4().hex[:8]}'
        notice.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0070_category_is_restaurant_menu_sitesettings_price_label_and_more'),
    ]

    operations = [
        # 1. Add slug without unique first (allow blank default '')
        migrations.AddField(
            model_name='notice',
            name='slug',
            field=models.SlugField(
                blank=True, default='', max_length=200,
                help_text='URLスラッグ（空欄なら自動生成）',
            ),
            preserve_default=False,
        ),
        # 2. Populate existing slugs
        migrations.RunPython(populate_notice_slugs, migrations.RunPython.noop),
        # 3. Now add unique constraint
        migrations.AlterField(
            model_name='notice',
            name='slug',
            field=models.SlugField(
                blank=True, max_length=200, unique=True,
                help_text='URLスラッグ（空欄なら自動生成）',
            ),
        ),
        # 4. Other field changes
        migrations.AddField(
            model_name='notice',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='notice',
            name='is_published',
            field=models.BooleanField(default=True, verbose_name='公開'),
        ),
        migrations.AddField(
            model_name='notice',
            name='thumbnail',
            field=models.ImageField(
                blank=True, null=True, upload_to='notice_thumbnails/',
                verbose_name='サムネイル',
            ),
        ),
        migrations.AlterField(
            model_name='notice',
            name='link',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='notice',
            name='content',
            field=models.TextField(default='', help_text='HTML形式で記述できます'),
        ),
        migrations.AlterModelOptions(
            name='notice',
            options={
                'ordering': ['-updated_at'],
                'verbose_name': 'お知らせ',
                'verbose_name_plural': 'お知らせ',
            },
        ),
    ]
