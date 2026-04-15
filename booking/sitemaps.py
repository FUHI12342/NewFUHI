"""
SEO用サイトマップ定義
django.contrib.sitemaps を使用して各ページの URL を自動生成する。
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from booking.models.core import Store


class StaticPageSitemap(Sitemap):
    """静的ページ（トップ・一覧・ヘルプ等）のサイトマップ"""
    priority = 0.8
    changefreq = "weekly"
    # i18n prefix なしのロケールを使用（LocaleMiddleware が付与する）
    i18n = False

    def items(self):
        return [
            "booking:booking_top",
            "booking:all_fortune_tellers",
            "booking:help",
            "booking:notice_list",
            "booking:privacy_policy",
            "booking:tokushoho",
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):  # type: ignore[override]
        if item == "booking:booking_top":
            return 1.0
        return 0.8


class StoreStaffSitemap(Sitemap):
    """店舗スタッフ一覧ページのサイトマップ（/store/{id}/staffs/）"""
    priority = 0.7
    changefreq = "weekly"
    i18n = False

    def items(self):
        return Store.objects.all()

    def location(self, store):
        return reverse("booking:staff_list", args=[store.pk])

    def lastmod(self, store):
        # Store モデルに updated_at がない場合は None を返す（省略可）
        return getattr(store, "updated_at", None)
