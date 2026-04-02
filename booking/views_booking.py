"""Booking flow views: LINE auth, email booking, payment processing,
cancel reservation, QR checkin, and related helpers."""
import datetime
import hashlib
import hmac as _hmac
import json
import logging
import secrets
import urllib.parse
from urllib.parse import quote

import jwt
import pytz
import requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.mail import send_mail
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django import forms

from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage

from booking.models import Schedule, Staff, Store

logger = logging.getLogger(__name__)


# ===== LINE settings helpers =====

def _get_line_setting(name):
    """LINE設定値を取得。未設定の場合はエラーを発生させる。"""
    value = getattr(settings, name, None)
    if not value:
        raise ImproperlyConfigured(
            f"settings.{name} が設定されていません。.envファイルを確認してください。"
        )
    return value


class _LazyLineSetting:
    """Descriptor that defers _get_line_setting() to first access."""
    def __init__(self, setting_name):
        self._setting_name = setting_name
        self._value = None
        self._resolved = False

    def __call__(self):
        if not self._resolved:
            self._value = _get_line_setting(self._setting_name)
            self._resolved = True
        return self._value


_lazy_line_channel_id = _LazyLineSetting('LINE_CHANNEL_ID')
_lazy_line_channel_secret = _LazyLineSetting('LINE_CHANNEL_SECRET')
_lazy_line_redirect_url = _LazyLineSetting('LINE_REDIRECT_URL')


def get_line_channel_id():
    return _lazy_line_channel_id()


def get_line_channel_secret():
    return _lazy_line_channel_secret()


def get_line_redirect_url():
    return _lazy_line_redirect_url()


# ===== LINE auth views =====

class LineEnterView(View):
    def get(self, request):
        state = secrets.token_hex(10)
        request.session['state'] = state

        params = {
            'response_type': 'code',
            'client_id': get_line_channel_id(),
            'redirect_uri': get_line_redirect_url(),
            'state': state,
            'scope': 'openid profile email',
            'bot_prompt': 'aggressive',
        }
        auth_url = 'https://access.line.me/oauth2/v2.1/authorize?' + urllib.parse.urlencode(params)
        return HttpResponseRedirect(auth_url)


