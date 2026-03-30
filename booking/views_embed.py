"""外部埋め込み（iframe）ビュー — WordPress等からのiframe読み込み用"""
import secrets
from django.http import HttpResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from booking.models import SiteSettings, Store, Staff
from booking.models.shifts import ShiftAssignment, ShiftPeriod, ShiftPublishHistory


class EmbedAuthMixin:
    """API key 認証 + embed 有効性チェック"""

    def check_embed_auth(self, request, store_id):
        """認証チェック。成功時は Store を返す。失敗時は HttpResponse を返す。"""
        # グローバル embed 設定チェック
        site_settings = SiteSettings.load()
        if not site_settings.embed_enabled:
            raise Http404("Embed is not enabled")

        store = get_object_or_404(Store, pk=store_id)

        # API key チェック
        api_key = request.GET.get('api_key', '')
        if not store.embed_api_key or api_key != store.embed_api_key:
            return None, HttpResponseForbidden("Invalid or missing API key")

        return store, None

    def build_csp_header(self, store, response):
        """embed_allowed_domains が設定されている場合、frame-ancestors ヘッダーを追加"""
        allowed = store.embed_allowed_domains.strip()
        if allowed:
            domains = ' '.join(
                line.strip() for line in allowed.splitlines() if line.strip()
            )
            response['Content-Security-Policy'] = f"frame-ancestors {domains}"
        return response


@method_decorator(xframe_options_exempt, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class EmbedBookingView(EmbedAuthMixin, View):
    """予約カレンダー埋め込みビュー"""

    def get(self, request, store_id):
        store, error_response = self.check_embed_auth(request, store_id)
        if error_response:
            return error_response

        # 店舗のスタッフ一覧（占い師）
        staffs = Staff.objects.filter(
            store=store, staff_type='fortune_teller'
        ).order_by('-is_recommended', 'name')

        context = {
            'store': store,
            'staffs': staffs,
            'api_key': request.GET.get('api_key', ''),
            'site_settings': SiteSettings.load(),
        }
        response = TemplateResponse(
            request, 'booking/embed/booking_calendar.html', context,
        )
        return self.build_csp_header(store, response)


@method_decorator(xframe_options_exempt, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class EmbedShiftView(EmbedAuthMixin, View):
    """シフト表示（読み取り専用）埋め込みビュー"""

    def get(self, request, store_id):
        store, error_response = self.check_embed_auth(request, store_id)
        if error_response:
            return error_response

        today = timezone.localdate()

        # 公開済みのシフト期間を取得（year_monthが今月のもの）
        first_of_month = today.replace(day=1)
        published_period_ids = ShiftPublishHistory.objects.filter(
            action='publish',
            period__store=store,
            period__year_month=first_of_month,
        ).values_list('period_id', flat=True)

        assignments = ShiftAssignment.objects.filter(
            period_id__in=published_period_ids,
            date=today,
        ).select_related('staff').order_by('start_hour', 'staff__name')

        period = ShiftPeriod.objects.filter(
            id__in=published_period_ids,
        ).first()

        context = {
            'store': store,
            'today': today,
            'assignments': assignments,
            'period': period,
            'api_key': request.GET.get('api_key', ''),
        }
        response = TemplateResponse(
            request, 'booking/embed/shift_view.html', context,
        )
        return self.build_csp_header(store, response)


def generate_embed_api_key():
    """安全なランダム API キーを生成"""
    return secrets.token_urlsafe(32)
