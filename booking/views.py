from __future__ import absolute_import, unicode_literals
import datetime
import json
import jwt
import requests
import secrets
from datetime import timedelta
from django.utils import timezone
from celery import shared_task
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import generic, View
from django.views.decorators.http import require_POST
from booking.models import Store, Staff, Schedule, Timer,UserSerializer
import sys
from rest_framework import generics
from django.contrib.auth.models import User

class UserList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
User = get_user_model()
class Index(generic.TemplateView):
    template_name = 'booking/index.html'

    
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render

def LINETimerView(request, user_id):
    # タイマーの開始時刻をデータベースに保存します
    timer, created = Timer.objects.get_or_create(user_id=user_id, defaults={'start_time': timezone.now()})

    if not created:
        # 既存のタイマーを更新する場合の処理
        timer.start_time = timezone.now()
        timer.save()

    # タイマーの終了時間を設定します（ここでは開始時間から10分後とします）
    timer.end_time = timer.start_time + timedelta(minutes=60)
    timer.save()

    # 終了時間をcontextに追加します
    context = {'end_time': timer.end_time}

    # timer.htmlテンプレートをレンダリングします
    return render(request, 'booking/timer.html', context)

# 終了時間を保存する変数
# ここではサーバー起動時から1時間後を終了時間としています
end_time = timezone.now() + timedelta(hours=1)

def get_end_time(request):
    # 終了時間をISO 8601形式の文字列として返す
    return JsonResponse({'time': end_time.isoformat()})

def get_current_time(request):
    # 現在時間をISO 8601形式の文字列として返す
    return JsonResponse({'time': timezone.now().isoformat()})

def get_reservation_times(request, pk):
    # pkを使用して予約を取得
    schedule = get_object_or_404(Schedule, pk=pk)
    # 開始時間と終了時間をISO 8601形式の文字列として返す
    return JsonResponse({'startTime': schedule.start.isoformat(), 'endTime': schedule.end.isoformat()})

def get_reservation(request, pk):
    # pkを使用して予約を取得
    schedule = get_object_or_404(Schedule, pk=pk)
    # 開始時間と終了時間をISO 8601形式の文字列として返す
    return JsonResponse({
        'startTime': schedule.start.isoformat(),
        'endTime': schedule.end.isoformat()
    })
     
class CurrentTimeView(APIView):
    def get(self, request):
        import datetime
        current_time = datetime.datetime.now()
        return Response({"current_time": str(current_time)})
    
    
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.views import View
import hashlib
import urllib.parse
import requests
import json
import jwt
from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
import requests

LINE_CHANNEL_ID =  settings.LINE_CHANNEL_ID
LINE_CHANNEL_SECRET = settings.LINE_CHANNEL_SECRET
LINE_REDIRECT_URL = settings.LINE_REDIRECT_URL

class LineEnterView(View):
    def get(self, request):
        # 認証URLを生成する
        state = secrets.token_hex(10)  # ランダムな文字列を生成
        request.session['state'] = state  # stateをセッションに保存

        params = {
            'response_type': 'code',
            'client_id': LINE_CHANNEL_ID,
            'redirect_uri':LINE_REDIRECT_URL,
            'state': state,
            'scope': 'openid profile email',
        }
        auth_url = 'https://access.line.me/oauth2/v2.1/authorize?' + urllib.parse.urlencode(params)

        # ユーザーをLINEログインページにリダイレクト
        return HttpResponseRedirect(auth_url)
    
from django.shortcuts import redirect, render
from django.http import HttpResponse, HttpResponseBadRequest
from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
import requests
import json
import hashlib
import jwt
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from linebot.models import FollowEvent, TextSendMessage
from linebot.exceptions import LineBotApiError
from linebot.exceptions import InvalidSignatureError
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden

