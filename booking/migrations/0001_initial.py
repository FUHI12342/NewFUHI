# Generated by Django 5.0.4 on 2024-06-20 08:36

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='会社名')),
                ('address', models.CharField(max_length=255, verbose_name='住所')),
                ('tel', models.CharField(default='000-0000-0000', max_length=20, verbose_name='電話番号')),
            ],
            options={
                'verbose_name': '運営会社情報',
                'verbose_name_plural': '運営会社情報',
            },
        ),
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('line_user_id', models.CharField(max_length=255, verbose_name='LINEユーザーID')),
                ('name', models.CharField(blank=True, max_length=255, null=True, verbose_name='名前')),
            ],
        ),
        migrations.CreateModel(
            name='Media',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('link', models.URLField()),
                ('title', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'メディア掲載情報',
                'verbose_name_plural': 'メディア掲載情報',
            },
        ),
        migrations.CreateModel(
            name='Notice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=200)),
                ('link', models.URLField()),
            ],
            options={
                'verbose_name': 'お知らせ',
                'verbose_name_plural': 'お知らせ',
            },
        ),
        migrations.CreateModel(
            name='Store',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='店名')),
                ('thumbnail', models.ImageField(blank=True, null=True, upload_to='store_thumbnails/', verbose_name='サムネイル画像')),
                ('address', models.CharField(default='', max_length=255, verbose_name='住所')),
                ('business_hours', models.CharField(default='', max_length=255, verbose_name='営業時間')),
                ('nearest_station', models.CharField(default='', max_length=255, verbose_name='最寄り駅')),
                ('regular_holiday', models.CharField(default='', max_length=255, verbose_name='定休日')),
                ('description', models.TextField(blank=True, default='', verbose_name='店舗情報')),
            ],
            options={
                'verbose_name': '店舗一覧',
                'verbose_name_plural': '店舗一覧',
            },
        ),
        migrations.CreateModel(
            name='Timer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.CharField(max_length=255, unique=True)),
                ('start_time', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Staff',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='表示名')),
                ('line_id', models.CharField(blank=True, max_length=50, null=True, verbose_name='LINE ID')),
                ('thumbnail', models.ImageField(blank=True, null=True, upload_to='thumbnails/', verbose_name='サムネイル画像')),
                ('introduction', models.TextField(blank=True, null=True, verbose_name='自己紹介文')),
                ('price', models.IntegerField(default=0, verbose_name='価格')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='staff', to=settings.AUTH_USER_MODEL, verbose_name='ログインユーザー')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='booking.store', verbose_name='店舗')),
            ],
            options={
                'verbose_name': '在籍占い師スタッフリスト',
                'verbose_name_plural': '在籍占い師スタッフリスト',
            },
        ),
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reservation_number', models.CharField(default=uuid.uuid4, editable=False, max_length=255, verbose_name='予約番号')),
                ('start', models.DateTimeField(verbose_name='開始時間')),
                ('end', models.DateTimeField(verbose_name='終了時間')),
                ('is_temporary', models.BooleanField(default=True, verbose_name='仮予約フラグ')),
                ('price', models.IntegerField(default=0, verbose_name='価格')),
                ('temporary_booked_at', models.DateTimeField(blank=True, null=True)),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='booking.customer', verbose_name='顧客')),
                ('staff', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='booking.staff', verbose_name='占いスタッフ')),
            ],
            options={
                'verbose_name': '予約確定済みのスケジュール',
                'verbose_name_plural': '予約確定済みのスケジュール',
            },
        ),
    ]
