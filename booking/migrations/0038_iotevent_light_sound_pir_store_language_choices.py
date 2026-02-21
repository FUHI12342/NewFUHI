"""
Migration 0038: Add light_value, sound_value, pir_triggered to IoTEvent.
Add choices to Store.default_language.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0037_remove_iotdevice_api_key_and_more'),
    ]

    operations = [
        # IoTEvent new sensor fields
        migrations.AddField(
            model_name='iotevent',
            name='light_value',
            field=models.FloatField(blank=True, db_index=True, null=True, verbose_name='照度値'),
        ),
        migrations.AddField(
            model_name='iotevent',
            name='sound_value',
            field=models.FloatField(blank=True, db_index=True, null=True, verbose_name='音値'),
        ),
        migrations.AddField(
            model_name='iotevent',
            name='pir_triggered',
            field=models.BooleanField(blank=True, null=True, verbose_name='PIR検知'),
        ),
        # New indexes for light and sound
        migrations.AddIndex(
            model_name='iotevent',
            index=models.Index(fields=['device', 'created_at', 'light_value'], name='booking_iot_device__b0e4c9_idx'),
        ),
        migrations.AddIndex(
            model_name='iotevent',
            index=models.Index(fields=['device', 'created_at', 'sound_value'], name='booking_iot_device__c1f5da_idx'),
        ),
        # Store.default_language choices
        migrations.AlterField(
            model_name='store',
            name='default_language',
            field=models.CharField(
                blank=True, choices=[
                    ('ja', '日本語'), ('en', 'English'), ('zh-hant', '繁體中文'),
                    ('zh-hans', '简体中文'), ('ko', '한국어'), ('es', 'Español'), ('pt', 'Português'),
                ],
                default='ja', max_length=10, verbose_name='既定言語',
            ),
        ),
    ]
