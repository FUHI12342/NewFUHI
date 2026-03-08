"""Tests for CMS models: SiteSettings, HeroBanner, HomepageCustomBlock, BannerAd, ExternalLink."""
import pytest
from unittest.mock import patch
from django.urls import reverse

from booking.models import (
    SiteSettings, HeroBanner, HomepageCustomBlock, BannerAd, ExternalLink,
    Store, Staff,
)


class TestSiteSettingsModel:
    """Tests for the SiteSettings singleton model."""

    @pytest.mark.django_db
    def test_load_creates_singleton(self):
        """SiteSettings.load() creates instance with pk=1 if none exists."""
        ss = SiteSettings.load()
        assert ss.pk == 1

    @pytest.mark.django_db
    def test_load_returns_existing(self):
        """SiteSettings.load() returns the existing pk=1 instance."""
        ss1 = SiteSettings.load()
        ss1.site_name = 'Changed Name'
        ss1.save()
        ss2 = SiteSettings.load()
        assert ss2.pk == 1
        assert ss2.site_name == 'Changed Name'

    @pytest.mark.django_db
    def test_save_always_uses_pk_1(self):
        """SiteSettings.save() forces pk=1."""
        ss = SiteSettings(site_name='Test Site')
        ss.save()
        assert ss.pk == 1

    @pytest.mark.django_db
    def test_str_returns_site_name(self):
        """SiteSettings __str__ returns site_name."""
        ss = SiteSettings.load()
        assert str(ss) == ss.site_name

    @pytest.mark.django_db
    def test_default_values(self):
        """SiteSettings has sensible defaults."""
        ss = SiteSettings.load()
        assert ss.show_card_store is True
        assert ss.show_card_fortune_teller is True
        assert ss.show_ai_chat is False


class TestHeroBannerModel:
    """Tests for the HeroBanner model."""

    @pytest.mark.django_db
    def test_get_link_url_none(self):
        """HeroBanner.get_link_url returns empty string for link_type='none'."""
        banner = HeroBanner(title='Test', link_type='none')
        assert banner.get_link_url() == ''

    @pytest.mark.django_db
    def test_get_link_url_custom_url(self):
        """HeroBanner.get_link_url returns link_url for link_type='url'."""
        banner = HeroBanner(
            title='Test',
            link_type='url',
            link_url='https://example.com',
        )
        assert banner.get_link_url() == 'https://example.com'

    @pytest.mark.django_db
    def test_get_link_url_store(self, store):
        """HeroBanner.get_link_url returns store URL for link_type='store'."""
        banner = HeroBanner.objects.create(
            title='Store Banner',
            image='hero_banners/test.jpg',
            link_type='store',
            linked_store=store,
        )
        url = banner.get_link_url()
        expected = reverse('booking:staff_list', kwargs={'pk': store.pk})
        assert url == expected

    @pytest.mark.django_db
    def test_get_link_url_staff(self, staff):
        """HeroBanner.get_link_url returns staff calendar URL for link_type='staff'."""
        banner = HeroBanner.objects.create(
            title='Staff Banner',
            image='hero_banners/test.jpg',
            link_type='staff',
            linked_staff=staff,
        )
        url = banner.get_link_url()
        expected = reverse('booking:staff_calendar', kwargs={'pk': staff.pk})
        assert url == expected

    @pytest.mark.django_db
    def test_str(self):
        """HeroBanner __str__ returns title."""
        banner = HeroBanner(title='My Banner')
        assert str(banner) == 'My Banner'


class TestHomepageCustomBlockModel:
    """Tests for the HomepageCustomBlock model."""

    @pytest.mark.django_db
    def test_position_choices(self):
        """HomepageCustomBlock supports all position choices."""
        for pos, _ in HomepageCustomBlock.POSITION_CHOICES:
            block = HomepageCustomBlock.objects.create(
                title=f'Block {pos}',
                content='<p>Test</p>',
                position=pos,
            )
            assert block.position == pos

    @pytest.mark.django_db
    def test_str(self):
        """HomepageCustomBlock __str__ includes title and position display."""
        block = HomepageCustomBlock(title='Test Block', position='sidebar')
        assert 'Test Block' in str(block)


class TestBannerAdModel:
    """Tests for the BannerAd model."""

    @pytest.mark.django_db
    def test_position_choices(self):
        """BannerAd supports all position choices."""
        for pos, _ in BannerAd.POSITION_CHOICES:
            ad = BannerAd.objects.create(
                title=f'Ad {pos}',
                image='banner_ads/test.jpg',
                position=pos,
            )
            assert ad.position == pos

    @pytest.mark.django_db
    def test_str(self):
        """BannerAd __str__ includes title and position."""
        ad = BannerAd(title='Test Ad', position='sidebar')
        assert 'Test Ad' in str(ad)


class TestExternalLinkModel:
    """Tests for the ExternalLink model."""

    @pytest.mark.django_db
    def test_creation(self):
        """ExternalLink can be created with required fields."""
        link = ExternalLink.objects.create(
            title='External Site',
            url='https://example.com',
        )
        assert link.pk is not None
        assert link.open_in_new_tab is True

    @pytest.mark.django_db
    def test_str(self):
        """ExternalLink __str__ returns title."""
        link = ExternalLink(title='My Link', url='https://test.com')
        assert str(link) == 'My Link'
