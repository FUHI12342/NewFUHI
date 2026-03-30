"""Embed ビュー（WordPress iframe埋め込み）のテスト"""
import pytest
from django.test import RequestFactory

from booking.models import SiteSettings, Store
from booking.views_embed import (
    EmbedBookingView, EmbedShiftView, EmbedAuthMixin, generate_embed_api_key,
)


@pytest.fixture
def embed_store(db):
    """embed_api_key 付きの Store"""
    return Store.objects.create(
        name="テスト店舗",
        address="東京都",
        business_hours="10:00-20:00",
        nearest_station="新宿駅",
        embed_api_key="test_key_123",
    )


@pytest.fixture
def embed_enabled(db):
    """embed を有効にした SiteSettings"""
    ss = SiteSettings.load()
    ss.embed_enabled = True
    ss.save()
    return ss


@pytest.mark.django_db
class TestEmbedAuth:
    def test_embed_disabled_returns_404(self, client, embed_store):
        """embed_enabled=False の場合 404"""
        ss = SiteSettings.load()
        ss.embed_enabled = False
        ss.save()
        response = client.get(
            f'/embed/booking/{embed_store.pk}/?api_key=test_key_123'
        )
        assert response.status_code == 404

    def test_missing_api_key_returns_403(self, client, embed_store, embed_enabled):
        """API key なしで 403"""
        response = client.get(f'/embed/booking/{embed_store.pk}/')
        assert response.status_code == 403

    def test_wrong_api_key_returns_403(self, client, embed_store, embed_enabled):
        """間違った API key で 403"""
        response = client.get(
            f'/embed/booking/{embed_store.pk}/?api_key=wrong_key'
        )
        assert response.status_code == 403

    def test_valid_api_key_returns_200(self, client, embed_store, embed_enabled):
        """正しい API key で 200"""
        response = client.get(
            f'/embed/booking/{embed_store.pk}/?api_key=test_key_123'
        )
        assert response.status_code == 200

    def test_no_xframe_header(self, client, embed_store, embed_enabled):
        """embed ビューは X-Frame-Options ヘッダーを送らない"""
        response = client.get(
            f'/embed/booking/{embed_store.pk}/?api_key=test_key_123'
        )
        assert 'X-Frame-Options' not in response


@pytest.mark.django_db
class TestEmbedBookingView:
    def test_booking_view_contains_store_name(self, client, embed_store, embed_enabled):
        """予約ビューに店舗名が含まれる"""
        response = client.get(
            f'/embed/booking/{embed_store.pk}/?api_key=test_key_123'
        )
        assert embed_store.name.encode() in response.content


@pytest.mark.django_db
class TestEmbedShiftView:
    def test_shift_view_returns_200(self, client, embed_store, embed_enabled):
        """シフトビューが 200 を返す"""
        response = client.get(
            f'/embed/shift/{embed_store.pk}/?api_key=test_key_123'
        )
        assert response.status_code == 200

    def test_shift_view_contains_store_name(self, client, embed_store, embed_enabled):
        """シフトビューに店舗名が含まれる"""
        response = client.get(
            f'/embed/shift/{embed_store.pk}/?api_key=test_key_123'
        )
        assert embed_store.name.encode() in response.content


@pytest.mark.django_db
class TestEmbedCSPHeader:
    def test_csp_header_when_domains_set(self, client, embed_store, embed_enabled):
        """embed_allowed_domains が設定されている場合 CSP ヘッダーが追加される"""
        embed_store.embed_allowed_domains = "example.com\nother.com"
        embed_store.save()
        response = client.get(
            f'/embed/booking/{embed_store.pk}/?api_key=test_key_123'
        )
        assert 'Content-Security-Policy' in response
        assert 'example.com' in response['Content-Security-Policy']


class TestGenerateEmbedApiKey:
    def test_generates_unique_keys(self):
        """毎回異なる API キーが生成される"""
        key1 = generate_embed_api_key()
        key2 = generate_embed_api_key()
        assert key1 != key2
        assert len(key1) > 20