class LineCallbackView(View):
    def get(self, request):
        context = {}
        code = request.GET.get('code')
        state = request.GET.get('state')

        if state != request.session.get('state'):
            return HttpResponseBadRequest("Invalid state parameter")

        uri_access_token = "https://api.line.me/oauth2/v2.1/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        if code is not None:
            data_params = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.LINE_REDIRECT_URL,
                "client_id": settings.LINE_CHANNEL_ID,
                "client_secret": settings.LINE_CHANNEL_SECRET
            }
            response_post = requests.post(uri_access_token, headers=headers, data=data_params)

            if response_post.status_code == 200:
                line_id_token = json.loads(response_post.text)["id_token"]
                user_profile = jwt.decode(line_id_token,
                                          settings.LINE_CHANNEL_SECRET,
                                          audience=settings.LINE_CHANNEL_ID,
                                          issuer='https://access.line.me',
                                          algorithms=['HS256'],
                                          options={'verify_iat': False})

                customer_name = user_profile['name'] if user_profile else 'Unknown User'
                hashed_id = hashlib.sha256(user_profile['sub'].encode()).hexdigest()
                context["user_profile"] = user_profile
                print('★★★ユーザー情報★★★: ' + str(user_profile))

                temporary_booking = request.session.get('temporary_booking')

                if temporary_booking is not None:
                    schedule = Schedule(
                        reservation_number=temporary_booking['reservation_number'],       
                        start=timezone.make_aware(datetime.datetime.fromisoformat(temporary_booking['start'])),
                        end=timezone.make_aware(datetime.datetime.fromisoformat(temporary_booking['end'])),
                        price=temporary_booking['price'],
                        customer_name=customer_name,
                        hashed_id=hashed_id,
                        staff_id=temporary_booking['staff_id']
                    )
                    schedule.save()
                    del request.session['temporary_booking']
                else:
                    print("仮予約情報がセッションに存在しません。")
                    return HttpResponseBadRequest("Temporary booking not found in session")

                line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)

                try:
                    user_id = user_profile['sub']
                    profile = line_bot_api.get_profile(user_id)
                    user_id = profile.user_id

                    payment_url = 'https://api.coiney.io/api/v1/payments'
                    reservation_number = schedule.reservation_number

                    headers = {
                        'Authorization': 'Bearer ' + settings.PAYMENT_API_KEY,
                        'Content-Type': 'application/json'
                    }
                    price = schedule.price
                    webhook_url = f"{settings.WEBHOOK_URL_BASE}{reservation_number}/"
                    now = timezone.now()
                    expired_on = now + timedelta(days=1)
                    expired_on_str = expired_on.strftime('%Y-%m-%d')
                    print('有効期限' + expired_on_str)

                    data = {
                        "amount": price,
                        "currency": "jpy",
                        "locale": "ja_JP",
                        "cancelUrl": settings.CANCEL_URL,
                        "webhookUrl": webhook_url,
                        "method": "creditcard",
                        "subject": "ご予約料金",
                        "description": "ウェブサイトからの支払い",
                        "remarks": "仮予約から10分を過ぎますと自動的にキャンセルとなります。あらかじめご了承ください。",
                        "metadata": {
                            "orderId": reservation_number
                        },
                        "expiredOn": expired_on_str
                    }

                    response = requests.post(payment_url, headers=headers, data=json.dumps(data))
                    if response.status_code == 201:
                        try:
                            payment_url = response.json()['links']['paymentUrl']
                        except (ValueError, KeyError):
                            print("Error decoding JSON or key not found")
                            payment_url = None
                    else:
                        print("HTTP request failed with status code ", response.status_code)
                        print("Response body: ", response.content)
                        payment_url = None

                    if payment_url is not None:
                        message = TextSendMessage(text='こちらのURLから決済を行ってください。決済後に予約が確定します。: ' + payment_url)
                        line_bot_api.push_message(user_id, message)
                        print('LINEアカウントID' + user_id)
                        return render(request, 'booking/redirect.html')
                    else:
                        print("Payment URL is not available")
                        return HttpResponseBadRequest("Payment URL is not available")

                except LineBotApiError as e:
                    print("LineBotApiError: ", e.status_code, e.error.message)
                    if e.status_code == 404:
                            print('ユーザーがボットを友達登録していません400')
                            friend_register_url = "https://line.me/R/ti/p/@649whqyj"
                            request.session['user_profile'] = user_profile
                            request.session['schedule_id'] = schedule.reservation_number
                            return render(request, 'booking/friend_register.html')
                    else:
                        return HttpResponseBadRequest("Failed to get user profile")

            request.session['profile'] = user_profile

            return render(request, 'booking/line_success.html', {'profile': user_profile})

