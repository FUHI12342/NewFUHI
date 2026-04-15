"""SNS 下書き管理ビュー — AI生成、編集、即時投稿、予約投稿"""
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from booking.models import DraftPost, Store
from booking.views_dashboard_base import AdminSidebarMixin
from social_browser.services.browser_service import VALID_PLATFORMS

logger = logging.getLogger(__name__)


def _get_user_store_ids(user):
    """ユーザーがアクセス可能な店舗IDリストを返す"""
    if user.is_superuser:
        return None  # None = 全店舗アクセス可
    if hasattr(user, 'staff') and user.staff.store_id:
        return [user.staff.store_id]
    return []


def _get_draft_for_user(pk, user):
    """ユーザーの権限に基づいてDraftPostを取得（IDOR防止）"""
    store_ids = _get_user_store_ids(user)
    if store_ids is None:
        return get_object_or_404(DraftPost, pk=pk)
    if not store_ids:
        raise PermissionDenied
    return get_object_or_404(DraftPost, pk=pk, store_id__in=store_ids)


def _validate_platforms(platforms):
    """プラットフォームリストをバリデーションし、有効なもののみ返す"""
    return [p for p in platforms if p in VALID_PLATFORMS]


class StaffRequiredMixin(LoginRequiredMixin):
    """管理スタッフ権限チェック（店長・オーナー・開発者・superuser のみ）"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        is_admin = request.user.is_superuser or request.user.is_staff
        is_manager = (
            hasattr(request.user, 'staff')
            and (
                request.user.staff.is_store_manager
                or request.user.staff.is_owner
                or getattr(request.user.staff, 'is_developer', False)
            )
        )
        if not (is_admin or is_manager):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class DraftListView(AdminSidebarMixin, StaffRequiredMixin, ListView):
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

        # 各ドラフトにプラットフォーム別セッション状態をアノテーション
        try:
            from social_browser.models import BrowserSession
            sessions = BrowserSession.objects.all()
            session_map = {}
            for s in sessions:
                session_map[(s.store_id, s.platform)] = {
                    'status': s.status,
                    'label': s.get_status_display(),
                }
        except Exception:
            session_map = {}

        from booking.models import SocialAccount
        x_api_store_ids = set(
            SocialAccount.objects.filter(
                platform='x', is_active=True,
            ).values_list('store_id', flat=True)
        )

        for draft in ctx['drafts']:
            platform_states = []
            for p in (draft.platforms or []):
                state = {'platform': p}
                if p == 'x':
                    if draft.store_id in x_api_store_ids:
                        state['icon'] = 'fab fa-x-twitter'
                        state['method'] = 'API'
                        state['color'] = '#16a34a'
                    else:
                        sess = session_map.get((draft.store_id, 'x'))
                        state['icon'] = 'fab fa-x-twitter'
                        if sess and sess['status'] == 'active':
                            state['method'] = 'ブラウザ'
                            state['color'] = '#7c3aed'
                        else:
                            state['method'] = '要設定'
                            state['color'] = '#9ca3af'
                elif p == 'instagram':
                    sess = session_map.get((draft.store_id, 'instagram'))
                    state['icon'] = 'fab fa-instagram'
                    if sess and sess['status'] == 'active':
                        state['method'] = '有効'
                        state['color'] = '#16a34a'
                    elif sess and sess['status'] == 'expired':
                        state['method'] = '期限切れ'
                        state['color'] = '#dc2626'
                    else:
                        state['method'] = '要セットアップ'
                        state['color'] = '#f59e0b'
                elif p == 'gbp':
                    sess = session_map.get((draft.store_id, 'gbp'))
                    state['icon'] = 'fab fa-google'
                    if sess and sess['status'] == 'active':
                        state['method'] = '有効'
                        state['color'] = '#16a34a'
                    elif sess and sess['status'] == 'expired':
                        state['method'] = '期限切れ'
                        state['color'] = '#dc2626'
                    else:
                        state['method'] = '要セットアップ'
                        state['color'] = '#f59e0b'
                platform_states.append(state)
            draft.platform_states = platform_states

        return ctx


class DraftEditView(StaffRequiredMixin, View):
    """インライン編集 (POST) — 内容 + プラットフォーム更新"""

    def post(self, request, pk):
        draft = _get_draft_for_user(pk, request.user)
        content = request.POST.get('content', '').strip()
        if not content:
            return HttpResponseBadRequest("Content is required")

        draft.content = content

        # プラットフォーム更新（バリデーション付き）
        platforms = _validate_platforms(request.POST.getlist('platforms'))
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
    """即時投稿 — プラットフォームごとに自動ルーティング

    X: API投稿（SocialAccount あり）→ フォールバック: ブラウザ
    Instagram / GBP: ブラウザ投稿のみ（dispatch_draft_post 内で処理）
    """

    def post(self, request, pk):
        draft = _get_draft_for_user(pk, request.user)

        platforms = _validate_platforms(request.POST.getlist('platforms'))
        if not platforms:
            platforms = _validate_platforms(draft.platforms or ['x'])
        if not platforms:
            return HttpResponseBadRequest("有効なプラットフォームを選択してください")

        errors = []
        successes = []

        for platform in platforms:
            try:
                ok, msg = self._dispatch(draft, platform)
                if ok:
                    successes.append(f'{platform}: {msg}')
                else:
                    errors.append(f'{platform}: {msg}')
            except Exception as e:
                logger.error("Draft post failed for %s: %s", platform, e)
                errors.append(f'{platform}: 投稿処理中にエラーが発生しました')

        # 全成功 / 部分成功 / 全失敗 でステータスを分ける
        if successes and not errors:
            draft.status = 'posted'
            draft.posted_at = timezone.now()
            draft.save(update_fields=['status', 'posted_at', 'updated_at'])
            messages.success(request, '投稿しました: ' + '; '.join(successes))
        elif successes and errors:
            draft.posted_at = timezone.now()
            draft.save(update_fields=['posted_at', 'updated_at'])
            messages.warning(request, '一部投稿しました: ' + '; '.join(successes))
            messages.error(request, '投稿失敗: ' + '; '.join(errors))
        elif errors:
            messages.error(request, '投稿失敗: ' + '; '.join(errors))

        return redirect('social_draft_list')

    def _dispatch(self, draft, platform):
        """プラットフォームごとに最適な投稿方法を自動判定

        X: API投稿（SocialAccount あり時）→ フォールバック: ブラウザ
        Instagram / GBP: ブラウザ投稿（dispatch_draft_post 内で処理）
        """
        from booking.services.post_dispatcher import dispatch_draft_post

        if platform == 'x':
            # まず API 投稿を試行
            from booking.models import SocialAccount
            has_api = SocialAccount.objects.filter(
                store=draft.store, platform='x', is_active=True,
            ).exists()
            if has_api:
                ok, msg = dispatch_draft_post(draft, 'x')
                if ok:
                    return ok, msg
                # API 失敗時はブラウザフォールバックを試行
                logger.info("X API failed, trying browser fallback: %s", msg)
                return self._post_via_browser_x(draft)
            # API アカウントなし → ブラウザ
            return self._post_via_browser_x(draft)

        # Instagram / GBP はブラウザ投稿（PostHistory 記録含む）
        return dispatch_draft_post(draft, platform)

    def _post_via_browser_x(self, draft):
        """X ブラウザフォールバック（PostHistory も記録）"""
        from booking.models import PostHistory

        try:
            from social_browser.models import BrowserSession, BrowserPostLog
            from social_browser.services.browser_service import get_profile_dir
        except ImportError:
            return False, 'social_browser モジュールが利用できません'

        session, _ = BrowserSession.objects.get_or_create(
            store=draft.store, platform='x',
            defaults={
                'profile_dir': get_profile_dir(draft.store_id, 'x'),
                'status': 'setup_required',
            },
        )

        if session.status in ('setup_required', 'expired'):
            return False, f'Xブラウザセッション: {session.get_status_display()}'

        from social_browser.services.x_browser_poster import post_to_x_browser
        success, screenshot, error = post_to_x_browser(
            draft.content, session.profile_dir, headless=True,
        )

        BrowserPostLog.objects.create(
            session=session, draft_post=draft,
            content=draft.content, success=success,
            error_message=error or '',
        )

        # PostHistory も記録
        history = PostHistory.objects.create(
            store=draft.store, platform='x',
            trigger_type='manual', content=draft.content,
            status='posted' if success else 'failed',
            error_message='' if success else (error or ''),
        )
        if success:
            history.posted_at = timezone.now()
            history.save(update_fields=['posted_at'])
            return True, 'ブラウザ投稿完了'
        return False, error or 'ブラウザ投稿に失敗'


class DraftScheduleView(StaffRequiredMixin, View):
    """予約投稿 (POST)"""

    def post(self, request, pk):
        draft = _get_draft_for_user(pk, request.user)
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

        platforms = _validate_platforms(request.POST.getlist('platforms'))
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
        from booking.admin_site import custom_site
        stores = Store.objects.all()
        context = {
            'stores': stores,
            'available_apps': custom_site.get_app_list(request),
            'has_permission': True,
        }
        return TemplateResponse(request, 'admin/booking/social_drafts/generate.html', context)

    def post(self, request):
        store_id = request.POST.get('store_id')
        target_date_str = request.POST.get('target_date', '')
        platforms = _validate_platforms(request.POST.getlist('platforms')) or ['x']

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
            messages.error(request, 'AI下書きの生成に失敗しました。管理者に連絡してください。')

        return redirect('social_draft_list')


class DraftRegenerateView(StaffRequiredMixin, View):
    """AI 再生成"""

    def post(self, request, pk):
        draft = _get_draft_for_user(pk, request.user)

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
