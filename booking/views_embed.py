"""外部埋め込み（iframe）ビュー — WordPress等からのiframe読み込み用"""
import datetime
import hashlib
import json
import logging
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db.models import Q
from django.http import HttpResponse, Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

import pytz
import requests

from booking.models import SiteSettings, Store, Staff
from booking.models.schedule import Schedule
from booking.models.shifts import ShiftAssignment, ShiftPeriod, ShiftPublishHistory
from booking.views import get_time_slots

logger = logging.getLogger(__name__)


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


@method_decorator(xframe_options_exempt, name='dispatch')
class EmbedDemoView(View):
    """埋め込みデモページ — 共有用"""

    def get(self, request):
        site_settings = SiteSettings.load()
        if not site_settings.embed_enabled:
            raise Http404("Embed is not enabled")

        # embed_api_key が設定されている最初の店舗を使用
        store = Store.objects.exclude(embed_api_key='').first()
        if not store:
            raise Http404("No store with embed API key configured")

        context = {
            'store': store,
            'api_key': store.embed_api_key,
        }
        return TemplateResponse(request, 'booking/embed/demo.html', context)


def generate_embed_api_key():
    """安全なランダム API キーを生成"""
    return secrets.token_urlsafe(32)


# ===== iframe内予約フロー完結ビュー =====


class EmbedTokenMixin:
    """embed_token で Schedule を取得するヘルパー"""

    def get_embed_schedule(self, embed_token):
        """embed_token で仮予約を取得。期限切れ/無効ならNone。"""
        cutoff = timezone.now() - datetime.timedelta(minutes=15)
        return Schedule.objects.filter(
            embed_token=embed_token,
            is_temporary=True,
            is_cancelled=False,
            temporary_booked_at__gte=cutoff,
        ).select_related('staff', 'store').first()


def _build_embed_url(path, api_key):
    """embed URL に api_key クエリパラメータを付与"""
    sep = '&' if '?' in path else '?'
    return f"{path}{sep}api_key={api_key}" if api_key else path


