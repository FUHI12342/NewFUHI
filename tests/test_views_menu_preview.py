"""
Tests for booking/views_menu_preview.py — MenuPreviewRedirectView.
"""
import pytest
from django.test import Client
from django.contrib.auth import get_user_model

from booking.models import Store, Staff, TableSeat

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def preview_store(db):
    return Store.objects.create(name="プレビュー店舗", address="東京都")


@pytest.fixture
def preview_admin(db, preview_store):
    user = User.objects.create_superuser(
        username="prev_admin", password="pass1234", email="prev@test.com",
    )
    Staff.objects.create(name="管理者", store=preview_store, user=user, is_developer=True)
    client = Client()
    client.login(username="prev_admin", password="pass1234")
    return client


@pytest.fixture
def preview_staff_client(db, preview_store):
    user = User.objects.create_user(
        username="prev_staff", password="pass1234", email="pstaff@test.com",
        is_staff=True,
    )
    Staff.objects.create(name="スタッフ", store=preview_store, user=user)
    client = Client()
    client.login(username="prev_staff", password="pass1234")
    return client


class TestMenuPreviewRedirectView:
    URL = "/admin/menu/preview/"

    def test_redirect_to_table(self, preview_admin, preview_store):
        seat = TableSeat.objects.create(
            store=preview_store, label="A1", is_active=True,
        )
        resp = preview_admin.get(self.URL)
        assert resp.status_code == 302
        assert f"/t/{seat.id}/" in resp.url

    def test_no_table_returns_message(self, preview_admin, preview_store):
        resp = preview_admin.get(self.URL)
        assert resp.status_code == 200
        assert "テーブル" in resp.content.decode()

    def test_inactive_table_skipped(self, preview_admin, preview_store):
        TableSeat.objects.create(
            store=preview_store, label="INACTIVE", is_active=False,
        )
        resp = preview_admin.get(self.URL)
        assert resp.status_code == 200  # no active table → message

    def test_staff_user_redirect(self, preview_staff_client, preview_store):
        seat = TableSeat.objects.create(
            store=preview_store, label="B1", is_active=True,
        )
        resp = preview_staff_client.get(self.URL)
        assert resp.status_code == 302
        assert f"/t/{seat.id}/" in resp.url

    def test_staff_no_staff_profile(self, db, preview_store):
        user = User.objects.create_user(
            username="nostaffprofile", password="pass1234",
            email="nosp@test.com", is_staff=True,
        )
        client = Client()
        client.login(username="nostaffprofile", password="pass1234")
        # No Staff object → falls through to Store.objects.first()
        TableSeat.objects.create(
            store=preview_store, label="C1", is_active=True,
        )
        resp = client.get(self.URL)
        assert resp.status_code == 302

    def test_selects_first_by_label(self, preview_admin, preview_store):
        seat_b = TableSeat.objects.create(
            store=preview_store, label="B1", is_active=True,
        )
        seat_a = TableSeat.objects.create(
            store=preview_store, label="A1", is_active=True,
        )
        resp = preview_admin.get(self.URL)
        assert resp.status_code == 302
        # ordered by label, "A1" < "B1"
        assert f"/t/{seat_a.id}/" in resp.url