def send_payment_url(user_id, payment_url):
    line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
    message = TextSendMessage(text='こちらのURLから決済を行ってください。決済後に予約が確定します。: ' + payment_url)
    line_bot_api.push_message(user_id, message)
    print('LINEアカウントID' + user_id)

class FriendRegisterView(View):
    def get(self, request, *args, **kwargs):
        user_profile = request.session.get('user_profile')
        schedule_id = request.session.get('schedule_id')
        payment_url = request.session.get('payment_url')  # セッションから決済URLを取得

        if user_profile and schedule_id and payment_url:
            send_payment_url(user_profile['sub'], payment_url)  # 決済URLを再送
            return JsonResponse({'message': 'Payment URL sent again.'})
        else:
            return JsonResponse({'message': 'Required data not found.'}, status=400)
        
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from django.http import HttpRequest
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)

@method_decorator(csrf_exempt, name='dispatch')
class LineWebhookView(View):
    def post(self, request, *args, **kwargs):
        signature = request.META['HTTP_X_LINE_SIGNATURE']
        body = request.body.decode('utf-8')

        try:
            handler.handle(body, signature)
        except InvalidSignatureError:
            return HttpResponse(status=400)

        return HttpResponse(status=200)

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id

    # 新しいリクエストオブジェクトを作成
    request = HttpRequest()
    # セッションミドルウェアを適用
    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()

    # セッションにユーザーIDを保存
    request.session['user_profile'] = {'sub': user_id}
    request.session.save()

    # FriendRegisterViewを呼び出して決済用リンクを再送
    view = FriendRegisterView.as_view()
    response = view(request)
    return response
                  
from django.http import JsonResponse
from django.views import View
from linebot import LineBotApi
from linebot.models import TextSendMessage
from django.urls import reverse
from urllib.parse import quote
from linebot.exceptions import LineBotApiError
import json


class PayingSuccessView(View):
    def post(self, request, orderId):
        # 決済サービスからのレスポンスを解析
        payment_response = json.loads(request.body)
        #print('PayingSuccessView起動、決済サービスからのレスポンス解析中')
        return process_payment(payment_response, request, orderId)
    
class LineSuccessView(View):
    def get(self, request):
        # セッションからプロフィールを取得します。
        profile = request.session.get('profile')

        return render(request, 'booking/line_success.html', {'profile': profile})
    
   
class OnlyStaffMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        return staff.user == self.request.user or self.request.user.is_superuser


class OnlyScheduleMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        schedule = get_object_or_404(Schedule, pk=self.kwargs['pk'])
        return schedule.staff.user == self.request.user or self.request.user.is_superuser


class OnlyUserMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return self.kwargs['pk'] == self.request.user.pk or self.request.user.is_superuser


class StoreList(generic.ListView):
    model = Store
    ordering = 'name'


class StaffList(generic.ListView):
    model = Staff
    ordering = 'name'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['store'] = self.store
        return context

    def get_queryset(self):
        store = self.store = get_object_or_404(Store, pk=self.kwargs['pk'])
        queryset = super().get_queryset().filter(store=store)
        return queryset


