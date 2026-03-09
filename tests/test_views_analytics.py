"""分析テスト"""
import json
import pytest
from django.test import Client
from booking.models import VisitorCount


@pytest.mark.django_db
class TestVisitorAnalyticsDashboard:
    def test_dashboard_returns_200(self, admin_client):
        resp = admin_client.get('/admin/analytics/visitors/')
        assert resp.status_code == 200

    def test_dashboard_contains_title(self, admin_client):
        resp = admin_client.get('/admin/analytics/visitors/')
        assert '来客分析' in resp.content.decode()

    def test_dashboard_requires_auth(self):
        client = Client()
        resp = client.get('/admin/analytics/visitors/')
        assert resp.status_code in (302, 403)


@pytest.mark.django_db
class TestVisitorCountAPI:
    def test_list_visitors(self, admin_client, visitor_count):
        resp = admin_client.get('/api/analytics/visitors/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data) >= 1

    def test_list_with_range(self, admin_client, visitor_count):
        resp = admin_client.get('/api/analytics/visitors/?range=30')
        assert resp.status_code == 200

    def test_list_empty(self, admin_client):
        resp = admin_client.get('/api/analytics/visitors/?range=1')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert isinstance(data, list)

    def test_visitor_data_fields(self, admin_client, visitor_count):
        resp = admin_client.get('/api/analytics/visitors/')
        data = json.loads(resp.content)
        if data:
            assert 'date' in data[0]
            assert 'estimated_visitors' in data[0]
            assert 'order_count' in data[0]


@pytest.mark.django_db
class TestHeatmapAPI:
    def test_heatmap_returns_200(self, admin_client):
        resp = admin_client.get('/api/analytics/heatmap/')
        assert resp.status_code == 200

    def test_heatmap_data_structure(self, admin_client, visitor_count):
        resp = admin_client.get('/api/analytics/heatmap/')
        data = json.loads(resp.content)
        assert isinstance(data, dict)


@pytest.mark.django_db
class TestVisitorAggregation:
    def test_aggregate_empty(self, store):
        from booking.services.visitor_analytics import aggregate_visitor_counts
        from datetime import date
        count = aggregate_visitor_counts(store, date.today(), date.today())
        assert count >= 0

    def test_count_sessions(self):
        from booking.services.visitor_analytics import _count_sessions
        from datetime import datetime, timedelta
        t0 = datetime(2026, 3, 9, 12, 0, 0)
        timestamps = [t0, t0 + timedelta(seconds=60), t0 + timedelta(seconds=600)]
        assert _count_sessions(timestamps, 300) == 2

    def test_count_sessions_empty(self):
        from booking.services.visitor_analytics import _count_sessions
        assert _count_sessions([], 300) == 0

    def test_count_sessions_single(self):
        from booking.services.visitor_analytics import _count_sessions
        from datetime import datetime
        assert _count_sessions([datetime.now()], 300) == 1

    def test_count_sessions_all_close(self):
        from booking.services.visitor_analytics import _count_sessions
        from datetime import datetime, timedelta
        t0 = datetime(2026, 3, 9, 12, 0, 0)
        timestamps = [t0 + timedelta(seconds=i * 10) for i in range(5)]
        assert _count_sessions(timestamps, 300) == 1


@pytest.mark.django_db
class TestConversionRate:
    def test_conversion(self, store, visitor_count):
        from booking.services.visitor_analytics import calculate_conversion_rate
        from datetime import date, timedelta
        result = calculate_conversion_rate(store, date.today() - timedelta(days=1), date.today())
        assert 'conversion_rate' in result
        assert result['total_visitors'] >= 0

    def test_conversion_no_data(self, store):
        from booking.services.visitor_analytics import calculate_conversion_rate
        from datetime import date
        result = calculate_conversion_rate(store, date(2020, 1, 1), date(2020, 1, 2))
        assert result['conversion_rate'] == 0.0

    def test_conversion_zero_visitors(self, store):
        from booking.services.visitor_analytics import calculate_conversion_rate
        from datetime import date
        result = calculate_conversion_rate(store, date(2020, 1, 1), date(2020, 1, 1))
        assert result['total_visitors'] == 0
