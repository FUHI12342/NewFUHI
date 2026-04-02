"""Tests for seed_page_templates management command."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from booking.models import PageTemplate


class SeedPageTemplatesTest(TestCase):
    """Test the seed_page_templates management command."""

    def test_creates_five_templates(self):
        out = StringIO()
        call_command('seed_page_templates', stdout=out)
        assert PageTemplate.objects.count() == 5

    def test_all_templates_are_system(self):
        call_command('seed_page_templates', stdout=StringIO())
        assert PageTemplate.objects.filter(is_system=True).count() == 5

    def test_template_categories(self):
        call_command('seed_page_templates', stdout=StringIO())
        salon_count = PageTemplate.objects.filter(category='salon').count()
        general_count = PageTemplate.objects.filter(category='general').count()
        assert salon_count == 2
        assert general_count == 3

    def test_templates_have_html_content(self):
        call_command('seed_page_templates', stdout=StringIO())
        for tpl in PageTemplate.objects.all():
            assert tpl.html_content.strip(), f'{tpl.name} has no HTML content'

    def test_idempotent_run(self):
        call_command('seed_page_templates', stdout=StringIO())
        call_command('seed_page_templates', stdout=StringIO())
        assert PageTemplate.objects.count() == 5

    def test_expected_template_names(self):
        call_command('seed_page_templates', stdout=StringIO())
        names = set(PageTemplate.objects.values_list('name', flat=True))
        expected = {'サロン紹介LP', 'キャンペーンページ', 'スタッフ紹介ページ', 'メニュー・料金表', 'お問い合わせページ'}
        assert names == expected