class StaffCalendar(generic.TemplateView):
    template_name = 'booking/calendar.html'

    def get_context_data(self, **kwargs):
        print(datetime.date)  # ここを追加
        context = super().get_context_data(**kwargs)
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        today = datetime.date.today()

        # どの日を基準にカレンダーを表示するかの処理。
        # 年月日の指定があればそれを、なければ今日からの表示。
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')
        if year and month and day:
            base_date = datetime.date(year=year, month=month, day=day)
        else:
            base_date = today

        # カレンダーは1週間分表示するので、基準日から1週間の日付を作成しておく
        days = [base_date + datetime.timedelta(days=day) for day in range(7)]
        start_day = days[0]
        end_day = days[-1]

        # 9時から17時まで1時間刻み、1週間分の、値がTrueなカレンダーを作る
        calendar = {}
        for hour in range(9, 18):
            row = {}
            for day in days:
                row[day] = True
            calendar[hour] = row

        # カレンダー表示する最初と最後の日時の間にある予約を取得する
        start_time = datetime.datetime.combine(start_day, datetime.time(hour=9, minute=0, second=0))
        end_time = datetime.datetime.combine(end_day, datetime.time(hour=17, minute=0, second=0))
        
        for schedule in Schedule.objects.filter(staff=staff).exclude(Q(start__gt=end_time) | Q(end__lt=start_time)):
            local_dt = timezone.localtime(schedule.start)
            booking_date = local_dt.date()
            booking_hour = local_dt.hour
            if booking_hour in calendar and booking_date in calendar[booking_hour]:
                # 予約が仮予約の場合は値を'Temp'に、そうでない場合は'Booked'に設定
                calendar[booking_hour][booking_date] = 'Temp' if schedule.is_temporary else 'Booked'

        context['staff'] = staff
        context['calendar'] = calendar
        context['days'] = days
        context['start_day'] = start_day
        context['end_day'] = end_day
        context['before'] = days[0] - datetime.timedelta(days=7)
        context['next'] = days[-1] + datetime.timedelta(days=1)
        context['today'] = today
        context['public_holidays'] = settings.PUBLIC_HOLIDAYS
        return context
    
from django import forms

class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = []  # Scheduleモデルのフィールドを指定

import pytz

class PreBooking(generic.CreateView):
    model = Schedule
    form_class = ScheduleForm
    template_name = 'booking/booking.html'
    
    def get_context_data(self, **kwargs):
        print('ゲットコンテキストデータ')
        context = super().get_context_data(**kwargs)
        context['staff'] = get_object_or_404(Staff, pk=self.kwargs['pk'])
        return context

    def post(self, request, *args, **kwargs):
        print(request.POST)  # POSTデータを出力
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        print('form_invalid:', form.errors)  # フォームのエラーを出力
        return super().form_invalid(form)
    
    def form_valid(self, form):
        print('form.is_valid()の結果:', form.is_valid())        
        print('form.errorsの結果:', form.errors)
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        # StaffからPriceを取得
        price = staff.price
        year = int(self.kwargs.get('year'))
        month = int(self.kwargs.get('month'))
        day = int(self.kwargs.get('day'))
        hour = int(self.kwargs.get('hour'))
        tz = pytz.timezone(settings.TIME_ZONE)
        start = datetime.datetime(year=year, month=month, day=day, hour=hour)
        end = datetime.datetime(year=year, month=month, day=day, hour=hour + 1)
        
        # 既存のスケジュールがあるかどうかを確認
        if Schedule.objects.filter(staff=staff, start=start).exists():
            print("既に同じスタッフと開始時間でスケジュールが存在します。")
            messages.error(self.request, 'すみません、入れ違いで予約がありました。別の日時はどうですか。')
            return HttpResponseRedirect(reverse('booking:staff_calendar', args=[staff.id]))  # スタッフのカレンダーページにリダイレクト
        else:
            schedule = form.save(commit=False)
            schedule.staff = staff
            schedule.start = start
            schedule.end = end
            schedule.is_temporary = True  # 仮予約フラグを設定
            schedule.price = price  # 価格を設定
            schedule.temporary_booked_at = datetime.datetime.now(tz)  # 仮予約日時を設定
            
            # 仮予約情報をセッションに保存
            self.request.session['temporary_booking'] = {
                'reservation_number': str(schedule.reservation_number),
                'start': start.isoformat(),
                'end': end.isoformat(),
                'price': price,
                'is_temporary': schedule.is_temporary,  # 仮予約フラグを保存
                'staff_id': staff.id,  # スタッフIDを保存
            }


        return redirect('booking:line_enter')
    
from linebot import LineBotApi
from linebot.models import TextSendMessage