class LineCallbackView(View):
    def get(self, request):
        code = request.GET.get('code')
        state = request.GET.get('state')

        if state != request.session.get('state'):
            return HttpResponseBadRequest()

        if code is None:
            return HttpResponse('トークンの取得に失敗しました')

        uri_access_token = "https://api.line.me/oauth2/v2.1/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data_params = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": get_line_redirect_url(),
            "client_id": get_line_channel_id(),
            "client_secret": get_line_channel_secret()
        }
        response_post = requests.post(uri_access_token, headers=headers, data=data_params)

        if response_post.status_code != 200:
            logger.error('LINE token exchange failed: %s %s', response_post.status_code, response_post.text)
            return HttpResponse('トークンの取得に失敗しました。しばらく後でお試しください。')

        try:
            line_id_token = json.loads(response_post.text)["id_token"]
        except (json.JSONDecodeError, KeyError) as e:
            logger.error('LINE token response parse error: %s', e)
            return HttpResponse('トークンの取得に失敗しました。しばらく後でお試しください。')

        user_profile = jwt.decode(
            line_id_token,
            get_line_channel_secret(),
            audience=get_line_channel_id(),
            issuer='https://access.line.me',
            algorithms=['HS256'],
            options={'verify_iat': False}
        )

        customer_name = user_profile.get('name') if user_profile else 'Unknown User'
        hashed_id = hashlib.sha256(user_profile['sub'].encode()).hexdigest()

        line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
        user_id = user_profile['sub']

        is_friend = True
        try:
            profile = line_bot_api.get_profile(user_id)
            user_id = profile.user_id
        except LineBotApiError as e:
            if getattr(e, "status_code", None) == 404:
                is_friend = False
                logger.info("LINE user %s is not a friend, proceeding with web fallback", user_id[:8])
            else:
                logger.error("LINE get_profile failed: %s", e)
                return HttpResponseBadRequest()

        try:
            from datetime import datetime as dt, timedelta as td
            now = timezone.now()
            expired_on = now + td(days=1)
            expired_on_str = expired_on.strftime('%Y-%m-%d')

            temporary_booking = request.session.get('temporary_booking')
            if temporary_booking is None:
                return HttpResponse('仮予約情報がありません')

            schedule = Schedule(
                reservation_number=temporary_booking['reservation_number'],
                start=timezone.make_aware(dt.fromisoformat(temporary_booking['start'])),
                end=timezone.make_aware(dt.fromisoformat(temporary_booking['end'])),
                price=temporary_booking['price'],
                customer_name=customer_name,
                hashed_id=hashed_id,
                staff_id=temporary_booking['staff_id'],
                is_temporary=True,
                temporary_booked_at=timezone.now(),
            )
            schedule.save()

            # 生のLINE user_idは保存しない（暗号化+ハッシュで保存）
            try:
                schedule.set_line_user_id(user_id)
                schedule.save(update_fields=["line_user_hash", "line_user_enc"])
            except Exception as e:
                logger.warning("Failed to store encrypted LINE user id: %s", e)

            del request.session['temporary_booking']

            reservation_number = schedule.reservation_number

            if int(schedule.price) >= 100:
                # 有料予約: Coiney で決済URL を発行
                payment_api_url = settings.PAYMENT_API_URL
                pay_headers = {
                    'Authorization': 'Bearer ' + settings.PAYMENT_API_KEY,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CoineyPayge-Version': '2016-10-25',
                }
                _wh_token = f"?token={settings.COINEY_WEBHOOK_TOKEN}" if settings.COINEY_WEBHOOK_TOKEN else ""
                webhook_url = f"{settings.WEBHOOK_URL_BASE}{reservation_number}/{_wh_token}"

                data = {
                    "amount": int(schedule.price),
                    "currency": "jpy",
                    "locale": "ja_JP",
                    "cancelUrl": settings.CANCEL_URL,
                    "webhookUrl": webhook_url,
                    "method": "creditcard",
                    "subject": "ご予約料金",
                    "description": "ウェブサイトからの支払い",
                    "remarks": "仮予約から15分を過ぎますと自動的にキャンセルとなります。あらかじめご了承ください。",
                    "metadata": {"orderId": reservation_number},
                    "expiredOn": expired_on_str
                }

                response = requests.post(payment_api_url, headers=pay_headers, data=json.dumps(data))
                payment_url = None
                if response.status_code == 201:
                    try:
                        payment_url = response.json()['links']['paymentUrl']
                    except (ValueError, KeyError) as e:
                        logger.error("Coiny response JSON parse error: %s, body=%s", e, response.text)
                else:
                    logger.error("Coiny API failed: status=%s, body=%s", response.status_code, response.text)

                if is_friend and payment_url is not None:
                    line_bot_api.push_message(
                        user_id,
                        TextSendMessage(
                            text='こちらのURLから決済を行ってください。決済後に予約が確定します。\n'
                                 '15分以内にお支払いがない場合、仮予約は自動キャンセルされます。\n'
                                 + payment_url
                                 + '\n\n※ キャンセル時の返金は店舗スタッフが対応いたします。'
                                 + '\n処理にお時間をいただく場合がございます。'
                        )
                    )
                elif not is_friend and payment_url is not None:
                    # 非友達: Webページで決済URLを表示
                    return self._render_not_friend_page(
                        request, schedule, user_profile,
                        payment_url=payment_url,
                    )
                else:
                    logger.error("Payment URL not obtained for reservation %s", reservation_number)
            else:
                # 無料予約（price=0）: 決済不要、直接確定
                schedule.is_temporary = False
                schedule.save(update_fields=['is_temporary'])

                # 署名付きQR + バックアップコード生成
                from booking.services.checkin_token import (
                    generate_backup_code as _gen_backup,
                    generate_signed_checkin_qr as _gen_qr,
                )
                backup_code = None
                try:
                    staff_obj = Staff.objects.select_related('store').get(pk=schedule.staff_id)
                    qr_file = _gen_qr(str(schedule.reservation_number), schedule.end)
                    schedule.checkin_qr.save(qr_file.name, qr_file, save=True)
                    backup_code = _gen_backup(staff_obj.store, schedule.start.date())
                    Schedule.objects.filter(pk=schedule.pk).update(
                        checkin_backup_code=backup_code,
                    )
                except Exception as e:
                    logger.warning('無料予約QR/バックアップコード生成エラー: %s', e)

                # キャスト（スタッフ）通知
                from booking.services.staff_notifications import notify_booking_to_staff
                notify_booking_to_staff(schedule)

                if is_friend:
                    # 顧客LINE通知（予約情報 + QR/バックアップコード）
                    local_tz = pytz.timezone('Asia/Tokyo')
                    local_start = schedule.start.astimezone(local_tz)
                    local_end = schedule.end.astimezone(local_tz)
                    qr_page_url = (
                        f'{settings.SITE_BASE_URL}/reservation/'
                        f'{reservation_number}/qr/'
                    )
                    cancel_page_url = (
                        f'{settings.SITE_BASE_URL}/cancel/{reservation_number}/'
                    )
                    staff_obj = Staff.objects.select_related('store').get(pk=schedule.staff_id)
                    store = staff_obj.store
                    access_lines = _build_access_lines(store)
                    checkin_line = ''
                    if backup_code:
                        checkin_line = (
                            f'\n\n■ チェックイン'
                            f'\nQRコード: {qr_page_url}'
                            f'\n口頭確認コード: {backup_code}'
                            f'\n（QRが読み取れない場合、スタッフにこの6桁コードをお伝えください）'
                        )
                    duration_min = int((schedule.end - schedule.start).total_seconds() // 60)
                    line_bot_api.push_message(
                        user_id,
                        TextSendMessage(
                            text=f'【予約確定】ご予約が確定しました。'
                                 f'\n\n■ 予約情報'
                                 f'\n予約番号: {reservation_number}'
                                 f'\n日時: {local_start.strftime("%Y年%m月%d日 %H:%M")}〜{local_end.strftime("%H:%M")}（{duration_min}分）'
                                 f'\n担当: {staff_obj.name}'
                                 + checkin_line
                                 + access_lines
                                 + f'\n\n■ キャンセル'
                                 + f'\nキャンセル番号: {schedule.cancel_token}'
                                 + f'\n{cancel_page_url}'
                                 + f'\n（上記URLでキャンセル番号を入力してください）'
                        )
                    )
                else:
                    # 非友達: Webページで QR/バックアップコード表示
                    return self._render_not_friend_page(
                        request, schedule, user_profile,
                        backup_code=backup_code,
                    )

        except LineBotApiError as e:
            logger.error("Failed to send LINE message: %s", e)

        request.session['profile'] = user_profile
        return render(request, 'booking/line_success.html', {'profile': user_profile})

    @staticmethod
    def _render_not_friend_page(request, schedule, user_profile, payment_url=None, backup_code=None):
        """非友達ユーザー向けWebページを表示。"""
        local_tz = pytz.timezone('Asia/Tokyo')
        local_start = schedule.start.astimezone(local_tz)
        local_end = schedule.end.astimezone(local_tz)
        duration_min = int((schedule.end - schedule.start).total_seconds() // 60)

        qr_page_url = None
        if not schedule.is_temporary:
            qr_page_url = (
                f'{settings.SITE_BASE_URL}/reservation/'
                f'{schedule.reservation_number}/qr/'
            )

        line_bot_id = getattr(settings, 'LINE_BOT_ID', '')
        friend_add_url = f'https://line.me/R/ti/p/@{line_bot_id}' if line_bot_id else ''

        request.session['profile'] = user_profile
        return render(request, 'booking/line_not_friend.html', {
            'reservation_number': schedule.reservation_number,
            'start_display': f'{local_start.strftime("%Y年%m月%d日 %H:%M")}〜{local_end.strftime("%H:%M")}（{duration_min}分）',
            'staff_name': schedule.staff.name,
            'price': schedule.price,
            'payment_url': payment_url,
            'qr_page_url': qr_page_url,
            'backup_code': backup_code,
            'cancel_token': schedule.cancel_token if not schedule.is_temporary else None,
            'friend_add_url': friend_add_url,
            'profile': user_profile,
        })


class PayingSuccessView(View):
    """決済成功処理 -- coiney_webhookからのみ呼び出されることを想定"""
    _called_from_webhook = False

    def post(self, request, orderId):
        if not self._called_from_webhook:
            logger.warning('PayingSuccessView: webhookを経由せず直接呼び出されました')
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            payment_response = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        return process_payment(payment_response, request, orderId)


class LineSuccessView(View):
    def get(self, request):
        profile = request.session.get('profile')
        return render(request, 'booking/line_success.html', {'profile': profile})


# ===== Booking flow views =====

class EmailBookingForm(forms.Form):
    from django.utils.translation import gettext_lazy as _
    customer_name = forms.CharField(max_length=255, label=_('お名前'))
    customer_email = forms.EmailField(label=_('メールアドレス'))


class EmailBookingView(View):
    """メアド+名前入力 -> OTP送信"""

    def get(self, request):
        form = EmailBookingForm()
        booking = request.session.get('temporary_booking')
        if not booking:
            return redirect('booking:booking_top')
        return render(request, 'booking/email_form.html', {'form': form, 'booking': booking})

    def post(self, request):
        form = EmailBookingForm(request.POST)
        booking = request.session.get('temporary_booking')
        if not booking:
            return redirect('booking:booking_top')

        if not form.is_valid():
            return render(request, 'booking/email_form.html', {'form': form, 'booking': booking})

        customer_name = form.cleaned_data['customer_name']
        customer_email = form.cleaned_data['customer_email']

        # 6桁OTP生成
        otp = f"{secrets.randbelow(1000000):06d}"
        otp_hash = hashlib.sha256(otp.encode('utf-8')).hexdigest()
        otp_expires = timezone.now() + datetime.timedelta(minutes=10)

        # セッションに保存
        request.session['email_booking'] = {
            'customer_name': customer_name,
            'customer_email': customer_email,
            'otp_hash': otp_hash,
            'otp_expires': otp_expires.isoformat(),
        }

        # OTPメール送信
        try:
            send_mail(
                subject='予約認証コード',
                message=f'{customer_name}様\n\nご予約の認証コードは {otp} です。\n10分以内にご入力ください。',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[customer_email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error('OTPメール送信失敗: %s', e)
            messages.error(request, 'メール送信に失敗しました。もう一度お試しください。')
            return render(request, 'booking/email_form.html', {'form': form, 'booking': booking})

        return redirect('booking:email_verify')


class EmailVerifyView(View):
    """OTP入力 -> 認証 -> 仮予約作成 -> 決済URL送信"""

    def get(self, request):
        email_booking = request.session.get('email_booking')
        if not email_booking:
            return redirect('booking:booking_top')
        return render(request, 'booking/email_verify.html', {'email': email_booking['customer_email']})

    def post(self, request):
        email_booking = request.session.get('email_booking')
        temporary_booking = request.session.get('temporary_booking')

        if not email_booking or not temporary_booking:
            return redirect('booking:booking_top')

        otp_input = request.POST.get('otp', '').strip()
        otp_hash_input = hashlib.sha256(otp_input.encode('utf-8')).hexdigest()

        # ハッシュ照合
        if otp_hash_input != email_booking['otp_hash']:
            messages.error(request, '認証コードが正しくありません。')
            return render(request, 'booking/email_verify.html', {'email': email_booking['customer_email']})

        # 有効期限チェック
        from datetime import datetime as dt
        otp_expires = dt.fromisoformat(email_booking['otp_expires'])
        if timezone.is_naive(otp_expires):
            otp_expires = timezone.make_aware(otp_expires)
        if timezone.now() > otp_expires:
            messages.error(request, '認証コードの有効期限が切れています。もう一度やり直してください。')
            return redirect('booking:email_booking')

        # 仮予約作成
        schedule = Schedule(
            reservation_number=temporary_booking['reservation_number'],
            start=timezone.make_aware(dt.fromisoformat(temporary_booking['start'])),
            end=timezone.make_aware(dt.fromisoformat(temporary_booking['end'])),
            price=temporary_booking['price'],
            customer_name=email_booking['customer_name'],
            staff_id=temporary_booking['staff_id'],
            is_temporary=True,
            temporary_booked_at=timezone.now(),
            booking_channel='email',
            customer_email=email_booking['customer_email'],
            email_verified=True,
        )
        schedule.save()

        # Coiney決済URL取得
        from datetime import timedelta as td
        now = timezone.now()
        expired_on = now + td(days=1)
        expired_on_str = expired_on.strftime('%Y-%m-%d')

        payment_api_url = settings.PAYMENT_API_URL
        pay_headers = {
            'Authorization': 'Bearer ' + settings.PAYMENT_API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-CoineyPayge-Version': '2016-10-25',
        }
        reservation_number = schedule.reservation_number
        _wh_token = f"?token={settings.COINEY_WEBHOOK_TOKEN}" if settings.COINEY_WEBHOOK_TOKEN else ""
        webhook_url = f"{settings.WEBHOOK_URL_BASE}{reservation_number}/{_wh_token}"

        data = {
            "amount": int(schedule.price),
            "currency": "jpy",
            "locale": "ja_JP",
            "cancelUrl": settings.CANCEL_URL,
            "webhookUrl": webhook_url,
            "method": "creditcard",
            "subject": "ご予約料金",
            "description": "ウェブサイトからの支払い",
            "remarks": "仮予約から15分を過ぎますと自動的にキャンセルとなります。あらかじめご了承ください。",
            "metadata": {"orderId": str(reservation_number)},
            "expiredOn": expired_on_str,
        }

        payment_url = None
        try:
            response = requests.post(payment_api_url, headers=pay_headers, data=json.dumps(data))
            if response.status_code == 201:
                payment_url = response.json()['links']['paymentUrl']
        except Exception as e:
            logger.error('決済URL取得失敗: %s', e)

        if payment_url:
            schedule.payment_url = payment_url
            schedule.save(update_fields=['payment_url'])

            # メールで決済URL送信
            try:
                send_mail(
                    subject='予約決済のご案内',
                    message=(
                        f'{email_booking["customer_name"]}様\n\n'
                        f'以下のURLから決済を行ってください。\n'
                        f'{payment_url}\n\n'
                        f'15分以内にお支払いがない場合、仮予約は自動キャンセルされます。\n'
                        f'あらかじめご了承ください。'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email_booking['customer_email']],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error('決済URLメール送信失敗: %s', e)

        # セッションクリア
        del request.session['temporary_booking']
        del request.session['email_booking']

        return render(request, 'booking/email_payment_sent.html', {
            'customer_email': email_booking['customer_email'],
            'customer_name': email_booking['customer_name'],
            'payment_url_sent': bool(payment_url),
        })


# ===== Customer Cancel (public, no login required) =====

@method_decorator(csrf_exempt, name='dispatch')
class CustomerCancelView(View):
    """公開キャンセルページ（認証不要）。cancel_tokenで保護されるためCSRF exempt。"""

    def get(self, request, reservation_number):
        schedule = get_object_or_404(
            Schedule, reservation_number=reservation_number, is_temporary=False,
        )
        if schedule.is_cancelled:
            return render(request, 'booking/customer_cancel_form.html', {
                'error': 'この予約は既にキャンセル済みです。',
            })
        return render(request, 'booking/customer_cancel_form.html')

    def post(self, request, reservation_number):
        schedule = get_object_or_404(
            Schedule, reservation_number=reservation_number, is_temporary=False,
        )
        if schedule.is_cancelled:
            return render(request, 'booking/customer_cancel_form.html', {
                'error': 'この予約は既にキャンセル済みです。',
            })

        cancel_token_input = request.POST.get('cancel_token', '').strip().upper()
        if not cancel_token_input or not _hmac.compare_digest(
            cancel_token_input, schedule.cancel_token or '',
        ):
            return render(request, 'booking/customer_cancel_form.html', {
                'error': 'キャンセル番号が正しくありません。',
            })

        # 検証OK→確認画面
        return render(request, 'booking/customer_cancel_confirm.html', {
            'schedule': schedule,
            'cancel_token': cancel_token_input,
        })


@method_decorator(csrf_exempt, name='dispatch')
class CustomerCancelConfirmView(View):
    """キャンセル実行（POST only）。cancel_tokenで保護されるためCSRF exempt。"""

    def get(self, request, reservation_number):
        """GET アクセスはキャンセルフォームにリダイレクト。"""
        return redirect('booking:customer_cancel', reservation_number=reservation_number)

    def post(self, request, reservation_number):
        schedule = get_object_or_404(
            Schedule,
            reservation_number=reservation_number,
            is_temporary=False,
        )
        if schedule.is_cancelled:
            return render(request, 'booking/customer_cancel_done.html', {
                'schedule': schedule,
            })

        cancel_token_input = request.POST.get('cancel_token', '').strip().upper()
        if not cancel_token_input or not _hmac.compare_digest(
            cancel_token_input, schedule.cancel_token or '',
        ):
            return render(request, 'booking/customer_cancel_form.html', {
                'error': 'キャンセル番号が正しくありません。',
            })

        # キャンセル実行
        Schedule.objects.filter(pk=schedule.pk).update(is_cancelled=True)
        schedule.is_cancelled = True

        # 1. 管理者メール通知（返金対応依頼）
        self._notify_admin_email(schedule)

        # 2. 顧客にLINEキャンセル完了メッセージ
        self._notify_customer_line(schedule)

        # 3. スタッフにLINEキャンセル通知
        self._notify_staff_line(schedule)

        return render(request, 'booking/customer_cancel_done.html', {
            'schedule': schedule,
        })

    @staticmethod
    def _notify_admin_email(schedule):
        """管理者に返金対応依頼メールを送信。"""
        try:
            notification_emails = getattr(settings, 'NOTIFICATION_EMAILS', [])
            if not notification_emails:
                admin_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
                notification_emails = [admin_email] if admin_email else []
            if not notification_emails:
                return

            local_tz = pytz.timezone('Asia/Tokyo')
            local_start = schedule.start.astimezone(local_tz)

            refund_note = ''
            if schedule.price and int(schedule.price) >= 100:
                refund_note = (
                    '\n\n【要対応】決済済み予約のキャンセルです。'
                    '\nSTORES管理画面から手動返金を行ってください。'
                    f'\n返金金額: {schedule.price:,}円'
                )

            send_mail(
                subject=f'[要対応] 予約キャンセル - {schedule.reservation_number}',
                message=(
                    f'顧客がオンラインで予約をキャンセルしました。\n\n'
                    f'予約番号: {schedule.reservation_number}\n'
                    f'顧客名: {schedule.customer_name or "不明"}\n'
                    f'日時: {local_start.strftime("%Y年%m月%d日 %H:%M")}\n'
                    f'担当: {schedule.staff.name}\n'
                    f'料金: {schedule.price:,}円'
                    + refund_note
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=notification_emails,
                fail_silently=True,
            )
        except Exception as e:
            logger.warning('CustomerCancelConfirmView: 管理者メール通知に失敗: %s', e)

    @staticmethod
    def _notify_customer_line(schedule):
        """顧客にLINEでキャンセル完了通知。"""
        try:
            user_id = schedule.get_line_user_id()
            if not user_id:
                return
            local_tz = pytz.timezone('Asia/Tokyo')
            local_start = schedule.start.astimezone(local_tz)
            refund_line = ''
            if schedule.price and int(schedule.price) >= 100:
                refund_line = '\n\n返金は店舗スタッフが対応いたします。処理完了後にご連絡いたします。'
            line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
            line_bot_api.push_message(
                user_id,
                TextSendMessage(
                    text=(
                        f'【キャンセル完了】ご予約のキャンセルが完了しました。'
                        f'\n\n予約番号: {schedule.reservation_number}'
                        f'\n日時: {local_start.strftime("%Y年%m月%d日 %H:%M")}'
                        f'\n担当: {schedule.staff.name}'
                        + refund_line
                    )
                ),
            )
        except Exception as e:
            logger.warning('CustomerCancelConfirmView: 顧客LINE通知に失敗: %s', e)

    @staticmethod
    def _notify_staff_line(schedule):
        """スタッフにLINEでキャンセル通知。"""
        try:
            staff_line_id = getattr(schedule.staff, 'line_id', None)
            if not staff_line_id:
                return
            local_tz = pytz.timezone('Asia/Tokyo')
            local_start = schedule.start.astimezone(local_tz)
            line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
            line_bot_api.push_message(
                staff_line_id,
                TextSendMessage(
                    text=(
                        f'【キャンセル通知】予約がキャンセルされました。'
                        f'\n顧客名: {schedule.customer_name or "不明"}'
                        f'\n日時: {local_start.strftime("%Y年%m月%d日 %H:%M")}'
                    )
                ),
            )
        except Exception as e:
            logger.warning('CustomerCancelConfirmView: スタッフLINE通知に失敗: %s', e)


# ===== Cancel (admin/staff, login required) =====

class CancelReservationView(LoginRequiredMixin, View):
    def post(self, request, schedule_id):
        schedule = get_object_or_404(Schedule, id=schedule_id)
        # 本人またはスタッフ/管理者のみキャンセル可能
        session_line_id = request.session.get('line_user_id', '')
        is_owner = bool(
            session_line_id
            and schedule.line_user_hash
            and schedule.line_user_hash == Schedule.make_line_user_hash(session_line_id)
        )
        is_staff_or_admin = (request.user.is_staff or request.user.is_superuser)
        if not is_owner and not is_staff_or_admin:
            raise PermissionDenied
        schedule.is_cancelled = True
        schedule.save(update_fields=["is_cancelled"])

        # スタッフ通知（任意）
        try:
            staff_line_account_id = schedule.staff.line_id
            if staff_line_account_id:
                line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
                local_tz = pytz.timezone('Asia/Tokyo')
                local_time = timezone.localtime(schedule.start, local_tz)
                line_bot_api.push_message(
                    staff_line_account_id,
                    TextSendMessage(text=f'予約がキャンセルされました。予約日時: {local_time}')
                )
        except Exception as e:
            logger.warning('CancelReservationView: スタッフLINE通知に失敗しました: %s', e)

        # 顧客通知（復号できる場合のみ）
        try:
            customer_user_id = schedule.get_line_user_id()
            if customer_user_id:
                line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
                local_tz = pytz.timezone('Asia/Tokyo')
                local_time = timezone.localtime(schedule.start, local_tz)
                line_bot_api.push_message(
                    customer_user_id,
                    TextSendMessage(text=f'あなたの予約がキャンセルされました。予約日時: {local_time}')
                )
        except Exception as e:
            logger.warning('CancelReservationView: 顧客LINE通知に失敗しました: %s', e)

        return render(request, 'booking/cancel_success.html', {"schedule": schedule})


# ===== Payment processing =====

def _build_access_lines(store):
    """店舗アクセス情報テキストを組み立てる。情報がなければ空文字を返す。"""
    parts = [
        f'\n\n■ 店舗アクセス',
        f'{store.name}',
        f'{store.address}',
    ]
    if store.nearest_station:
        parts.append(f'最寄り駅: {store.nearest_station}')
    if store.access_info:
        parts.append(store.access_info)
    if store.map_url:
        parts.append(f'地図: {store.map_url}')
    return '\n'.join(parts)


def process_payment(payment_response, request, order_id):
    if payment_response.get('type') == 'payment.succeeded':
        try:
            schedule = Schedule.objects.select_related('staff__store').get(reservation_number=order_id)
        except Schedule.DoesNotExist:
            logger.error("process_payment: Schedule not found for order_id=%s", order_id)
            return JsonResponse({"error": "reservation not found"}, status=404)
        schedule.is_temporary = False
        schedule.save(update_fields=["is_temporary"])

        # 署名付きQRコード + 6桁バックアップコード生成
        from booking.services.checkin_token import (
            generate_backup_code,
            generate_signed_checkin_qr,
        )
        if not schedule.checkin_qr:
            qr_file = generate_signed_checkin_qr(
                str(schedule.reservation_number), schedule.end,
            )
            schedule.checkin_qr.save(qr_file.name, qr_file, save=True)
        if not schedule.checkin_backup_code:
            backup_code = generate_backup_code(
                schedule.staff.store, schedule.start.date(),
            )
            Schedule.objects.filter(pk=schedule.pk).update(
                checkin_backup_code=backup_code,
            )
            schedule.checkin_backup_code = backup_code

        line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)

        # スタッフ通知（通知設定を尊重）
        from booking.services.staff_notifications import notify_booking_to_staff
        notify_booking_to_staff(schedule)

        # 顧客通知：Scheduleに保存した暗号化LINE user id を復号してpush
        user_id = None
        try:
            user_id = schedule.get_line_user_id()
        except Exception as e:
            logger.warning('Failed to decrypt LINE user id: %s', e)

        if user_id:
            local_tz = pytz.timezone('Asia/Tokyo')
            local_start = schedule.start.astimezone(local_tz)
            local_end = schedule.end.astimezone(local_tz)
            qr_page_url = (
                f'{settings.SITE_BASE_URL}/reservation/'
                f'{schedule.reservation_number}/qr/'
            )
            cancel_page_url = (
                f'{settings.SITE_BASE_URL}/cancel/{schedule.reservation_number}/'
            )
            store = schedule.staff.store
            access_lines = _build_access_lines(store)
            checkin_line = ''
            if schedule.checkin_backup_code:
                checkin_line = (
                    f'\n\n■ チェックイン'
                    f'\nQRコード: {qr_page_url}'
                    f'\n口頭確認コード: {schedule.checkin_backup_code}'
                    f'\n（QRが読み取れない場合、スタッフにこの6桁コードをお伝えください）'
                )
            duration_min = int((schedule.end - schedule.start).total_seconds() // 60)
            message_text = (
                f'【予約確定】決済が完了しました。'
                f'\n\n■ 予約情報'
                f'\n予約番号: {schedule.reservation_number}'
                f'\n日時: {local_start.strftime("%Y年%m月%d日 %H:%M")}〜{local_end.strftime("%H:%M")}（{duration_min}分）'
                f'\n担当: {schedule.staff.name}'
                f'\n料金: {schedule.price:,}円（決済済み）'
                + checkin_line
                + access_lines
                + f'\n\n■ キャンセル'
                + f'\nキャンセル番号: {schedule.cancel_token}'
                + f'\n{cancel_page_url}'
                + f'\n（上記URLでキャンセル番号を入力してください）'
                + f'\n※ 返金は店舗スタッフが対応いたします。処理にお時間をいただく場合がございます。'
            )
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=message_text))
            except LineBotApiError as e:
                logger.error('顧客向け決済完了メッセージにてLineBotApiErrorが発生しました: %s', e)

        # メール予約の場合: 決済完了メールを送信
        if schedule.booking_channel == 'email' and schedule.customer_email:
            local_tz = pytz.timezone('Asia/Tokyo')
            local_time = schedule.start.astimezone(local_tz)
            store = schedule.staff.store
            access_lines = _build_access_lines(store)
            email_qr_url = (
                f'{settings.SITE_BASE_URL}/reservation/'
                f'{schedule.reservation_number}/qr/'
            )
            email_backup = ''
            if schedule.checkin_backup_code:
                email_backup = (
                    f'\n\nチェックインQRコード: {email_qr_url}'
                    f'\n口頭確認コード: {schedule.checkin_backup_code}'
                    f'\n（QRが読み取れない場合、スタッフにこの6桁コードをお伝えください）'
                )
            email_cancel_url = (
                f'{settings.SITE_BASE_URL}/cancel/{schedule.reservation_number}/'
            )
            email_cancel_section = (
                f'\n\n■ キャンセル'
                f'\nキャンセル番号: {schedule.cancel_token}'
                f'\n{email_cancel_url}'
                f'\n（上記URLでキャンセル番号を入力してください）'
            )
            if int(schedule.price) >= 100:
                email_cancel_section += (
                    f'\n※ 返金は店舗スタッフが対応いたします。処理にお時間をいただく場合がございます。'
                )
            try:
                send_mail(
                    subject='予約確定のお知らせ',
                    message=(
                        f'{schedule.customer_name}様\n\n'
                        f'予約が確定しました。\n\n'
                        f'占い師: {schedule.staff.name}\n'
                        f'日時: {local_time.strftime("%Y年%m月%d日 %H:%M")}\n'
                        f'料金: {schedule.price}円'
                        + email_backup
                        + access_lines
                        + email_cancel_section
                        + f'\n\nご予約ありがとうございます。'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[schedule.customer_email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error('決済確定メール送信失敗 reservation=%s: %s', schedule.reservation_number, e)

    return JsonResponse({"status": "success"})


@csrf_exempt
def coiney_webhook(request, orderId):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if not request.content_type or not request.content_type.startswith('application/json'):
        return JsonResponse({"error": "Content-Type must be application/json"}, status=400)

    # Webhookトークン検証（URLクエリパラメータ方式）
    expected_token = getattr(settings, 'COINEY_WEBHOOK_TOKEN', '')
    if expected_token:
        import hmac as _hmac
        received_token = request.GET.get('token', '')
        if not _hmac.compare_digest(received_token, expected_token):
            logger.warning('coiney_webhook: トークン検証失敗 orderId=%s', orderId)
            return JsonResponse({"error": "Invalid token"}, status=403)
    else:
        logger.warning('coiney_webhook: COINEY_WEBHOOK_TOKEN 未設定。トークン検証をスキップします。')

    # リクエストヘッダーのログ出力（機密情報を除外）
    safe_meta = {k: v for k, v in request.META.items()
                 if k.startswith('HTTP_') and k not in ('HTTP_COOKIE', 'HTTP_AUTHORIZATION')}
    logger.info('coiney_webhook called: orderId=%s, headers=%s', orderId, safe_meta)

    if orderId:
        # EC注文の場合は専用ハンドラに委譲
        if orderId.startswith('ec_order_'):
            from .views_ec_payment import process_ec_payment
            return process_ec_payment(request, orderId)
        view = PayingSuccessView()
        view._called_from_webhook = True
        return view.post(request, orderId)
    return JsonResponse({"error": "orderId not found in request body"}, status=400)


# ===== QR Checkin views =====

class ReservationQRView(View):
    """予約確認 + QRコード表示ページ"""
    def get(self, request, reservation_number):
        schedule = get_object_or_404(
            Schedule,
            reservation_number=reservation_number,
            is_temporary=False,
            is_cancelled=False,
        )
        return render(request, 'booking/reservation_qr.html', {'schedule': schedule})


class CheckinScanView(LoginRequiredMixin, UserPassesTestMixin, View):
    """スタッフ用チェックインスキャンページ"""
    def test_func(self):
        return self.request.user.is_staff

    def get(self, request):
        return render(request, 'booking/checkin_scan.html')


class CheckinAPIView(APIView):
    """チェックイン API (POST: qr_token or backup_code)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from booking.services.checkin_token import (
            is_within_checkin_window,
            verify_qr_token,
        )

        qr_token = request.data.get('qr_token', '').strip()
        backup_code = request.data.get('backup_code', '').strip()

        if not qr_token and not backup_code:
            return Response(
                {'status': 'error', 'message': 'QRトークンまたはバックアップコードが必要です'},
                status=400,
            )

        schedule = None

        # --- QR token path ---
        if qr_token:
            valid, reservation_number, error = verify_qr_token(qr_token)
            if not valid:
                return Response(
                    {'status': 'error', 'message': error or 'QRコードが無効です'},
                    status=400,
                )
            try:
                schedule = Schedule.objects.select_related('staff__store').get(
                    reservation_number=reservation_number,
                    is_temporary=False,
                    is_cancelled=False,
                )
            except Schedule.DoesNotExist:
                return Response(
                    {'status': 'error', 'message': '有効な予約が見つかりません'},
                    status=404,
                )

        # --- Backup code path ---
        elif backup_code:
            staff = getattr(request.user, 'staff', None)
            if not staff and not request.user.is_superuser:
                return Response(
                    {'status': 'error', 'message': 'スタッフアカウントが必要です'},
                    status=403,
                )
            today = timezone.localdate()
            store_filter = {} if request.user.is_superuser else {'staff__store': staff.store}
            try:
                schedule = Schedule.objects.select_related('staff__store').get(
                    checkin_backup_code=backup_code,
                    start__date=today,
                    is_temporary=False,
                    is_cancelled=False,
                    is_checked_in=False,
                    **store_filter,
                )
            except Schedule.DoesNotExist:
                return Response(
                    {'status': 'error', 'message': '該当する予約が見つかりません'},
                    status=404,
                )
            except Schedule.MultipleObjectsReturned:
                return Response(
                    {'status': 'error', 'message': '複数の予約が該当しました。QRコードをご利用ください'},
                    status=400,
                )

        # --- Store scope check ---
        if not request.user.is_superuser:
            staff = getattr(request.user, 'staff', None)
            if staff and schedule.staff.store_id != staff.store_id:
                return Response(
                    {'status': 'error', 'message': '別店舗の予約はチェックインできません'},
                    status=403,
                )

        # --- Time window check ---
        if not is_within_checkin_window(schedule):
            return Response(
                {'status': 'error', 'message': 'チェックイン可能時間外です（予約開始30分前〜終了まで）'},
                status=400,
            )

        # --- Atomic checkin (prevents race condition) ---
        checked_in_by = getattr(request.user, 'staff', None)
        now = timezone.now()
        updated = Schedule.objects.filter(
            pk=schedule.pk,
            is_checked_in=False,
        ).update(
            is_checked_in=True,
            checked_in_at=now,
            checked_in_by=checked_in_by,
        )
        if not updated:
            return Response(
                {'status': 'error', 'message': 'すでにチェックイン済みです'},
                status=409,
            )

        # --- 顧客にチェックイン完了通知 ---
        self._notify_customer_checkin(schedule)

        return Response({
            'status': 'ok',
            'message': f'{schedule.customer_name or "お客様"} のチェックインが完了しました',
            'checked_in_at': now.isoformat(),
        })

    @staticmethod
    def _notify_customer_checkin(schedule):
        """チェックイン完了をLINEまたはメールで顧客に通知する。"""
        local_tz = pytz.timezone('Asia/Tokyo')
        local_time = schedule.start.astimezone(local_tz)
        message = (
            f'チェックインが完了しました。\n\n'
            f'占い師: {schedule.staff.name}\n'
            f'日時: {local_time.strftime("%Y/%m/%d %H:%M")}\n'
            f'ご来店ありがとうございます。'
        )

        # LINE通知
        try:
            user_id = schedule.get_line_user_id()
            if user_id:
                line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
                line_bot_api.push_message(
                    user_id, TextSendMessage(text=message),
                )
        except Exception as e:
            logger.warning('チェックイン完了LINE通知に失敗: %s', e)

        # メール通知
        if schedule.booking_channel == 'email' and schedule.customer_email:
            try:
                send_mail(
                    subject='チェックイン完了のお知らせ',
                    message=f'{schedule.customer_name}様\n\n{message}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[schedule.customer_email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.warning('チェックイン完了メール通知に失敗: %s', e)
