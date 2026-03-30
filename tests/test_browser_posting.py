"""ブラウザ自動投稿モジュールのテスト (Playwright mock)"""
import pytest
from unittest.mock import patch, MagicMock

from booking.models import Store


@pytest.mark.django_db
class TestBrowserServiceHelpers:
    def test_get_profile_dir(self, store):
        from social_browser.services.browser_service import get_profile_dir
        path = get_profile_dir(store.pk, 'x')
        assert str(store.pk) in path
        assert 'x' in path

    def test_get_profile_dir_creates_directory(self, store, tmp_path):
        with patch('social_browser.services.browser_service.settings') as mock_settings:
            mock_settings.MEDIA_ROOT = str(tmp_path)
            from social_browser.services.browser_service import get_profile_dir
            path = get_profile_dir(store.pk, 'instagram')
            import os
            assert os.path.isdir(path)


@pytest.mark.django_db
class TestXBrowserPoster:
    def test_post_without_playwright_returns_error(self):
        """playwright 未インストール時は not installed エラーを返す"""
        from social_browser.services.x_browser_poster import post_to_x_browser
        success, screenshot, error = post_to_x_browser('test', '/tmp/profile')
        assert success is False
        # playwright 未インストール or ブラウザ未初期化
        assert error != ''


@pytest.mark.django_db
class TestInstagramPoster:
    def test_without_playwright_returns_error(self):
        """playwright 未インストール時はエラーを返す"""
        from social_browser.services.instagram_poster import post_to_instagram_browser
        success, screenshot, error = post_to_instagram_browser('test', '', '/tmp/profile')
        assert success is False
        assert error != ''


@pytest.mark.django_db
class TestBrowserSessionModel:
    def test_create_session(self, store):
        from social_browser.models import BrowserSession
        session = BrowserSession.objects.create(
            store=store, platform='x',
            profile_dir='/tmp/test', status='active',
        )
        assert session.id is not None
        assert 'X (Twitter)' in str(session)

    def test_unique_together(self, store):
        from social_browser.models import BrowserSession
        from django.db import IntegrityError
        BrowserSession.objects.create(
            store=store, platform='x', profile_dir='/tmp/1',
        )
        with pytest.raises(IntegrityError):
            BrowserSession.objects.create(
                store=store, platform='x', profile_dir='/tmp/2',
            )
