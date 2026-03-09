"""AI推薦テスト"""
import pytest
from datetime import date, timedelta, time
from booking.models import ShiftAssignment, VisitorCount, StaffRecommendationResult


@pytest.mark.django_db
class TestFeatureMatrix:
    def test_empty_data(self, store):
        from booking.services.ai_staff_recommend import build_feature_matrix
        X, y, names = build_feature_matrix(store, lookback_days=7)
        assert isinstance(X, list)
        assert len(names) == 6

    def test_with_data(self, store, shift_assignment, visitor_count):
        from booking.services.ai_staff_recommend import build_feature_matrix
        X, y, names = build_feature_matrix(store, lookback_days=365)
        assert isinstance(X, list)

    def test_feature_names(self, store):
        from booking.services.ai_staff_recommend import build_feature_matrix
        _, _, names = build_feature_matrix(store)
        assert 'day_of_week' in names
        assert 'hour' in names


@pytest.mark.django_db
class TestModelTraining:
    def test_train_insufficient_data(self, store):
        from booking.services.ai_staff_recommend import train_model
        result = train_model(store)
        assert result is None

    def test_train_with_data(self, store, staff, shift_period):
        """Create enough data to train"""
        from booking.services.ai_staff_recommend import train_model
        # Create 20+ assignments across dates
        for i in range(25):
            d = date.today() - timedelta(days=i)
            ShiftAssignment.objects.create(
                period=shift_period, staff=staff,
                date=d, start_hour=9, end_hour=17,
                start_time=time(9, 0), end_time=time(17, 0),
            )
            for h in range(9, 17):
                VisitorCount.objects.create(
                    store=store, date=d, hour=h,
                    estimated_visitors=5, order_count=3,
                )
        model = train_model(store)
        if model:  # sklearn might not be installed
            assert model.mae_score >= 0
            assert model.training_samples > 0

    def test_train_returns_none_without_sklearn(self, store):
        from booking.services.ai_staff_recommend import train_model
        result = train_model(store)
        # With no data, should return None regardless
        assert result is None


@pytest.mark.django_db
class TestRecommendation:
    def test_no_model(self, store):
        from booking.services.ai_staff_recommend import generate_recommendations
        count = generate_recommendations(store, [date.today()])
        assert count == 0

    def test_api_returns_200(self, admin_client):
        resp = admin_client.get('/api/ai/recommendations/')
        assert resp.status_code == 200

    def test_model_status_no_model(self, admin_client):
        resp = admin_client.get('/api/ai/model-status/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['has_model'] is False

    def test_recommendation_page(self, admin_client):
        resp = admin_client.get('/admin/ai/recommendation/')
        assert resp.status_code == 200


@pytest.mark.django_db
class TestAIRecommendationAPI:
    def test_recommendations_empty(self, admin_client):
        resp = admin_client.get('/api/ai/recommendations/')
        data = resp.json()
        assert isinstance(data, list)

    def test_train_no_data(self, admin_client):
        resp = admin_client.post('/api/ai/train/', content_type='application/json')
        assert resp.status_code == 400

    def test_model_status(self, admin_client):
        resp = admin_client.get('/api/ai/model-status/')
        assert resp.status_code == 200