@method_decorator(xframe_options_exempt, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class EmbedStaffCalendarView(EmbedAuthMixin, View):
    """iframe内カレンダー表示"""

    def get(self, request, store_id, pk, year=None, month=None, day=None):
        store, error_response = self.check_embed_auth(request, store_id)
        if error_response:
            return error_response

        staff = get_object_or_404(Staff, pk=pk)
        api_key = request.GET.get('api_key', '')
        today = datetime.date.today()
        if year and month and day:
            try:
                base_date = datetime.date(year=year, month=month, day=day)
            except ValueError:
                raise Http404("Invalid date")
        else:
            base_date = today

        days = [base_date + datetime.timedelta(days=d) for d in range(7)]
        start_day, end_day = days[0], days[-1]

        time_slots_list, open_h, close_h, duration = get_time_slots(store)

        calendar = {}
        for slot in time_slots_list:
            calendar[slot['label']] = {d: True for d in days}

        start_time = datetime.datetime.combine(
            start_day, datetime.time(hour=open_h, minute=0))
        end_time = datetime.datetime.combine(
            end_day, datetime.time(hour=close_h, minute=0))

        for schedule in Schedule.objects.filter(
            staff=staff, is_cancelled=False,
        ).exclude(Q(start__gt=end_time) | Q(end__lt=start_time)):
            local_dt = timezone.localtime(schedule.start)
            booking_date = local_dt.date()
            booking_label = f"{local_dt.hour}:{local_dt.minute:02d}"
            if booking_label in calendar and booking_date in calendar[booking_label]:
                calendar[booking_label][booking_date] = (
                    'Temp' if schedule.is_temporary else 'Booked'
                )

        before = days[0] - datetime.timedelta(days=7)
        next_day = days[-1] + datetime.timedelta(days=1)

        context = {
            'store': store,
            'staff': staff,
            'calendar': calendar,
            'days': days,
            'start_day': start_day,
            'end_day': end_day,
            'before': before,
            'next': next_day,
            'today': today,
            'public_holidays': getattr(settings, 'PUBLIC_HOLIDAYS', []),
            'time_slots': time_slots_list,
            'slot_duration': duration,
            'api_key': api_key,
        }
        response = TemplateResponse(
            request, 'booking/embed/staff_calendar.html', context)
        return self.build_csp_header(store, response)


@method_decorator(xframe_options_exempt, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class EmbedPreBookingView(EmbedAuthMixin, View):
    """iframe内予約確認 → embed_token付きSchedule生成"""

    def get(self, request, store_id, pk, year, month, day, hour, minute=0):
        store, error_response = self.check_embed_auth(request, store_id)
        if error_response:
            return error_response

        staff = get_object_or_404(Staff, pk=pk)
        api_key = request.GET.get('api_key', '')
        _, _, _, duration = get_time_slots(store)

        context = {
            'store': store,
            'staff': staff,
            'year': year,
            'month': month,
            'day': day,
            'hour': hour,
            'minute': minute,
            'duration': duration,
            'api_key': api_key,
        }
        response = TemplateResponse(
            request, 'booking/embed/prebooking.html', context)
        return self.build_csp_header(store, response)

    def post(self, request, store_id, pk, year, month, day, hour, minute=0):
        store, error_response = self.check_embed_auth(request, store_id)
        if error_response:
            return error_response

        staff = get_object_or_404(Staff, pk=pk)
        api_key = request.GET.get('api_key', '')

        tz = pytz.timezone(settings.TIME_ZONE)
        start = tz.localize(datetime.datetime(
            year=year, month=month, day=day, hour=hour, minute=minute))
        _, _, _, duration = get_time_slots(store)
        end = start + datetime.timedelta(minutes=duration)

        # 二重予約チェック
        if Schedule.objects.filter(
            staff=staff, start=start, is_cancelled=False,
        ).exists():
            context = {
                'store': store,
                'staff': staff,
                'error': '入れ違いで予約が入りました。別の日時をお選びください。',
                'api_key': api_key,
            }
            response = TemplateResponse(
                request, 'booking/embed/prebooking.html', context)
            return self.build_csp_header(store, response)

        embed_token = secrets.token_urlsafe(32)
        schedule = Schedule(
            staff=staff,
            store=store,
            start=start,
            end=end,
            is_temporary=True,
            price=staff.price,
            temporary_booked_at=datetime.datetime.now(tz),
            embed_token=embed_token,
        )
        schedule.save()

        return redirect(
            f'/embed/channel-choice/{embed_token}/?api_key={api_key}')


@method_decorator(xframe_options_exempt, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class EmbedChannelChoiceView(EmbedAuthMixin, EmbedTokenMixin, View):
    """LINE / メール選択画面"""

    def get(self, request, embed_token):
        schedule = self.get_embed_schedule(embed_token)
        if not schedule:
            return TemplateResponse(
                request, 'booking/embed/expired.html', status=410)

        api_key = request.GET.get('api_key', '')
        store = schedule.get_store()
        tz_jst = pytz.timezone('Asia/Tokyo')
        start_display = timezone.localtime(
            schedule.start, tz_jst).strftime('%Y年%m月%d日 %H:%M')

        context = {
            'schedule': schedule,
            'store': store,
            'staff': schedule.staff,
            'embed_token': embed_token,
            'start_display': start_display,
            'api_key': api_key,
        }
        response = TemplateResponse(
            request, 'booking/embed/channel_choice.html', context)
        return self.build_csp_header(store, response)


@method_decorator(xframe_options_exempt, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class EmbedEmailBookingView(EmbedTokenMixin, View):
    """メールアドレス+名前入力 → OTP送信"""

    def get(self, request, embed_token):
        schedule = self.get_embed_schedule(embed_token)
        if not schedule:
            return TemplateResponse(
                request, 'booking/embed/expired.html', status=410)

        api_key = request.GET.get('api_key', '')
        context = {
            'embed_token': embed_token,
            'schedule': schedule,
            'staff': schedule.staff,
            'api_key': api_key,
        }
        return TemplateResponse(
            request, 'booking/embed/email_form.html', context)

    def post(self, request, embed_token):
        schedule = self.get_embed_schedule(embed_token)
        if not schedule:
            return TemplateResponse(
                request, 'booking/embed/expired.html', status=410)

        api_key = request.GET.get('api_key', '')
        customer_name = request.POST.get('customer_name', '').strip()
        customer_email = request.POST.get('customer_email', '').strip()

        error = None
        if not customer_name or not customer_email:
            error = 'お名前とメールアドレスを入力してください。'
        elif customer_email:
            try:
                validate_email(customer_email)
            except ValidationError:
                error = 'メールアドレスの形式が正しくありません。'

        if error:
            context = {
                'embed_token': embed_token,
                'schedule': schedule,
                'staff': schedule.staff,
                'api_key': api_key,
                'error': error,
                'customer_name': customer_name,
                'customer_email': customer_email,
            }
            return TemplateResponse(
                request, 'booking/embed/email_form.html', context)

        # OTP生成
        otp = f"{secrets.randbelow(1000000):06d}"
        otp_hash = hashlib.sha256(otp.encode('utf-8')).hexdigest()
        otp_expires = timezone.now() + datetime.timedelta(minutes=10)

        schedule.customer_name = customer_name
        schedule.customer_email = customer_email
        schedule.email_otp_hash = otp_hash
        schedule.email_otp_expires = otp_expires
        schedule.booking_channel = 'email'
        schedule.save(update_fields=[
            'customer_name', 'customer_email',
            'email_otp_hash', 'email_otp_expires', 'booking_channel',
        ])

        # OTPメール送信
        try:
            send_mail(
                subject='予約認証コード',
                message=(
                    f'{customer_name}様\n\n'
                    f'ご予約の認証コードは {otp} です。\n'
                    f'10分以内にご入力ください。'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[customer_email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error('OTPメール送信失敗(embed): %s', e)
            context = {
                'embed_token': embed_token,
                'schedule': schedule,
                'staff': schedule.staff,
                'api_key': api_key,
                'error': 'メール送信に失敗しました。もう一度お試しください。',
                'customer_name': customer_name,
                'customer_email': customer_email,
            }
            return TemplateResponse(
                request, 'booking/embed/email_form.html', context)

        return redirect(
            f'/embed/email/{embed_token}/verify/?api_key={api_key}')


@method_decorator(xframe_options_exempt, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class EmbedEmailVerifyView(EmbedTokenMixin, View):
    """OTP認証 → 予約確定 or 決済URL送信"""

    def get(self, request, embed_token):
        schedule = self.get_embed_schedule(embed_token)
        if not schedule:
            return TemplateResponse(
                request, 'booking/embed/expired.html', status=410)

        api_key = request.GET.get('api_key', '')
        context = {
            'embed_token': embed_token,
            'email': schedule.customer_email,
            'api_key': api_key,
        }
        return TemplateResponse(
            request, 'booking/embed/email_verify.html', context)

    def post(self, request, embed_token):
        schedule = self.get_embed_schedule(embed_token)
        if not schedule:
            return TemplateResponse(
                request, 'booking/embed/expired.html', status=410)

        api_key = request.GET.get('api_key', '')
        otp_input = request.POST.get('otp', '').strip()
        otp_hash_input = hashlib.sha256(otp_input.encode('utf-8')).hexdigest()

        # ハッシュ照合
        if otp_hash_input != schedule.email_otp_hash:
            context = {
                'embed_token': embed_token,
                'email': schedule.customer_email,
                'api_key': api_key,
                'error': '認証コードが正しくありません。',
            }
            return TemplateResponse(
                request, 'booking/embed/email_verify.html', context)

        # 有効期限チェック
        if (schedule.email_otp_expires
                and timezone.now() > schedule.email_otp_expires):
            context = {
                'embed_token': embed_token,
                'email': schedule.customer_email,
                'api_key': api_key,
                'error': '認証コードの有効期限が切れています。',
            }
            return TemplateResponse(
                request, 'booking/embed/email_verify.html', context)

        schedule.email_verified = True
        schedule.save(update_fields=['email_verified'])

        # 無料の場合は即確定
        if schedule.price == 0:
            schedule.is_temporary = False
            schedule.save(update_fields=['is_temporary'])
            return TemplateResponse(
                request, 'booking/embed/booking_complete.html', {
                    'schedule': schedule,
                    'api_key': api_key,
                })

        # 有料: Coiney決済URL生成
        payment_url = _create_coiney_payment(schedule)

        if payment_url:
            schedule.payment_url = payment_url
            schedule.save(update_fields=['payment_url'])

            # 決済URLメール送信
            try:
                send_mail(
                    subject='予約決済のご案内',
                    message=(
                        f'{schedule.customer_name}様\n\n'
                        f'以下のURLから決済を行ってください。\n'
                        f'{payment_url}\n\n'
                        f'15分以内にお支払いがない場合、'
                        f'仮予約は自動キャンセルされます。'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[schedule.customer_email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error('決済URLメール送信失敗(embed): %s', e)

        return TemplateResponse(
            request, 'booking/embed/email_payment_sent.html', {
                'customer_email': schedule.customer_email,
                'customer_name': schedule.customer_name,
                'payment_url_sent': bool(payment_url),
                'api_key': api_key,
            })


@method_decorator(xframe_options_exempt, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class EmbedLineRedirectView(EmbedTokenMixin, View):
    """embed_token → セッションに移行 → LINE OAuthへ（新タブで開く前提）"""

    def get(self, request, embed_token):
        schedule = self.get_embed_schedule(embed_token)
        if not schedule:
            return TemplateResponse(
                request, 'booking/embed/expired.html', status=410)

        tz_jst = pytz.timezone('Asia/Tokyo')
        start_display = timezone.localtime(
            schedule.start, tz_jst).strftime('%Y年%m月%d日 %H:%M')

        # セッションに仮予約情報をコピー（新タブなのでCookie正常動作）
        request.session['temporary_booking'] = {
            'reservation_number': str(schedule.reservation_number),
            'start': schedule.start.isoformat(),
            'start_display': start_display,
            'end': schedule.end.isoformat(),
            'price': schedule.price,
            'is_temporary': True,
            'staff_id': schedule.staff_id,
            'staff_name': schedule.staff.name,
            'store_id': schedule.store_id,
        }

        # embed_token付きScheduleは削除（セッション側で管理）
        schedule.delete()

        return redirect('booking:line_enter')


def _create_coiney_payment(schedule):
    """Coiney決済URLを生成。失敗時はNone。"""
    payment_api_url = getattr(settings, 'PAYMENT_API_URL', '')
    payment_api_key = getattr(settings, 'PAYMENT_API_KEY', '')
    if not payment_api_url or not payment_api_key:
        return None

    now = timezone.now()
    expired_on = (now + datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    reservation_number = schedule.reservation_number
    webhook_token = getattr(settings, 'COINEY_WEBHOOK_TOKEN', '')
    _wh_token = f"?token={webhook_token}" if webhook_token else ""
    webhook_url_base = getattr(settings, 'WEBHOOK_URL_BASE', '')
    webhook_url = f"{webhook_url_base}{reservation_number}/{_wh_token}"

    headers = {
        'Authorization': f'Bearer {payment_api_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-CoineyPayge-Version': '2016-10-25',
    }
    data = {
        "amount": int(schedule.price),
        "currency": "jpy",
        "locale": "ja_JP",
        "cancelUrl": getattr(settings, 'CANCEL_URL', ''),
        "webhookUrl": webhook_url,
        "method": "creditcard",
        "subject": "ご予約料金",
        "description": "ウェブサイトからの支払い",
        "remarks": "仮予約から15分を過ぎますと自動的にキャンセルとなります。",
        "metadata": {"orderId": str(reservation_number)},
        "expiredOn": expired_on,
    }

    try:
        resp = requests.post(
            payment_api_url, headers=headers, data=json.dumps(data),
            timeout=10)
        if resp.status_code == 201:
            return resp.json()['links']['paymentUrl']
    except Exception as e:
        logger.error('Coiney決済URL取得失敗(embed): %s', e)
    return None
