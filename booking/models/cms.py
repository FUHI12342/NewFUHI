"""CMS models: Company, Notice, Media, HeroBanner, BannerAd, ExternalLink, HomepageCustomBlock"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from newspaper import Article


class Company(models.Model):
    name = models.CharField(_('会社名'), max_length=255)
    address = models.CharField(_('住所'), max_length=255)
    tel = models.CharField(_('電話番号'), max_length=20, default='000-0000-0000')

    class Meta:
        app_label = 'booking'
        verbose_name = _('運営会社情報')
        verbose_name_plural = _('運営会社情報')

    def __str__(self):
        return self.name


class Notice(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=200, unique=True, blank=True,
        help_text=_('URLスラッグ（空欄なら自動生成）'),
    )
    link = models.URLField(blank=True, default='')
    content = models.TextField(default='', help_text=_('HTML形式で記述できます'))
    is_published = models.BooleanField(_('公開'), default=True)
    thumbnail = models.ImageField(
        _('サムネイル'), upload_to='notice_thumbnails/', blank=True, null=True,
    )

    class Meta:
        app_label = 'booking'
        verbose_name = _('お知らせ')
        verbose_name_plural = _('お知らせ')
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            import uuid as _uuid
            base = slugify(self.title, allow_unicode=True) or 'notice'
            self.slug = f'{base}-{_uuid.uuid4().hex[:8]}'
        if self.content:
            from booking.services.html_sanitizer import sanitize_rich_text
            self.content = sanitize_rich_text(self.content)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('booking:notice_detail', kwargs={'slug': self.slug})

    def excerpt(self, length=100):
        """HTMLタグを除去して抜粋を返す"""
        import re
        text = re.sub(r'<[^>]+>', '', self.content)
        return text[:length] + '...' if len(text) > length else text


class Media(models.Model):
    link = models.URLField()
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)
    cached_thumbnail_url = models.URLField(_('サムネイルURL'), blank=True)

    @staticmethod
    def _is_safe_url(url: str) -> bool:
        """内部ネットワークへのアクセスを防ぐURLバリデーション"""
        from urllib.parse import urlparse
        import ipaddress
        import socket
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # 内部IPアドレスをブロック
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(hostname))
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except socket.gaierror:
            return False
        except ValueError:
            pass
        return True

    def save(self, *args, **kwargs):
        # 初回作成時のみ（title未設定の場合のみ）URLからメタ情報を取得
        if self.link and not self.title and self._is_safe_url(self.link):
            try:
                article = Article(self.link)
                article.download()
                article.parse()
                if article.title:
                    self.title = article.title[:200]
                if article.text and not self.description:
                    self.description = article.text[:300]
                if article.top_image and not self.cached_thumbnail_url:
                    self.cached_thumbnail_url = article.top_image
            except Exception:
                pass  # 外部URLの取得失敗時もsave自体は成功させる
        super().save(*args, **kwargs)

    def thumbnail_url(self):
        """キャッシュされたサムネイルURLを返す（毎回ダウンロードしない）"""
        return self.cached_thumbnail_url or ''

    class Meta:
        app_label = 'booking'
        verbose_name = _('メディア掲載情報')
        verbose_name_plural = _('メディア掲載情報')

    def __str__(self):
        return self.title


class HomepageCustomBlock(models.Model):
    """WordPress風カスタムHTMLブロック"""
    POSITION_CHOICES = [
        ('above_cards', _('カードの上')),
        ('below_cards', _('カードの下')),
        ('sidebar', _('サイドバー')),
    ]
    title = models.CharField(_('タイトル'), max_length=200)
    content = models.TextField(_('HTML内容'), help_text=_('HTMLを直接記述できます'))
    position = models.CharField(_('表示位置'), max_length=20, choices=POSITION_CHOICES, default='below_cards')
    sort_order = models.IntegerField(_('並び順'), default=0)
    is_active = models.BooleanField(_('公開'), default=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('カスタムブロック')
        verbose_name_plural = _('カスタムブロック')
        ordering = ['position', 'sort_order']

    def save(self, *args, **kwargs):
        if self.content:
            from booking.services.html_sanitizer import sanitize_rich_text
            self.content = sanitize_rich_text(self.content)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.title} ({self.get_position_display()})'


class HeroBanner(models.Model):
    """ヒーローバナースライダー"""
    IMAGE_POSITION_CHOICES = [
        ('center', _('中央')),
        ('top', _('上')),
        ('bottom', _('下')),
        ('left', _('左')),
        ('right', _('右')),
        ('top left', _('左上')),
        ('top right', _('右上')),
        ('bottom left', _('左下')),
        ('bottom right', _('右下')),
    ]
    LINK_TYPE_CHOICES = [
        ('none', _('リンクなし')),
        ('store', _('店舗')),
        ('staff', _('占い師')),
        ('url', _('カスタムURL')),
    ]
    title = models.CharField(_('タイトル'), max_length=200)
    image = models.ImageField(_('バナー画像'), upload_to='hero_banners/')
    image_position = models.CharField(
        _('画像表示位置'), max_length=20,
        choices=IMAGE_POSITION_CHOICES, default='center',
        help_text=_('バナー内で画像のどの部分を表示するかを指定します'),
    )
    link_type = models.CharField(
        _('リンク種別'), max_length=10,
        choices=LINK_TYPE_CHOICES, default='none',
    )
    linked_store = models.ForeignKey(
        'Store', verbose_name=_('リンク先店舗'),
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    linked_staff = models.ForeignKey(
        'Staff', verbose_name=_('リンク先占い師'),
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    link_url = models.URLField(_('リンクURL'), blank=True, default='')
    sort_order = models.IntegerField(_('並び順'), default=0)
    is_active = models.BooleanField(_('公開'), default=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        ordering = ['sort_order']
        verbose_name = _('ヒーローバナー')
        verbose_name_plural = _('ヒーローバナー')

    def __str__(self):
        return self.title

    def get_link_url(self):
        """link_type に応じたリンク先URLを返す"""
        from django.urls import reverse
        if self.link_type == 'store' and self.linked_store_id:
            return reverse('booking:staff_list', kwargs={'pk': self.linked_store_id})
        elif self.link_type == 'staff' and self.linked_staff_id:
            return reverse('booking:staff_calendar', kwargs={'pk': self.linked_staff_id})
        elif self.link_type == 'url' and self.link_url:
            return self.link_url
        return ''


class BannerAd(models.Model):
    """バナー広告"""
    POSITION_CHOICES = [
        ('after_hero', _('ヒーローバナーの後')),
        ('after_cards', _('カードの後')),
        ('after_ranking', _('ランキングの後')),
        ('after_campaign', _('キャンペーンの後')),
        ('sidebar', _('サイドバー')),
    ]
    title = models.CharField(_('タイトル'), max_length=200)
    image = models.ImageField(_('バナー画像'), upload_to='banner_ads/')
    link_url = models.URLField(_('リンクURL'), blank=True, default='')
    position = models.CharField(_('表示位置'), max_length=20, choices=POSITION_CHOICES, default='after_hero')
    sort_order = models.IntegerField(_('並び順'), default=0)
    is_active = models.BooleanField(_('公開'), default=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        ordering = ['position', 'sort_order']
        verbose_name = _('バナー広告')
        verbose_name_plural = _('バナー広告')

    def __str__(self):
        return f'{self.title} ({self.get_position_display()})'


class ExternalLink(models.Model):
    """外部リンク"""
    title = models.CharField(_('タイトル'), max_length=200)
    url = models.URLField(_('URL'))
    description = models.TextField(_('説明'), blank=True, default='')
    sort_order = models.IntegerField(_('並び順'), default=0)
    is_active = models.BooleanField(_('公開'), default=True)
    open_in_new_tab = models.BooleanField(_('新しいタブで開く'), default=True)

    class Meta:
        app_label = 'booking'
        ordering = ['sort_order']
        verbose_name = _('外部リンク')
        verbose_name_plural = _('外部リンク')

    def __str__(self):
        return self.title
