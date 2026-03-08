"""Tests for core models: DashboardLayout, SystemConfig, AdminTheme, IRCode, Timer, Company, Notice, Media."""
import pytest
from unittest.mock import patch
from django.contrib.auth.models import User

from booking.models import (
    DashboardLayout, SystemConfig, AdminTheme, IRCode, Timer,
    Company, Notice, Media, Store,
)


class TestSystemConfigModel:
    """Tests for SystemConfig.get and SystemConfig.set."""

    @pytest.mark.django_db
    def test_get_returns_default_when_key_missing(self):
        """SystemConfig.get returns default when key does not exist."""
        result = SystemConfig.get('missing_key', 'fallback')
        assert result == 'fallback'

    @pytest.mark.django_db
    def test_get_returns_empty_string_default(self):
        """SystemConfig.get returns empty string by default."""
        result = SystemConfig.get('missing_key')
        assert result == ''

    @pytest.mark.django_db
    def test_set_creates_new_entry(self):
        """SystemConfig.set creates a new config entry."""
        obj = SystemConfig.set('new_key', 'new_value')
        assert obj.key == 'new_key'
        assert obj.value == 'new_value'

    @pytest.mark.django_db
    def test_set_updates_existing_entry(self):
        """SystemConfig.set updates an existing config entry."""
        SystemConfig.set('upd_key', 'old')
        SystemConfig.set('upd_key', 'new')
        assert SystemConfig.get('upd_key') == 'new'
        assert SystemConfig.objects.filter(key='upd_key').count() == 1

    @pytest.mark.django_db
    def test_str(self):
        """SystemConfig __str__ shows key = value."""
        obj = SystemConfig.set('log_level', 'DEBUG')
        assert str(obj) == 'log_level = DEBUG'


class TestDashboardLayoutModel:
    """Tests for the DashboardLayout model."""

    @pytest.mark.django_db
    def test_creation(self):
        """DashboardLayout can be created for a user."""
        user = User.objects.create_user(username='layout_user', password='pass')
        layout = DashboardLayout.objects.create(
            user=user,
            layout_json=[{'widget': 'iot', 'x': 0, 'y': 0}],
        )
        assert layout.pk is not None
        assert layout.dark_mode is False

    @pytest.mark.django_db
    def test_str(self):
        """DashboardLayout __str__ includes username."""
        user = User.objects.create_user(username='dl_user', password='pass')
        layout = DashboardLayout.objects.create(user=user)
        assert 'dl_user' in str(layout)


class TestTimerModel:
    """Tests for the Timer model."""

    @pytest.mark.django_db
    def test_str_format(self):
        """Timer __str__ includes user_id and times."""
        from django.utils import timezone
        timer = Timer.objects.create(
            user_id='U12345',
            end_time=timezone.now(),
        )
        result = str(timer)
        assert 'U12345' in result

    @pytest.mark.django_db
    def test_user_id_unique(self):
        """Timer user_id is unique."""
        Timer.objects.create(user_id='unique_user')
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            Timer.objects.create(user_id='unique_user')


class TestCompanyModel:
    """Tests for the Company model."""

    @pytest.mark.django_db
    def test_creation(self):
        """Company can be created."""
        company = Company.objects.create(
            name='Test Company',
            address='Tokyo',
            tel='03-1234-5678',
        )
        assert company.pk is not None

    @pytest.mark.django_db
    def test_str(self):
        """Company __str__ returns company name."""
        company = Company(name='My Co')
        assert str(company) == 'My Co'


class TestNoticeModel:
    """Tests for the Notice model."""

    @pytest.mark.django_db
    def test_creation(self):
        """Notice can be created."""
        notice = Notice.objects.create(
            title='Important Notice',
            link='https://example.com',
            content='This is a notice.',
        )
        assert notice.pk is not None

    @pytest.mark.django_db
    def test_str(self):
        """Notice __str__ returns title."""
        notice = Notice(title='Test Notice')
        assert str(notice) == 'Test Notice'


class TestMediaModel:
    """Tests for the Media model."""

    @pytest.mark.django_db
    def test_creation_without_url_fetch(self):
        """Media can be created (url fetch may fail in test env)."""
        with patch.object(Media, '_is_safe_url', return_value=False):
            media = Media.objects.create(
                link='https://example.com/article',
            )
            assert media.pk is not None

    @pytest.mark.django_db
    def test_str(self):
        """Media __str__ returns title."""
        media = Media(title='Article Title')
        assert str(media) == 'Article Title'


class TestAdminThemeModel:
    """Tests for the AdminTheme model."""

    @pytest.mark.django_db
    def test_defaults(self, store):
        """AdminTheme has correct default colors."""
        theme = AdminTheme.objects.create(store=store)
        assert theme.primary_color == '#8c876c'
        assert theme.secondary_color == '#f1f0ec'

    @pytest.mark.django_db
    def test_str(self, store):
        """AdminTheme __str__ includes store name."""
        theme = AdminTheme.objects.create(store=store)
        assert store.name in str(theme)


class TestIRCodeModel:
    """Tests for the IRCode model."""

    @pytest.mark.django_db
    def test_creation(self, iot_device):
        """IRCode can be created."""
        ir = IRCode.objects.create(
            device=iot_device,
            name='Power ON',
            protocol='NEC',
            code='0xFF00',
        )
        assert ir.pk is not None

    @pytest.mark.django_db
    def test_str(self, iot_device):
        """IRCode __str__ includes device name and IR code name."""
        ir = IRCode.objects.create(
            device=iot_device,
            name='Volume Up',
            protocol='NEC',
            code='0x01',
        )
        result = str(ir)
        assert iot_device.name in result
        assert 'Volume Up' in result
