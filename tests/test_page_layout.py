"""Tests for Phase 2: Section-based page layout system."""
import json
import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User

from booking.models import Store, PageLayout, SectionSchema
from booking.models.page_layout import DEFAULT_HOME_SECTIONS
from booking.services.page_layout_service import get_page_sections, _resolve_sections


class PageLayoutModelTest(TestCase):
    """PageLayout model tests."""

    def setUp(self):
        self.store = Store.objects.create(name='Test Store')

    def test_create_layout(self):
        layout = PageLayout.objects.create(
            store=self.store, page_type='home',
            sections_json=DEFAULT_HOME_SECTIONS,
        )
        assert layout.page_type == 'home'
        assert len(layout.sections_json) == len(DEFAULT_HOME_SECTIONS)

    def test_unique_together(self):
        PageLayout.objects.create(
            store=self.store, page_type='home',
            sections_json=[],
        )
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            PageLayout.objects.create(
                store=self.store, page_type='home',
                sections_json=[],
            )

    def test_str_representation(self):
        layout = PageLayout.objects.create(
            store=self.store, page_type='home', sections_json=[],
        )
        assert 'Test Store' in str(layout)

    def test_get_enabled_sections_empty(self):
        layout = PageLayout.objects.create(
            store=self.store, page_type='home', sections_json=[],
        )
        assert layout.get_enabled_sections() == []

    def test_get_enabled_sections_filters_disabled(self):
        layout = PageLayout.objects.create(
            store=self.store, page_type='home',
            sections_json=[
                {'type': 'hero_banner', 'enabled': True, 'settings': {}},
                {'type': 'ranking', 'enabled': False, 'settings': {}},
            ],
        )
        result = layout.get_enabled_sections()
        assert len(result) == 1
        assert result[0]['type'] == 'hero_banner'


class SectionSchemaTest(TestCase):
    """SectionSchema model tests."""

    def test_create_schema(self):
        schema = SectionSchema.objects.create(
            section_type='hero_banner',
            label='ヒーローバナー',
            template_name='booking/sections/hero_banner.html',
        )
        assert str(schema) == 'ヒーローバナー (hero_banner)'


class PageLayoutServiceTest(TestCase):
    """Page layout service tests."""

    def setUp(self):
        self.store = Store.objects.create(name='Test Store')

    def test_default_sections_when_no_layout(self):
        sections = get_page_sections(self.store, 'home')
        assert len(sections) == len(DEFAULT_HOME_SECTIONS)
        types = [s['type'] for s in sections]
        assert 'hero_banner' in types
        assert 'entry_cards' in types
        assert 'ranking' in types

    def test_custom_layout_overrides_default(self):
        PageLayout.objects.create(
            store=self.store, page_type='home',
            sections_json=[
                {'type': 'ranking', 'enabled': True, 'settings': {}},
                {'type': 'entry_cards', 'enabled': True, 'settings': {}},
            ],
        )
        sections = get_page_sections(self.store, 'home')
        assert len(sections) == 2
        assert sections[0]['type'] == 'ranking'
        assert sections[1]['type'] == 'entry_cards'

    def test_disabled_sections_filtered(self):
        PageLayout.objects.create(
            store=self.store, page_type='home',
            sections_json=[
                {'type': 'hero_banner', 'enabled': False, 'settings': {}},
                {'type': 'entry_cards', 'enabled': True, 'settings': {}},
            ],
        )
        sections = get_page_sections(self.store, 'home')
        assert len(sections) == 1
        assert sections[0]['type'] == 'entry_cards'

    def test_no_store_returns_defaults(self):
        sections = get_page_sections(None, 'home')
        assert len(sections) == len(DEFAULT_HOME_SECTIONS)

    def test_resolve_sections_template_name(self):
        result = _resolve_sections([
            {'type': 'hero_banner', 'enabled': True, 'settings': {}},
        ])
        assert result[0]['template_name'] == 'booking/sections/hero_banner.html'

    def test_unknown_page_type_returns_empty(self):
        sections = get_page_sections(self.store, 'nonexistent')
        assert sections == []


class PageLayoutEditorViewTest(TestCase):
    """Page layout editor view tests."""

    def setUp(self):
        self.store = Store.objects.create(name='Test Store')
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')

    def test_editor_get(self):
        self.client.force_login(self.user)
        resp = self.client.get(f'/admin/page-layout/{self.store.pk}/')
        assert resp.status_code == 200
        assert 'sections_json' in resp.context

    def test_editor_post_saves_layout(self):
        self.client.force_login(self.user)
        sections = [
            {'type': 'ranking', 'enabled': True, 'settings': {}},
            {'type': 'entry_cards', 'enabled': True, 'settings': {'columns': 2}},
        ]
        resp = self.client.post(
            f'/admin/page-layout/{self.store.pk}/',
            {'page_type': 'home', 'sections_json': json.dumps(sections)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'ok'
        layout = PageLayout.objects.get(store=self.store, page_type='home')
        assert len(layout.sections_json) == 2
        assert layout.sections_json[0]['type'] == 'ranking'

    def test_editor_post_invalid_json(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            f'/admin/page-layout/{self.store.pk}/',
            {'page_type': 'home', 'sections_json': 'not json'},
        )
        assert resp.status_code == 400
