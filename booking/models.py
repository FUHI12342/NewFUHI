from django.conf import settings
from django.db import models
from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth.models import User

class Timer(models.Model):
    user_id = models.CharField(max_length=255, unique=True)
    start_time = models.DateTimeField(auto_now_add=True)
    # class Meta:
    #     app_label = 'booking' 
from django.conf import settings

class Store(models.Model):
    """店舗一覧"""
    name = models.CharField('店名', max_length=255)
    thumbnail = models.ImageField('サムネイル画像', upload_to='store_thumbnails/', null=True, blank=True)
    address = models.CharField('住所', max_length=255, default='')
    business_hours = models.CharField('営業時間', max_length=255, default='')
    nearest_station = models.CharField('最寄り駅', max_length=255, default='')
    regular_holiday = models.CharField('定休日', max_length=255, default='')
    description = models.TextField('店舗情報', default='', blank=True) 

    class Meta:
        verbose_name = '店舗一覧'
        verbose_name_plural = '店舗一覧'

    def __str__(self):
        return self.name

    def get_thumbnail_url(self):
        if self.thumbnail and hasattr(self.thumbnail, 'url'):
            return self.thumbnail.url
        else:
            # デフォルトの画像URLを返す
            return settings.STATIC_URL + 'default_thumbnail.jpg'
        
class Staff(models.Model):
    """在籍占い師スタッフリスト"""
    name = models.CharField('表示名', max_length=50)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name='ログインユーザー', on_delete=models.CASCADE, related_name='staff'
    )
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE)
    line_id = models.CharField('LINE ID', max_length=50, null=True, blank=True)  # ラインID
    thumbnail = models.ImageField('サムネイル画像', upload_to='thumbnails/', null=True, blank=True)  # サムネイル画像
    introduction = models.TextField('自己紹介文', null=True, blank=True)  # 自己紹介文
    position = models.CharField(max_length=100)
    price = models.IntegerField('価格', default=0)  # 価格情報、デフォルト値を0に設定
    class Meta:
        verbose_name = '在籍占い師スタッフリスト'
        verbose_name_plural = '在籍占い師スタッフリスト'

    def __str__(self):
        return f'{self.store.name} - {self.name}'
    
class Customer(models.Model):
    name = models.CharField(max_length=100, default='Unknown')
    age = models.IntegerField(default=0) 
    hashed_line_user_id = models.CharField(max_length=64, unique=True, null=True)

    def __str__(self):  
        return self.name

    def print_hashed_line_user_id(self):
        print('hashed_line_user_id: ' + str(self.hashed_line_user_id))
    
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
import uuid

class Schedule(models.Model):
    """予約スケジュール."""
    reservation_number = models.CharField('予約管理番号', max_length=255, default=uuid.uuid4, editable=False)
    start = models.DateTimeField('開始時間')
    end = models.DateTimeField('終了時間')
    staff = models.ForeignKey('Staff', verbose_name='占いスタッフ', on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    hashed_id = models.CharField(max_length=255, null=True, blank=True)
    is_temporary = models.BooleanField('仮予約フラグ', default=True)
    price = models.IntegerField('価格', default=0)  # 価格情報、デフォルト値を0に設定
    memo = models.TextField('備考', blank=True, null=True, default='ここに備考を記入してください。')
    temporary_booked_at = models.DateTimeField(null=True, blank=True)
    store = models.ForeignKey('booking.Store', on_delete=models.CASCADE, default=1, verbose_name='店舗')
    reservation_time = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = '予約スケジュール'
        verbose_name_plural = '予約スケジュール'

    def __str__(self):
        start = timezone.localtime(self.start).strftime('%Y/%m/%d %H:%M:%S')
        end = timezone.localtime(self.end).strftime('%Y/%m/%d %H:%M:%S')
        customer_name = self.customer_name if self.customer_name else "No customer"
        return f'{self.reservation_number} {start} ~ {end} {self.staff} Customer: {customer_name}'
    
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class Company(models.Model):
    name = models.CharField('会社名', max_length=255)
    address = models.CharField('住所', max_length=255)
    tel = models.CharField('電話番号', max_length=20, default='000-0000-0000')
    class Meta:
        verbose_name = '運営会社情報'
        verbose_name_plural = '運営会社情報'

class Notice(models.Model):
    updated_at = models.DateTimeField(auto_now=True)  # 更新日
    title = models.CharField(max_length=200)  # タイトル
    link = models.URLField()  # リンク
    content = models.TextField(default='')  # 内容
    class Meta:
        verbose_name = 'お知らせ'
        verbose_name_plural = 'お知らせ'
    def __str__(self):
        return self.title

from newspaper import Article
import textwrap

class Media(models.Model):
    link = models.URLField()    
    title = models.CharField(max_length=200, blank=True)  # titleフィールドを追加
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)  # descriptionフィールドを追加
    
    def save(self, *args, **kwargs):
        article = Article(self.link)
        article.download()
        article.parse()
        self.title = article.title[:10] + '...' if len(article.title) > 10 else article.title

        # descriptionを12文字ごとに改行し、最初の3行だけを取得
        wrapped_text = textwrap.wrap(article.text, width=12)
        self.description = '\n'.join(wrapped_text[:3])

        super().save(*args, **kwargs)

    def thumbnail_url(self):
        article = Article(self.link)
        article.download()
        article.parse()
        return article.top_image

    class Meta:
        verbose_name = 'メディア掲載情報'
        verbose_name_plural = 'メディア掲載情報'

    def __str__(self):
        return self.title