class CancelReservationView(View):
    def post(self, request, schedule_id):
        # 予約情報を取得
        schedule = Schedule.objects.get(id=schedule_id)

        # 予約をキャンセル
        schedule.is_cancelled = True
        schedule.save()

        # LINE Messaging APIの初期化
        line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)

        # 予約者のLINEアカウントIDを取得
        customer_line_account_id = schedule.customer.line_id

        # キャンセル情報をメッセージとして送信
        message_text = 'あなたの予約がキャンセルされました。予約日時: {}'.format(schedule.start)
        message = TextSendMessage(text=message_text)
        line_bot_api.push_message(customer_line_account_id, message)

        return render(request, 'booking/cancel_success.html')

class MyPage(LoginRequiredMixin, generic.TemplateView):
    template_name = 'booking/my_page.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff_list'] = Staff.objects.filter(user=self.request.user).order_by('name')
        context['schedule_list'] = Schedule.objects.filter(staff__user=self.request.user, start__gte=timezone.now()).order_by('user')
        return context


class MyPageWithPk(OnlyUserMixin, generic.TemplateView):
    template_name = 'booking/my_page.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = get_object_or_404(User, pk=self.kwargs['pk'])
        context['staff_list'] = Staff.objects.filter(user__pk=self.kwargs['pk']).order_by('name')
        context['schedule_list'] = Schedule.objects.filter(staff__user__pk=self.kwargs['pk'], start__gte=timezone.now()).order_by('user')
        return context


class MyPageCalendar(OnlyStaffMixin, StaffCalendar):
    template_name = 'booking/my_page_calendar.html'


class MyPageDayDetail(OnlyStaffMixin, generic.TemplateView):
    template_name = 'booking/my_page_day_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = self.kwargs['pk']
        staff = get_object_or_404(Staff, pk=pk)
        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')
        date = datetime.date(year=year, month=month, day=day)

        # 9時から17時まで1時間刻みのカレンダーを作る
        calendar = {}
        for hour in range(9, 18):
            calendar[hour] = []

        # カレンダー表示する最初と最後の日時の間にある予約を取得する
        start_time = datetime.datetime.combine(date, datetime.time(hour=9, minute=0, second=0))
        end_time = datetime.datetime.combine(date, datetime.time(hour=17, minute=0, second=0))
        for schedule in Schedule.objects.filter(staff=staff).exclude(Q(start__gt=end_time) | Q(end__lt=start_time)):
            local_dt = timezone.localtime(schedule.start)
            booking_date = local_dt.date()
            booking_hour = local_dt.hour
            if booking_hour in calendar:
                calendar[booking_hour].append(schedule)

        context['calendar'] = calendar
        context['staff'] = staff
        return context


class MyPageSchedule(OnlyScheduleMixin, generic.UpdateView):
    model = Schedule
    fields = ('start', 'end', 'user')
    success_url = reverse_lazy('booking:my_page')


class MyPageScheduleDelete(OnlyScheduleMixin, generic.DeleteView):
    model = Schedule
    success_url = reverse_lazy('booking:my_page')
    
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
import pandas as pd
import json
import datetime
from .models import Schedule

from django.contrib.admin.sites import site

@staff_member_required
def analyze_customers(request):
    try:
        # 直近1年のデータを取得
        one_year_ago = datetime.datetime.now() - datetime.timedelta(days=365)
        schedules = Schedule.objects.filter(reservation_time__gte=one_year_ago).values()
        
        # データフレームに変換
        df = pd.DataFrame(schedules)
        
        # データが存在しない場合の処理
        if df.empty:
            return HttpResponse("予約データが存在しません", status=400)
        
        # スタッフ別予約数
        staff_reservations = df.groupby('staff_id').size().to_dict()
        
        # 店舗別予約数
        store_reservations = df.groupby('store_id').size().to_dict()
        
        # 時間別予約数
        df['hour'] = df['reservation_time'].dt.hour
        hourly_reservations = df.groupby('hour').size().to_dict()
        # 管理サイトのアプリケーションリストを取得
        app_list = site.get_app_list(request)
        
        context = {
            'staff_reservations': json.dumps(staff_reservations),
            'store_reservations': json.dumps(store_reservations),
            'hourly_reservations': json.dumps(hourly_reservations),
            'app_list': app_list,
        }
        
        return render(request, 'analyze_customers.html', context)
    except Exception as e:
        return HttpResponse(f"エラーが発生しました: {str(e)}", status=500)

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import generic
import datetime

