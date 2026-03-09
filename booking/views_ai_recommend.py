"""AI推薦View + API"""
import json
import logging
from datetime import date, timedelta

from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from booking.views_restaurant_dashboard import AdminSidebarMixin
from booking.models import Store, Staff, StaffRecommendationModel, StaffRecommendationResult

logger = logging.getLogger(__name__)


def _get_user_store(request):
    if request.user.is_superuser:
        store_id = request.GET.get('store_id') or request.POST.get('store_id')
        if store_id:
            return Store.objects.filter(id=store_id).first()
        return Store.objects.first()
    try:
        return request.user.staff.store
    except (Staff.DoesNotExist, AttributeError):
        return Store.objects.first()


class AIRecommendationView(AdminSidebarMixin, TemplateView):
    """AI推薦結果表示"""
    template_name = 'admin/booking/ai_recommendation.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)

        active_model = StaffRecommendationModel.objects.filter(
            store=store, is_active=True,
        ).first() if store else None

        # 今週の推薦結果
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        recommendations = StaffRecommendationResult.objects.filter(
            store=store,
            date__gte=week_start,
            date__lte=week_end,
        ).order_by('date', 'hour') if store else []

        ctx.update({
            'title': 'AI推薦',
            'has_permission': True,
            'store': store,
            'stores': Store.objects.all(),
            'active_model': active_model,
            'recommendations': recommendations,
            'week_start': week_start,
            'week_end': week_end,
        })
        return ctx


class AIRecommendationAPIView(View):
    """推薦結果JSON"""

    def get(self, request):
        store = _get_user_store(request)
        date_from = request.GET.get('date_from', date.today().isoformat())
        date_to = request.GET.get('date_to', (date.today() + timedelta(days=7)).isoformat())

        results = StaffRecommendationResult.objects.filter(
            store=store,
            date__gte=date_from,
            date__lte=date_to,
        ).order_by('date', 'hour') if store else []

        data = [{
            'date': r.date.isoformat(),
            'hour': r.hour,
            'recommended_staff_count': r.recommended_staff_count,
            'confidence': r.confidence,
            'factors': r.factors,
        } for r in results]

        return JsonResponse(data, safe=False)


class AITrainModelAPIView(View):
    """モデル再学習トリガー"""

    def post(self, request):
        store = _get_user_store(request)
        if not store:
            return JsonResponse({'error': 'No store found'}, status=404)

        from booking.services.ai_staff_recommend import train_model
        model = train_model(store)

        if model:
            return JsonResponse({
                'success': True,
                'model_type': model.model_type,
                'mae_score': model.mae_score,
                'training_samples': model.training_samples,
            })
        return JsonResponse({'error': 'Training failed - insufficient data'}, status=400)


class AIModelStatusAPIView(View):
    """モデル精度・最終学習日時"""

    def get(self, request):
        store = _get_user_store(request)
        model = StaffRecommendationModel.objects.filter(
            store=store, is_active=True,
        ).first() if store else None

        if not model:
            return JsonResponse({'has_model': False})

        return JsonResponse({
            'has_model': True,
            'model_type': model.model_type,
            'mae_score': model.mae_score,
            'accuracy_score': model.accuracy_score,
            'training_samples': model.training_samples,
            'trained_at': model.trained_at.isoformat(),
            'feature_names': model.feature_names,
        })
