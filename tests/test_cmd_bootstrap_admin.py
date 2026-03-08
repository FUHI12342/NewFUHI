"""Tests for bootstrap_admin_staff management command."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth.models import User

from booking.models import Staff, Store


class TestBootstrapAdminStaffCommand:
    """Tests for the bootstrap_admin_staff management command."""

    @pytest.mark.django_db
    def test_creates_user_and_staff(self, store):
        """Command creates both User and Staff when they do not exist."""
        call_command(
            'bootstrap_admin_staff',
            '--username', 'newadmin',
            '--store_id', str(store.pk),
        )
        user = User.objects.get(username='newadmin')
        assert user.is_staff
        assert user.is_superuser
        staff = Staff.objects.get(user=user)
        assert staff.store == store

    @pytest.mark.django_db
    def test_updates_existing_staff(self, store, staff):
        """Command updates existing Staff flags."""
        call_command(
            'bootstrap_admin_staff',
            '--username', staff.user.username,
            '--store_id', str(store.pk),
            '--manager',
            '--developer',
        )
        staff.refresh_from_db()
        assert staff.is_store_manager is True
        assert staff.is_developer is True

    @pytest.mark.django_db
    def test_raises_error_for_nonexistent_store(self):
        """Command raises CommandError when store_id does not exist."""
        with pytest.raises(CommandError, match='does not exist'):
            call_command(
                'bootstrap_admin_staff',
                '--username', 'someone',
                '--store_id', '9999',
            )

    @pytest.mark.django_db
    def test_sets_manager_flag(self, store):
        """Command sets is_store_manager when --manager is passed."""
        call_command(
            'bootstrap_admin_staff',
            '--username', 'mgr_user',
            '--store_id', str(store.pk),
            '--manager',
        )
        staff = Staff.objects.get(user__username='mgr_user')
        assert staff.is_store_manager is True

    @pytest.mark.django_db
    def test_sets_developer_flag(self, store):
        """Command sets is_developer when --developer is passed."""
        call_command(
            'bootstrap_admin_staff',
            '--username', 'dev_user',
            '--store_id', str(store.pk),
            '--developer',
        )
        staff = Staff.objects.get(user__username='dev_user')
        assert staff.is_developer is True
