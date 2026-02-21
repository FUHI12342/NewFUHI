"""
Migration 0041: Add Property, PropertyDevice, PropertyAlert models.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0040_systemconfig'),
    ]

    operations = [
        migrations.CreateModel(
            name='Property',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='物件名')),
                ('address', models.CharField(max_length=300, verbose_name='住所')),
                ('property_type', models.CharField(
                    choices=[('apartment', 'アパート/マンション'), ('house', '一戸建て'), ('office', 'オフィス'), ('store', '店舗')],
                    default='apartment', max_length=20, verbose_name='種別',
                )),
                ('owner_name', models.CharField(blank=True, max_length=100, verbose_name='オーナー名')),
                ('owner_contact', models.CharField(blank=True, max_length=200, verbose_name='オーナー連絡先')),
                ('is_active', models.BooleanField(default=True, verbose_name='有効')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('store', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='properties', to='booking.store', verbose_name='関連店舗',
                )),
            ],
            options={
                'verbose_name': '物件',
                'verbose_name_plural': '物件',
            },
        ),
        migrations.CreateModel(
            name='PropertyDevice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('location_label', models.CharField(help_text='例: リビング, 玄関, 寝室', max_length=100, verbose_name='設置場所')),
                ('property', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='property_devices', to='booking.property', verbose_name='物件',
                )),
                ('device', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='property_placements', to='booking.iotdevice', verbose_name='デバイス',
                )),
            ],
            options={
                'verbose_name': '物件デバイス',
                'verbose_name_plural': '物件デバイス',
                'unique_together': {('property', 'device')},
            },
        ),
        migrations.CreateModel(
            name='PropertyAlert',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(
                    choices=[('gas_leak', 'ガス漏れ'), ('no_motion', '長期不在'), ('device_offline', 'デバイスオフライン'), ('custom', 'カスタム')],
                    max_length=20, verbose_name='種別',
                )),
                ('severity', models.CharField(
                    choices=[('critical', '緊急'), ('warning', '警告'), ('info', '情報')],
                    default='info', max_length=10, verbose_name='重要度',
                )),
                ('message', models.TextField(blank=True, verbose_name='メッセージ')),
                ('is_resolved', models.BooleanField(db_index=True, default=False, verbose_name='解決済み')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True, verbose_name='解決日時')),
                ('property', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='alerts', to='booking.property', verbose_name='物件',
                )),
                ('device', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='property_alerts', to='booking.iotdevice', verbose_name='デバイス',
                )),
            ],
            options={
                'verbose_name': '物件アラート',
                'verbose_name_plural': '物件アラート',
                'indexes': [
                    models.Index(fields=['property', 'is_resolved', 'created_at'], name='booking_pro_propert_a1b2c3_idx'),
                    models.Index(fields=['alert_type', 'is_resolved'], name='booking_pro_alert_t_d4e5f6_idx'),
                ],
            },
        ),
    ]
