"""SNS 下書き管理ビュー — AI生成、編集、即時投稿、予約投稿"""
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from booking.models import DraftPost, Store

logger = logging.getLogger(__name__)


class StaffRequiredMixin(LoginRequiredMixin):
    """管理スタッフ権限チェック"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not (request.user.is_superuser or hasattr(request.user, 'staff')):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class DraftListView(StaffRequiredMixin, ListView):
    """下書き一覧"""
    template_name = 'admin/booking/social_drafts/list.html'
    context_object_name = 'drafts'
    paginate_by = 20

    def get_queryset(self):
        qs = DraftPost.objects.select_related('store', 'created_by')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        store_id = self.request.GET.get('store')
        if store_id:
            qs = qs.filter(store_id=store_id)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['stores'] = Store.objects.all()
        ctx['status_choices'] = DraftPost._meta.get_field('status').choices
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_store'] = self.request.GET.get('store', '')
        return ctx


class DraftEditView(StaffRequiredMixin, View):
    """インライン編集 (POST) — 内容 + プラットフォーム更新"""

    def post(self, request, pk):
        draft = get_object_or_404(DraftPost, pk=pk)
        content = request.POST.get('content', '').strip()
        if not content:
            return HttpResponseBadRequest("Content is required")

        draft.content = content

        # プラットフォーム更新
        platforms = request.POST.getlist('platforms')
        if platforms:
            draft.platforms = platforms

        if draft.status == 'generated':
            draft.status = 'reviewed'

        update_fields = ['content', 'status', 'platforms', 'updated_at']
        draft.save(update_fields=update_fields)

        # 再評価
        from booking.services.sns_evaluation_service import evaluate_draft_quality
        evaluate_draft_quality(draft)

        messages.success(request, f'下書きを更新しました (スコア: {draft.quality_score})')
        return redirect('social_draft_list')


class DraftPostView(StaffRequiredMixin, View):
    """即時投稿 — プラットフォームごとにAPI/ブラウザを振り分け"""

    def post(self, request, pk):
        draft = get_object_or_404(DraftPost, pk=pk)

        platforms = request.POST.getlist('platforms')
        if not platforms:
            platforms = draft.platforms or ['x']

        post_method = request.POST.get('post_method', 'api')  # 'api' or 'browser'
        errors = []
        successes = []

        for platform in platforms:
            try:
                if post_method == 'browser':
                    ok, msg = self._post_via_browser(draft, platform)
                else:
                    ok, msg = self._post_via_api(draft, platform)

                if ok:
                    successes.append(f'{platform}: {msg}')
                else:
                    errors.append(f'{platform}: {msg}')
            except Exception as e:
                logger.error("Draft post failed for %s: %s", platform, e)
                errors.append(f'{platform}: {e}')

        if successes:
            draft.status = 'posted'
            draft.posted_at = timezone.now()
            draft.save(update_fields=['status', 'posted_at', 'updated_at'])
            messages.success(request, '投稿しました: ' + '; '.join(successes))

        if errors:
            messages.error(request, '投稿失敗: ' + '; '.join(errors))

        return redirect('social_draft_list')

    def _post_via_api(self, draft, platform):
        """API経由で投稿（X のみ対応）"""
        if platform != 'x':
            return False, f'{platform}はAPI投稿に非対応（ブラウザ投稿を使用）'

        from booking.services.post_dispatcher import dispatch_post
        context_json = {'content': draft.content, 'draft_id': draft.pk}
        dispatch_post(draft.store_id, 'manual', context_json)
        return True, '投稿完了'

    def _post_via_browser(self, draft, platform):
        """ブラウザ経由で投稿（全プラットフォーム対応）"""
        try:
            from social_browser.models import BrowserSession, BrowserPostLog
            from social_browser.services.browser_service import get_profile_dir
        except ImportError:
            return False, 'social_browser モジュールが利用できません'

        # BrowserSession を取得 or 作成
        session, _ = BrowserSession.objects.get_or_create(
            store=draft.store, platform=platform,
            defaults={
                'profile_dir': get_profile_dir(draft.store_id, platform),
                'status': 'setup_required',
            },
        )

        if session.status == 'setup_required':
            return False, 'ブラウザセッション未設定（管理者がログインしてください）'

        # プラットフォーム別ブラウザ投稿
        if platform == 'x':
            from social_browser.services.x_browser_poster import post_to_x_browser
            success, screenshot, error = post_to_x_browser(
                draft.content, session.profile_dir, headless=True,
            )
        elif platform == 'instagram':
            from social_browser.services.instagram_poster import post_to_instagram_browser
            image_path = draft.image.path if draft.image else None
            success, screenshot, error = post_to_instagram_browser(
                draft.content, image_path, session.profile_dir, headless=True,
            )
        elif platform == 'gbp':
            from social_browser.services.gbp_poster import post_to_gbp_browser
            success, screenshot, error = post_to_gbp_browser(
                draft.content, session.profile_dir, headless=True,
            )
        else:
            return False, f'未対応プラットフォーム: {platform}'

        # ログ記録
        BrowserPostLog.objects.create(
            session=session,
            draft_post=draft,
            content=draft.content,
            success=success,
            error_message=error or '',
        )

        if success:
            return True, 'ブラウザ投稿完了'
        return False, error or 'ブラウザ投稿に失敗'


class DraftScheduleView(StaffRequiredMixin, View):
    """予約投稿 (POST)"""

    def post(self, request, pk):
        draft = get_object_or_404(DraftPost, pk=pk)
        scheduled_at = request.POST.get('scheduled_at')
        if not scheduled_at:
            return HttpResponseBadRequest("scheduled_at is required")

        try:
            from django.utils.dateparse import parse_datetime
            dt = parse_datetime(scheduled_at)
            if dt is None:
                return HttpResponseBadRequest("Invalid datetime format")
        except (ValueError, TypeError):
            return HttpResponseBadRequest("Invalid datetime format")

        platforms = request.POST.getlist('platforms')
        if platforms:
            draft.platforms = platforms

        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        draft.scheduled_at = dt
        draft.status = 'scheduled'
        draft.save(update_fields=['scheduled_at', 'status', 'platforms', 'updated_at'])
        messages.success(request, f'予約投稿を設定しま��た: {dt}')
        return redirect('social_draft_list')


class DraftGenerateView(StaffRequiredMixin, View):
    """AI 下書き新規生成"""

    def get(self, request):
        """生成フォーム表示"""
        from django.template.response import TemplateResponse
        stores = Store.objects.all()
        return TemplateResponse(request, 'admin/booking/social_drafts/generate.html', {
            'stores': stores,
        })

    def post(self, request):
        store_id = request.POST.get('store_id')
        target_date_str = request.POST.get('target_date', '')
        platforms = request.POST.getlist('platforms') or ['x']

        store = get_object_or_404(Store, pk=store_id)

        target_date = None
        if target_date_str:
            from django.utils.dateparse import parse_date
            target_date = parse_date(target_date_str)

        from booking.services.sns_draft_service import generate_daily_draft
        draft = generate_daily_draft(store, target_date, platforms)

        if draft:
            # 品質評価も実行
            from booking.services.sns_evaluation_service import evaluate_draft_quality
            evaluate_draft_quality(draft)
            messages.success(request, f'下書きを生成しました (スコア: {draft.quality_score})')
        else:
            messages.error(request, 'AI下書きの生成に失敗しました。GEMINI_API_KEY を確認してください。')

        return redirect('social_draft_list')


class DraftRegenerateView(StaffRequiredMixin, View):
    """AI 再生成"""

    def post(self, request, pk):
        draft = get_object_or_404(DraftPost, pk=pk)

        from booking.services.sns_draft_service import generate_daily_draft
        new_draft = generate_daily_draft(
            draft.store, draft.target_date, draft.platforms,
        )

        if new_draft:
            from booking.services.sns_evaluation_service import evaluate_draft_quality
            evaluate_draft_quality(new_draft)
            # 旧ドラフトを却下
            draft.status = 'rejected'
            draft.save(update_fields=['status', 'updated_at'])
            messages.success(request, f'再生成しました (新スコア: {new_draft.quality_score})')
        else:
            messages.error(request, 'AI再生成に失敗しました。')

        return redirect('social_draft_list')