@require_POST
def my_page_holiday_add(request, pk, year, month, day, hour):
    staff = get_object_or_404(Staff, pk=pk)
    if staff.user == request.user or request.user.is_superuser:
        start = datetime.datetime(year=year, month=month, day=day, hour=hour)
        end = datetime.datetime(year=year, month=month, day=day, hour=hour + 1)
        Schedule.objects.create(staff=staff, start=start, end=end, user=request.user)
        return redirect('booking:my_page_day_detail', pk=pk, year=year, month=month, day=day)

    raise PermissionDenied

@require_POST
def my_page_day_add(request, pk, year, month, day):
    staff = get_object_or_404(Staff, pk=pk)
    hour=9
    if staff.user == request.user or request.user.is_superuser:
            for num in range(9):
                start = datetime.datetime(year=year, month=month, day=day, hour=hour+num)
                end = datetime.datetime(year=year, month=month, day=day, hour=hour+num+1)
                Schedule.objects.create(staff=staff, start=start, end=end, user=request.user)
            return redirect('booking:my_page_day_detail', pk=pk, year=year, month=month, day=day)
    raise PermissionDenied

@require_POST
def my_page_day_delete(request, pk, year, month, day):
    staff = get_object_or_404(Staff, pk=pk)
    if staff.user == request.user or request.user.is_superuser:
        start = datetime.datetime(year=year, month=month, day=day, hour=9)
        end = datetime.datetime(year=year, month=month, day=day, hour=17)
        Schedule.objects.filter(staff=staff, start__gte=start, end__lte=end).delete()
        return redirect('booking:my_page_day_detail', pk=pk, year=year, month=month, day=day)

    raise PermissionDenied

#print('ビューのタスク.py')
@shared_task
def delete_temporary_schedules():
    print('delete_temporary_schedules')
    # 関数の本体
    now = timezone.now()
    print(str(now) + "現在時刻")
    
    Schedule.objects.filter(temporary_booked_at__lt=now - timezone.timedelta(minutes=10), is_temporary=True).delete()
    print('delete_temporary_schedules終了')
    
from django.http import HttpResponseRedirect
from django.shortcuts import render
from .forms import StaffForm  # Django管理画面でのフォームに対応するフォームをインポートします

def upload_file(request):
    if request.method == 'POST':
        form = StaffForm(request.POST, request.FILES)
        print('フォームの中身' + str(form))
        if form.is_valid():
            form.save()
            print('フォームのセーブ')
            return HttpResponseRedirect('/success/url/')  # 成功時のリダイレクト先URLを指定します
        else:
            print('フォームのエラー'+ form.errors)
    else:
        form = StaffForm()
        print('フォームの中身２' + str(form))
    return render(request, 'upload.html', {'form': form})

from django.views.decorators.csrf import csrf_exempt
from linebot import LineBotApi
from linebot.models import TextSendMessage
from linebot.exceptions import LineBotApiError

