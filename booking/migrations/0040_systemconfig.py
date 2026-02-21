"""
Migration 0040: Add SystemConfig model for runtime settings.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0039_backfill_iotevent_light_sound'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100, unique=True, verbose_name='キー')),
                ('value', models.TextField(blank=True, default='', verbose_name='値')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新日時')),
            ],
            options={
                'verbose_name': 'システム設定',
                'verbose_name_plural': 'システム設定',
            },
        ),
    ]