def process_payment(payment_response, request, orderId):
    print('process_paymentを起動、payment_responseは...' + str(payment_response))
    
    # 決済が成功したかどうかを確認
    if payment_response.get('type') == 'payment.succeeded':
        # 注文IDを取得
        schedule = Schedule.objects.get(reservation_number=orderId)
        print('スケジュール' + str(schedule))
        
        # 仮予約フラグをFalseに設定
        schedule.is_temporary = False

        # 予約情報を保存
        schedule.save()
        print('本予約情報として保存')
        
        # LINE Messaging APIの初期化
        line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
        print('LINE Messaging APIの初期化を行いました')
        
        # スタッフのLINEアカウントIDを取得
        staff_line_account_id = schedule.staff.line_id
        if not staff_line_account_id:
            print('スタッフのLINEアカウントIDが取得できませんでした')
            return JsonResponse({"error": "Staff LINE account ID not found"}, status=400)

        import pytz

        # ローカルタイムゾーンを取得
        local_tz = pytz.timezone('Asia/Tokyo')

        # schedule.startをローカルタイムゾーンに変換
        local_time = schedule.start.astimezone(local_tz)
        
        print('スタッフのLINEアカウントIDはこれです' + str(staff_line_account_id))
        print(schedule.start)
        # 予約完了情報をメッセージとして送信
        message_text = '予約が完了しました。予約者: {}, 日時: {}'.format(schedule.customer.name, local_time)
        message = TextSendMessage(text=message_text)
        import logging
        logger = logging.getLogger(__name__)
        try:
            line_bot_api.push_message(staff_line_account_id, message)  # LINEアカウントに通知
            print('スタッフのLINEアカウントに通知')
            print(message_text)
        except LineBotApiError as e:
            print('スタッフメッセージにてLineBotApiErrorが発生しました:', e)            
                        
           # 確認済みのセッションから顧客のLINE IDを取得します。
        try:
            user_id = request.session.get('temporary_booking').get('user_id')
            if user_id is None:
                logger.error('user_id is None')
                return JsonResponse({"error": "user_id not found"}, status=400)
        except Exception as e:
            logger.error('Error getting user_id from session: %s', e)
            return JsonResponse({"error": "Error getting user_id"}, status=500)

        # LINEプロフィールから名前を取得
        try:
            profile = line_bot_api.get_profile(user_id)
            name = profile.display_name
        except LineBotApiError as e:
            print('LINEプロフィール取得時にエラーが発生しました:', e)
            return JsonResponse({"error": "Error getting LINE profile"}, status=500)

        # 予約情報を更新
        schedule.customer.name = name
        schedule.save()

            
        # タイマーURLを生成
        timer_url = reverse('booking:LINETimerView', args=[user_id])
        encoded_timer_url = quote(timer_url)
        message = None  # 初期化
        
        # 決済完了の通知とタイマーURLをメッセージとして送信（予約キャンセルもこの先）
        message_text = '決済が完了しました。こちらのURLから予約情報・タイマーを確認できます: ' + '<' + 'https://timebaibai.com/' + encoded_timer_url + '>'
        
        message = TextSendMessage(text=message_text)
        try:  
            line_bot_api.push_message(user_id, message)  # LINEアカウントに通知
            print('顧客のLINEアカウントに通知')
            print(message_text)
        except LineBotApiError as e:
            print('顧客向け決済完了メッセージにてLineBotApiErrorが発生しました:', e)
        
    return JsonResponse({"status": "success"})

import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def coiney_webhook(request, orderId):
    if request.method == 'POST':
        # リクエストヘッダーをログに出力
        logger.info(request.META)
        print('coiney_webhook起動')

        if orderId:
            view = PayingSuccessView()
            return view.post(request,orderId)
        else:
            return JsonResponse({"error": "orderId not found in request body"}, status=400)
from .models import Media

def your_view(request):
    medias = Media.objects.order_by('-created_at')  # created_atフィールドの降順で並べ替え
    return render(request, 'booking/base.html', {'medias': medias})

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from booking.models import Customer, Schedule

@staff_member_required
def customer_booking_history(request, customer_id):
    customer = Customer.objects.get(id=customer_id)
    bookings = Schedule.objects.filter(customer=customer).select_related('staff').order_by('-start')
    
    context = {
        'customer': customer,
        'bookings': bookings,
    }
    
    return render(request, 'customer_booking_history.html', context)
import logging
from linebot import LineBotApi
from linebot.exceptions import LineBotApiError

# ログの設定
logging.basicConfig(level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

line_bot_api = LineBotApi('YOUR_CHANNEL_ACCESS_TOKEN')

def get(self, request, *args, **kwargs):
    user_id = 'USER_ID'
    message = 'YOUR_MESSAGE'
    try:
        profile = line_bot_api.get_profile(user_id)
        line_bot_api.push_message(user_id, message)
    except LineBotApiError as e:
        # エラーメッセージをログに記録
        logger.error(f"LineBotApiError: status_code={e.status_code}, request_id={e.request_id}, error_response={e.error.message}")
        for detail in e.error.details:
            logger.error(f"  - {detail.property}: {detail.message}")
        return HttpResponse("An error occurred", status=500)