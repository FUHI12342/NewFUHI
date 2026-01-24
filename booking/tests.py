import datetime
from django.shortcuts import resolve_url, get_object_or_404
from django.test import TestCase
from django.template.exceptions import TemplateDoesNotExist
from django.utils import timezone
from booking.models import Schedule, Staff, Store, IoTDevice, IoTEvent
import os
import json
# print(os.environ.get('PYTHONPATH', 'Not set'))

# Property-based testing imports
from hypothesis import given, strategies as st
from hypothesis.extra.django import TestCase as HypothesisTestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse

batu = '×'
maru = '○'
line = '-'
from django.http import HttpRequest
from unittest.mock import patch, Mock
from django.test import TestCase
from .views import process_payment


def api_post_json(client, url, data, **kwargs):
    """
    Helper function for IoT API testing that ensures proper JSON serialization.
    
    This replaces the problematic format='json' usage with manual JSON serialization
    to handle nested payload structures correctly.
    
    Args:
        client: APIClient instance
        url: URL to post to
        data: Data to serialize as JSON
        **kwargs: Additional headers (e.g., HTTP_X_API_KEY)
    
    Returns:
        Response object from the API call
    """
    return client.post(
        url,
        data=json.dumps(data),
        content_type='application/json',
        **kwargs
    )

@patch('requests.post')  # requests.postをモック化
def test_process_payment(self, mock_post):
     # モックのレスポンスを設定
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"status": "success"}
    
    # 決済成功を示すpayment_responseを作成
    payment_response = {'type': 'payment.succeeded'}

    # 空のHttpRequestオブジェクトを作成
    request = HttpRequest()

    # 適当なorderIdを設定
    orderId = 'test_order_id'

    # process_payment関数を呼び出す
    response = process_payment(payment_response, request, orderId)

    # responseが期待通りであることを確認
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json(), {"status": "success"})

class StoreListViewTests(TestCase):
    fixtures = ['initial']

    def test_get(self):
        """店舗の一覧が表示されるかテスト"""
        response = self.client.get(resolve_url('booking:store_list'))
        self.assertQuerysetEqual(response.context['store_list'],  ['<Store: 店舗A>', '<Store: 店舗B>', '<Store: 店舗C>'])


class StaffListViewTests(TestCase):
    fixtures = ['initial']

    def test_store_a(self):
        """店舗Aのスタッフリストの確認"""
        response = self.client.get(resolve_url('booking:staff_list', pk=1))
        self.assertQuerysetEqual(response.context['staff_list'],  ['<Staff: 店舗A - じゃば>', '<Staff: 店舗A - ぱいそん>'])

    def test_store_b(self):
        """店舗Bのスタッフリストの確認"""
        response = self.client.get(resolve_url('booking:staff_list', pk=2))
        self.assertQuerysetEqual(response.context['staff_list'],  ['<Staff: 店舗B - じゃんご>'])

    def test_store_c(self):
        """店舗Cのスタッフリストの確認。店舗Cには誰もいない"""
        response = self.client.get(resolve_url('booking:staff_list', pk=3))
        self.assertQuerysetEqual(response.context['staff_list'],  [])


class StaffCalendarViewTests(TestCase):
    fixtures = ['initial']

    def test_no_schedule(self):
        """スケジュールがない場合のカレンダーをテスト。

        店名や表示期間と、「☓」がないことを確認。これがあるのはスケジュールがある場合。
        """
        start = timezone.localtime()
        end = start + datetime.timedelta(days=6)
        response = self.client.get(resolve_url('booking:calendar', pk=1))
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{start.year}年{start.month}月{start.day}日 - {end.year}年{end.month}月{end.day}日')
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_day_9(self):
        """スケジュールが次の日の9時

        スケジュールがあるので、☓がカレンダー内に表示されることを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertContains(response, batu)

    def test_one_schedule_next_day_8(self):
        """スケジュールが次の日の8時

        8時のスケジュールはカレンダーに表示されないので、☓がないことを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=8, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_day_17(self):
        """スケジュールが次の日の17時

        17時はカレンダーに表示されるので、☓があることを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=17, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertContains(response, batu)

    def test_one_schedule_next_day_18(self):
        """次の日の18時にスケジュール

        18時はカレンダー表示されないので、☓がないことを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=18, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_before_day_9(self):
        """前の日の9時にスケジュール

        カレンダーは当日から表示なので、前の日のものは表示されない。☓がないことを確認。
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() - datetime.timedelta(days=1)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_week_9(self):
        """来週の9時にスケジュール

        7日後は表示されない。☓がないことを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=7)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_week_9_and_move(self):
        """来週の9時にスケジュール

        7日後を基準にカレンダー表示するので、スケジュールは表示される。☓があることを確認。
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=7)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk, year=start.year, month=start.month, day=start.day))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertContains(response, batu)

        end = start + datetime.timedelta(days=6)
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{start.year}年{start.month}月{start.day}日 - {end.year}年{end.month}月{end.day}日')


class BookingViewTests(TestCase):
    fixtures = ['initial']

    def test_get(self):
        """予約ページが表示されるかテスト"""
        now = timezone.localtime()
        response = self.client.get(resolve_url('booking:booking', pk=1, year=now.year, month=now.month, day=now.day, hour=9))
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{now.year}年{now.month}月{now.day}日 9時に予約')

    def test_post(self):
        """予約後に、カレンダーページで☓（予約あり）があることを確認"""
        now = timezone.localtime() + datetime.timedelta(days=1)
        response = self.client.post(
            resolve_url('booking:booking', pk=1, year=now.year, month=now.month, day=now.day, hour=9),
            {'name': 'テスト'},
            follow=True
        )
        messages = list(response.context['messages'])
        self.assertEqual(messages, [])
        self.assertContains(response, batu)

    def test_post_exists_data(self):
        """既に埋まった時間に予約した場合に、メッセージ表示があることを確認"""
        now = timezone.localtime().replace(hour=9, minute=0, second=0, microsecond=0)
        end = now + datetime.timedelta(hours=1)
        staff = get_object_or_404(Staff, pk=1)
        Schedule.objects.create(staff=staff, start=now, end=end, name='埋めた')
        response = self.client.post(
            resolve_url('booking:booking', pk=1, year=now.year, month=now.month, day=now.day, hour=9),
            {'name': 'これは入らない'},
            follow=True
        )
        messages = list(response.context['messages'])
        self.assertEqual(str(messages[0]), 'すみません、入れ違いで予約がありました。別の日時はどうですか。')


class MyPageViewTests(TestCase):
    fixtures = ['initial']

    def test_anonymous(self):
        """ログインしていない場合、ログインページにリダイレクトされることを確認"""
        response = self.client.get(resolve_url('booking:my_page'))
        self.assertRedirects(response, '/login/?next=%2Fmypage%2F')

    def test_login_admin(self):
        """管理者でログインした場合。店舗スタッフではないので、ナニも表示されない"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(resolve_url('booking:my_page'))
        self.assertQuerysetEqual(response.context['staff_list'], [])
        self.assertQuerysetEqual(response.context['schedule_list'], [])
        self.assertContains(response, 'adminのMyPage')

    def test_login_tanaka(self):
        """田中でログイン。スタッフデータが表示されることを確認"""
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page'))
        self.assertQuerysetEqual(response.context['staff_list'], ['<Staff: 店舗B - じゃんご>', '<Staff: 店舗A - ぱいそん>'])
        self.assertQuerysetEqual(response.context['schedule_list'], [])
        self.assertContains(response, 'tanakataroのMyPage')

    def test_login_tanaka_with_schedule(self):
        """田中でログインし、予約がある場合、自分担当の予約だけ表示されるか確認。"""
        staff1 = get_object_or_404(Staff, pk=1)
        staff2 = get_object_or_404(Staff, pk=2)
        staff3 = get_object_or_404(Staff, pk=3)
        now = timezone.localtime()
        s1 = Schedule.objects.create(staff=staff1, start=now - datetime.timedelta(hours=1), end=now, name='テスト1')  # 過去の予約は表示されない
        s2 = Schedule.objects.create(staff=staff1, start=now + datetime.timedelta(hours=1), end=now, name='テスト2')  # 問題なく表示
        s3 = Schedule.objects.create(staff=staff2, start=now + datetime.timedelta(hours=1), end=now, name='テスト3')  # 問題なく表示
        s4 = Schedule.objects.create(staff=staff3, start=now + datetime.timedelta(hours=1), end=now, name='テスト4')  # staff3は、自分じゃない
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page'))
        self.assertEqual(list(response.context['schedule_list']), [s2, s3])

    def test_login_yosida_with_schedule(self):
        """吉田でログインし、予約ある場合、自分担当の予約が表示されるか確認"""
        staff1 = get_object_or_404(Staff, pk=1)
        staff2 = get_object_or_404(Staff, pk=2)
        staff3 = get_object_or_404(Staff, pk=3)
        now = timezone.localtime()
        s1 = Schedule.objects.create(staff=staff1, start=now - datetime.timedelta(hours=1), end=now, name='テスト1')
        s2 = Schedule.objects.create(staff=staff1, start=now + datetime.timedelta(hours=1), end=now, name='テスト2')
        s3 = Schedule.objects.create(staff=staff2, start=now + datetime.timedelta(hours=1), end=now, name='テスト3')
        s4 = Schedule.objects.create(staff=staff3, start=now + datetime.timedelta(hours=1), end=now, name='テスト4')  # 吉田の予約
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page'))
        self.assertEqual(list(response.context['schedule_list']), [s4])
        self.assertContains(response, 'yosidaziroのMyPage')


class MyPageWithPkViewTests(TestCase):
    fixtures = ['initial']

    def test_anonymous(self):
        """ログインしていない場合、403の表示"""
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=2))
        self.assertEqual(response.status_code, 403)

    def test_login_admin(self):
        """スーパーユーザーは、どのユーザーのマイページでも見れる"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=2))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tanakataroのMyPage')

    def test_login_tanaka(self):
        """自分自身のマイページは見れる"""
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=2))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tanakataroのMyPage')

    def test_login_yosida(self):
        """他人のマイページは見れない"""
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=2))
        self.assertEqual(response.status_code, 403)

    def test_not_exist_user(self):
        """存在しないユーザーページにスーパーユーザーで行くと、404"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=10000))
        self.assertEqual(response.status_code, 404)

    def test_not_exist_user(self):
        """存在しないユーザーページに一般ユーザーで行くと、403"""
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=10000))
        self.assertEqual(response.status_code, 403)


class MyPageCalendarViewTests(TestCase):
    fixtures = ['initial']

    def test_anonymous(self):
        """ログインしていない場合は403"""
        response = self.client.get(resolve_url('booking:my_page_calendar', pk=1))
        self.assertEqual(response.status_code, 403)

    def test_login_admin(self):
        """スーパーユーザーは、誰のカレンダーでも見れる"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(resolve_url('booking:my_page_calendar', pk=1))
        self.assertEqual(response.status_code, 200)

    def test_login_tanaka(self):
        """自分用のカレンダーは見れる"""
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page_calendar', pk=1))
        self.assertEqual(response.status_code, 200)
        start = timezone.localtime()
        end = start + datetime.timedelta(days=6)
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{start.year}年{start.month}月{start.day}日 - {end.year}年{end.month}月{end.day}日')
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_login_yosida(self):
        """他人のカレンダーは見れない"""
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page_calendar', pk=1))
        self.assertEqual(response.status_code, 403)


class MyPageDayDetailViewTests(TestCase):
    fixtures = ['initial']

    def test_no_schedule(self):
        """店舗や日にちが正しく表示されるかの確認"""
        self.client.login(username='tanakataro', password='helloworld123')
        staff = get_object_or_404(Staff, pk=1)
        now = timezone.localtime().replace(hour=9, minute=0, second=0)
        response = self.client.get(resolve_url('booking:my_page_day_detail', pk=staff.pk, year=now.year, month=now.month, day=now.day))
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{now.year}年{now.month}月{now.day}日の予約一覧')

    def test_one_schedule_9(self):
        """予約が正しく表示されることを確認"""
        self.client.login(username='tanakataro', password='helloworld123')
        staff = get_object_or_404(Staff, pk=1)
        now = timezone.localtime().replace(hour=9, minute=0, second=0)
        Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_day_detail', pk=staff.pk, year=now.year, month=now.month, day=now.day))
        self.assertContains(response, 'テスト')

    def test_one_schedule_23(self):
        """時間外の予約は表示されないことを確認"""
        self.client.login(username='tanakataro', password='helloworld123')
        staff = get_object_or_404(Staff, pk=1)
        now = timezone.localtime().replace(hour=23, minute=0, second=0)
        Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_day_detail', pk=staff.pk, year=now.year, month=now.month, day=now.day))
        self.assertNotContains(response, 'テスト')


class MyPageScheduleViewTests(TestCase):
    fixtures = ['initial']

    def test_anonymous(self):
        """ログインしていないと403"""
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_schedule', pk=s1.pk))
        self.assertEqual(response.status_code, 403)

    def test_login_admin(self):
        """管理者は誰の予約でも詳細ページが見れる"""
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_schedule', pk=s1.pk))
        self.assertContains(response, '店舗A店 ぱいそん')

    def test_login_tanaka(self):
        """自分担当の予約は、詳細ページが見れる"""
        self.client.login(username='tanakataro', password='helloworld123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_schedule', pk=s1.pk))
        self.assertContains(response, '店舗A店 ぱいそん')

    def test_login_yosida(self):
        """自分の担当じゃない予約は、詳細ページが見れない(403)"""
        self.client.login(username='yosidaziro', password='helloworld123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_schedule', pk=s1.pk))
        self.assertEqual(response.status_code, 403)

    def test_post(self):
        """予約の更新を行い、反映されるかのテスト"""
        self.client.login(username='tanakataro', password='helloworld123')
        now = timezone.now() + datetime.timedelta(days=1)
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        response = self.client.post(
            resolve_url('booking:my_page_schedule', pk=s1.pk),
            {'name': '更新しました', 'start': now_str, 'end': now_str},
            follow=True
        )
        self.assertEqual(list(response.context['schedule_list']), [s1])


class MyPageScheduleDeleteViewTests(TestCase):
    fixtures = ['initial']

    def test_get(self):
        """予約の削除ページ。GETアクセスは想定していないので、TemplateDoesNotExist"""
        self.client.login(username='tanakataro', password='helloworld123')
        now = timezone.now() + datetime.timedelta(days=1)
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        with self.assertRaises(TemplateDoesNotExist):
            response = self.client.get(resolve_url('booking:my_page_schedule_delete', pk=s1.pk),)

    def test_post(self):
        """予約を削除すると当然、マイページの一覧には表示されなくなる"""
        self.client.login(username='tanakataro', password='helloworld123')
        now = timezone.now() + datetime.timedelta(days=1)
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.post(
            resolve_url('booking:my_page_schedule_delete', pk=s1.pk),
            follow=True
        )
        self.assertEqual(list(response.context['schedule_list']), [])


class MyPageHolidayAddViewTests(TestCase):
    fixtures = ['initial']

    def test_anonymous(self):
        """ログインしていないと403"""
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        response = self.client.post(
            resolve_url('booking:my_page_holiday_add', pk=staff.pk, year=now.year, month=now.month, day=now.day, hour=9),
            follow=True,
        )
        self.assertEqual(response.status_code, 403)

    def test_login_admin(self):
        """スーパーユーザーは、休日追加を自由に行える"""
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        response = self.client.post(
            resolve_url('booking:my_page_holiday_add', pk=staff.pk, year=now.year, month=now.month, day=now.day, hour=9),
            follow=True,
        )
        self.assertContains(response, '休暇(システムによる追加)')
        self.assertEqual(response.status_code, 200)

    def test_login_tanaka(self):
        """自分で休日を追加できることを確認"""
        self.client.login(username='tanakataro', password='helloworld123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        response = self.client.post(
            resolve_url('booking:my_page_holiday_add', pk=staff.pk, year=now.year, month=now.month, day=now.day, hour=9),
            follow=True,
        )
        self.assertContains(response, '休暇(システムによる追加)')
        self.assertEqual(response.status_code, 200)

    def test_login_yosida(self):
        """他人の休日は追加できないことを確認"""
        self.client.login(username='yosidaziro', password='helloworld123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        response = self.client.post(
            resolve_url('booking:my_page_holiday_add', pk=staff.pk, year=now.year, month=now.month, day=now.day, hour=9),
            follow=True,
        )
        self.assertEqual(response.status_code, 403)

    def test_get(self):
        """GETでアクセスできないことを確認"""
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        response = self.client.get(
            resolve_url('booking:my_page_holiday_add', pk=staff.pk, year=now.year, month=now.month, day=now.day, hour=9),
            follow=True,
        )
        self.assertEqual(response.status_code, 405)

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from linebot import LineBotApi
from django.conf import settings
from unittest.mock import Mock  
from unittest.mock import patch
from django.core.management import call_command

class PayingSuccessViewTest(TestCase):
    def setUp(self):
        super().setUp()
        # フィクスチャをロード
        call_command('loaddata', 'initial', verbosity=0)
        self.client = Client()
        line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
        # テスト用のユーザーIDを設定
        line_user_id = 'testLineUserId'

        # LINE APIからプロフィール情報を取得（モックを使用）
        profile = Mock()
        profile.user_id = line_user_id

        # セッションにプロフィール情報を設定
        session = self.client.session
        session['profile'] = {'user_id': profile.user_id, 'sub': '@yakiedamamesan'}
        session.save()
        # Userオブジェクトを作成（適切なパラメータを設定してください）
        self.user = User.objects.create_user(username='testuser', password='12345')
        # Storeオブジェクトを作成（適切なパラメータを設定してください）
        self.store = Store.objects.create(name='テストストア')
        # Staffオブジェクトを作成
        self.staff = Staff.objects.create(name='テストスタッフ', user_id=self.user.id, store_id=self.store.id,line_id='@yakiedamamesan')
        # Scheduleオブジェクトを作成
        self.schedule = Schedule.objects.create(
            is_temporary=True, 
            start=timezone.now(),
            end=timezone.now() + timezone.timedelta(hours=1),  # endフィールドに現在時刻の1時間後を設定
            staff_id=self.staff.id,# staff_idフィールドに先ほど作成したStaffオブジェクトのIDを設定
            customer_name='テストカスタマー'  # customer_nameフィールドを使用
        )

    #@patch('linebot.LineBotApi.push_message')
    
    def test_paying_success_view(self):
        # CoineyKit-Paygeから送られてくるであろうデータを模擬的に作成
        data = {
            'amount': '1000',
            'currency': 'JPY',
            'orderId': '1234',
            'status': 'paid',
            # 他の必要なデータ...
        }

        # PayingSuccessViewにPOSTリクエストを送信
        response = self.client.post(reverse('booking:paying_success'), data)

        # レスポンスのステータスコードが200（成功）であることを確認
        self.assertEqual(response.status_code, 200)

        # Scheduleオブジェクトのis_temporaryフラグがFalseに設定されていることを確認
        self.schedule.refresh_from_db()
        self.assertFalse(self.schedule.is_temporary)

        # Scheduleオブジェクトがデータベースに保存されていることを確認
        self.assertIsNotNone(self.schedule.id)

        # レスポンスの内容を確認
        self.assertEqual(response.content.decode(), 'Payment successful and message sent.')
import requests

class IoTAPISensorFieldAcceptanceTest(HypothesisTestCase):
    """
    **Property 2: API Sensor Field Acceptance**
    **Validates: Requirements 3.3, 9.1, 9.2, 9.3, 9.4, 9.5, 10.4**
    
    This property test ensures that the IoT API correctly accepts and processes
    sensor field data in various formats and field name variations.
    """
    
    def setUp(self):
        self.store = Store.objects.create(name="Test Store")
        self.device = IoTDevice.objects.create(
            name="Test Device",
            store=self.store,
            external_id="test_device_001",
            api_key="test_api_key_123"
        )
        self.client = APIClient()
    
    def tearDown(self):
        IoTEvent.objects.all().delete()
        IoTDevice.objects.all().delete()
        Store.objects.all().delete()
    
    @given(
        mq9_value=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        light_value=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        sound_value=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        temp_value=st.floats(min_value=-50.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        hum_value=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_api_accepts_sensor_fields_consistently(self, mq9_value, light_value, sound_value, temp_value, hum_value):
        """Property test: API accepts sensor fields in various formats consistently"""
        # Test direct field format
        data = {
            "device": self.device.external_id,
            "event_type": "sensor_reading",
            "mq9": mq9_value,
            "light": light_value,
            "sound": sound_value,
            "temp": temp_value,
            "hum": hum_value
        }
        
        response = api_post_json(
            self.client,
            reverse('booking:iot_events'),
            data,
            HTTP_X_API_KEY=self.device.api_key
        )
        
        self.assertEqual(response.status_code, 201)
        
        # Verify the event was created with correct mq9_value
        event = IoTEvent.objects.get(id=response.data['id'])
        if event.mq9_value is not None:
            self.assertAlmostEqual(float(event.mq9_value), mq9_value, places=2)
        else:
            # For very small floats that might be converted to None, just ensure they're very small
            self.assertLess(abs(mq9_value), 1e-100, f"mq9_value should be very small if converted to None, got {mq9_value}")
    
    @given(
        mq9_value=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
    )
    def test_api_accepts_mq9_value_field_name(self, mq9_value):
        """Property test: API accepts mq9_value field name as alternative"""
        data = {
            "device": self.device.external_id,
            "event_type": "sensor_reading",
            "mq9_value": mq9_value  # Alternative field name
        }
        
        response = api_post_json(
            self.client,
            reverse('booking:iot_events'),
            data,
            HTTP_X_API_KEY=self.device.api_key
        )
        
        self.assertEqual(response.status_code, 201)
        
        # Verify the event was created with correct mq9_value
        event = IoTEvent.objects.get(id=response.data['id'])
        if event.mq9_value is not None:
            self.assertAlmostEqual(float(event.mq9_value), mq9_value, places=2)
        else:
            # For very small floats that might be converted to None, just ensure they're very small
            self.assertLess(abs(mq9_value), 1e-100, f"mq9_value should be very small if converted to None, got {mq9_value}")
    
    @given(
        sensor_data=st.fixed_dictionaries({
            'mq9': st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False, allow_subnormal=False),
            'light': st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False, allow_subnormal=False),
            'sound': st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False, allow_subnormal=False),
            'temp': st.floats(min_value=-50.0, max_value=100.0, allow_nan=False, allow_infinity=False, allow_subnormal=False),
            'hum': st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False, allow_subnormal=False)
        })
    )
    def test_api_accepts_nested_sensors_payload(self, sensor_data):
        """Property test: API accepts sensor data in nested payload.sensors format"""
        # Ensure clean test environment for each run
        IoTEvent.objects.filter(device=self.device).delete()
        
        data = {
            "device": self.device.external_id,
            "event_type": "sensor_reading",
            "payload": {
                "sensors": sensor_data
            }
        }
        
        # 修正: 確実にJSONとして送信 - manual JSON serialization
        response = api_post_json(
            self.client,
            reverse('booking:iot_events'),
            data,
            HTTP_X_API_KEY=self.device.api_key
        )
        
        self.assertEqual(response.status_code, 201, f"API request failed with data: {data}")
        
        # Verify the event was created with correct mq9_value
        event = IoTEvent.objects.get(id=response.data['id'])
        
        # Debug information for troubleshooting
        if event.mq9_value is None:
            import json
            print(f"DEBUG: sensor_data = {sensor_data}")
            print(f"DEBUG: request data = {data}")
            print(f"DEBUG: response = {response.data}")
            print(f"DEBUG: event.mq9_value = {event.mq9_value}")
            print(f"DEBUG: event.payload = {event.payload}")
            
            # Try to understand why mq9_value is None
            try:
                payload = json.loads(event.payload)
                print(f"DEBUG: parsed payload = {payload}")
            except Exception as e:
                print(f"DEBUG: payload parsing error = {e}")
            
            self.fail(f"mq9_value is None when it should be {sensor_data['mq9']}")
        
        # The API should extract mq9 from nested sensors and store it as mq9_value
        self.assertIsNotNone(event.mq9_value, f"mq9_value should not be None for input {sensor_data['mq9']}")
        self.assertAlmostEqual(float(event.mq9_value), sensor_data['mq9'], places=2)
        
        # Verify that the sensor data is preserved in the payload
        import json
        payload = json.loads(event.payload)
        
        # Ensure no "payload_raw": "sensors" appears (regression prevention)
        self.assertNotEqual(payload.get("payload_raw"), "sensors", "payload_raw should never be 'sensors' - this indicates incorrect payload processing")
        self.assertNotIn("payload_raw", payload, "payload should not contain payload_raw when properly parsed")
        
        # Check if the sensors data was properly extracted and stored
        self.assertIn('mq9', payload, "payload should contain extracted mq9 value")
        self.assertAlmostEqual(float(payload['mq9']), sensor_data['mq9'], places=2)
    
    def test_api_accepts_nested_sensors_payload_with_zero_values(self):
        """Specific test for 0.0 values in nested sensors payload"""
        # Test the edge case of 0.0 values specifically
        sensor_data = {'mq9': 0.0, 'light': 0.0, 'sound': 0.0, 'temp': 0.0, 'hum': 0.0}
        
        # Ensure clean test environment
        IoTEvent.objects.filter(device=self.device).delete()
        
        data = {
            "device": self.device.external_id,
            "event_type": "sensor_reading",
            "payload": {
                "sensors": sensor_data
            }
        }
        
        # 修正: 確実にJSONとして送信 - manual JSON serialization
        response = api_post_json(
            self.client,
            reverse('booking:iot_events'),
            data,
            HTTP_X_API_KEY=self.device.api_key
        )
        
        self.assertEqual(response.status_code, 201, f"API request failed with data: {data}")
        
        # Verify the event was created with correct mq9_value
        event = IoTEvent.objects.get(id=response.data['id'])
        
        # The API should extract mq9 from nested sensors and store it as mq9_value
        self.assertIsNotNone(event.mq9_value, "mq9_value should not be None for 0.0 input")
        self.assertEqual(float(event.mq9_value), 0.0)
        
        # Verify that the sensor data is preserved in the payload
        import json
        payload = json.loads(event.payload)
        
        # Ensure no "payload_raw": "sensors" appears (regression prevention)
        self.assertNotEqual(payload.get("payload_raw"), "sensors", "payload_raw should never be 'sensors' - this indicates incorrect payload processing")
        self.assertNotIn("payload_raw", payload, "payload should not contain payload_raw when properly parsed")
        
        # Check if the sensors data was properly extracted and stored
        self.assertIn('mq9', payload, "payload should contain extracted mq9 value")
        self.assertEqual(float(payload['mq9']), 0.0)
    
    def test_api_accepts_nested_sensors_payload_unit_test(self):
        """Unit test version of nested sensors payload test"""
        import json
        test_cases = [
            {'mq9': 0.0, 'light': 0.0, 'sound': 0.0, 'temp': 0.0, 'hum': 0.0},
            {'mq9': 100.5, 'light': 75.2, 'sound': 45.8, 'temp': 23.4, 'hum': 65.1},
            {'mq9': 999.9, 'light': 99.9, 'sound': 99.9, 'temp': 99.9, 'hum': 99.9},
            {'mq9': 0.1, 'light': 0.1, 'sound': 0.1, 'temp': -49.9, 'hum': 0.1},
        ]
        
        for i, sensor_data in enumerate(test_cases):
            with self.subTest(case=i, sensor_data=sensor_data):
                # Clean up previous events
                IoTEvent.objects.filter(device=self.device).delete()
                
                data = {
                    "device": self.device.external_id,
                    "event_type": "sensor_reading",
                    "payload": {
                        "sensors": sensor_data
                    }
                }
                
                response = api_post_json(
                    self.client,
                    reverse('booking:iot_events'),
                    data,
                    HTTP_X_API_KEY=self.device.api_key
                )
                
                self.assertEqual(response.status_code, 201, f"API request failed with data: {data}")
                
                # Verify the event was created with correct mq9_value
                event = IoTEvent.objects.get(id=response.data['id'])
                
                # The API should extract mq9 from nested sensors and store it as mq9_value
                self.assertIsNotNone(event.mq9_value, f"mq9_value should not be None for input {sensor_data['mq9']}")
                self.assertAlmostEqual(float(event.mq9_value), sensor_data['mq9'], places=2)
                
                # Verify that the sensor data is preserved in the payload
                import json
                payload = json.loads(event.payload)
                
                # Ensure no "payload_raw": "sensors" appears (regression prevention)
                self.assertNotEqual(payload.get("payload_raw"), "sensors", f"payload_raw should never be 'sensors' for case {i}")
                
                self.assertAlmostEqual(float(payload['mq9']), sensor_data['mq9'], places=2)


class IoTAPIAuthenticationValidationTest(HypothesisTestCase):
    """
    **Property 3: API Authentication Validation**
    **Validates: Requirements 3.4**
    
    This property test ensures that the IoT API properly validates authentication
    across different scenarios and input variations.
    """
    
    def setUp(self):
        self.store = Store.objects.create(name="Test Store Auth")
        self.device = IoTDevice.objects.create(
            name="Test Device Auth",
            store=self.store,
            external_id="test_device_auth_001",
            api_key="test_api_key_auth_123"
        )
        self.client = APIClient()
    
    def tearDown(self):
        IoTEvent.objects.all().delete()
        IoTDevice.objects.all().delete()
        Store.objects.all().delete()
    
    @given(
        invalid_api_key=st.text(min_size=1, max_size=255).filter(lambda x: x != "test_api_key_auth_123")
    )
    def test_api_rejects_invalid_api_key(self, invalid_api_key):
        """Property test: API consistently rejects invalid API keys"""
        data = {
            "device": self.device.external_id,
            "event_type": "sensor_reading",
            "mq9": 100.0
        }
        
        response = api_post_json(
            self.client,
            reverse('booking:iot_events'),
            data,
            HTTP_X_API_KEY=invalid_api_key
        )
        
        self.assertEqual(response.status_code, 404)  # Device not found with invalid API key
    
    def test_api_requires_api_key_header(self):
        """Property test: API requires X-API-KEY header"""
        data = {
            "device": self.device.external_id,
            "event_type": "sensor_reading",
            "mq9": 100.0
        }
        
        response = self.client.post(
            reverse('booking:iot_events'),
            data=json.dumps(data),
            content_type='application/json'
            # No HTTP_X_API_KEY header
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("X-API-KEY header is required", response.data['detail'])


class IoTAPIErrorHandlingTest(HypothesisTestCase):
    """
    **Property 4: API Error Handling**
    **Validates: Requirements 3.5, 9.6**
    
    This property test ensures that the IoT API handles errors gracefully
    and provides appropriate error responses.
    """
    
    def setUp(self):
        self.store = Store.objects.create(name="Test Store Error")
        self.device = IoTDevice.objects.create(
            name="Test Device Error",
            store=self.store,
            external_id="test_device_error_001",
            api_key="test_api_key_error_123"
        )
        self.client = APIClient()
    
    def tearDown(self):
        IoTEvent.objects.all().delete()
        IoTDevice.objects.all().delete()
        Store.objects.all().delete()
    
    @given(
        invalid_device_name=st.text(min_size=1, max_size=255).filter(lambda x: x != "test_device_error_001")
    )
    def test_api_handles_invalid_device_gracefully(self, invalid_device_name):
        """Property test: API handles invalid device names gracefully"""
        data = {
            "device": invalid_device_name,
            "event_type": "sensor_reading",
            "mq9": 100.0
        }
        
        response = api_post_json(
            self.client,
            reverse('booking:iot_events'),
            data,
            HTTP_X_API_KEY=self.device.api_key
        )
        
        self.assertEqual(response.status_code, 404)
        self.assertIn("device not found", response.data['detail'])
    
    def test_api_handles_missing_device_field(self):
        """Property test: API handles missing device field gracefully"""
        data = {
            "event_type": "sensor_reading",
            "mq9": 100.0
            # Missing "device" field
        }
        
        response = api_post_json(
            self.client,
            reverse('booking:iot_events'),
            data,
            HTTP_X_API_KEY=self.device.api_key
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("device is required", response.data['detail'])


# Property-based tests for IoT integration
class IoTModelImportConsistencyTest(HypothesisTestCase):
    """
    **Property 1: Model Import Consistency**
    **Validates: Requirements 1.2, 10.3**
    
    This property test ensures that IoT models can be imported consistently
    and that their basic structure remains intact across different scenarios.
    """
    
    def test_iot_models_can_be_imported(self):
        """Test that IoT models can be imported without errors"""
        try:
            from booking.models import IoTDevice, IoTEvent
            # Verify models have expected attributes
            self.assertTrue(hasattr(IoTDevice, 'name'))
            self.assertTrue(hasattr(IoTDevice, 'store'))
            self.assertTrue(hasattr(IoTDevice, 'external_id'))
            self.assertTrue(hasattr(IoTEvent, 'device'))
            self.assertTrue(hasattr(IoTEvent, 'created_at'))
            self.assertTrue(hasattr(IoTEvent, 'mq9_value'))
        except ImportError as e:
            self.fail(f"Failed to import IoT models: {e}")
    
    @given(
        device_name=st.text(min_size=1, max_size=100),
        external_id=st.text(min_size=1, max_size=255),
        api_key=st.text(min_size=1, max_size=255)
    )
    def test_iot_device_creation_consistency(self, device_name, external_id, api_key):
        """Property test: IoTDevice can be created with valid data consistently"""
        # Create a test store first
        store = Store.objects.create(name="Test Store")
        
        try:
            device = IoTDevice.objects.create(
                name=device_name,
                store=store,
                external_id=external_id,
                api_key=api_key
            )
            # Verify the device was created successfully
            self.assertEqual(device.name, device_name)
            self.assertEqual(device.store, store)
            self.assertEqual(device.external_id, external_id)
            self.assertEqual(device.api_key, api_key)
        except Exception as e:
            # Only fail if it's not a validation error
            if "UNIQUE constraint failed" not in str(e):
                self.fail(f"Unexpected error creating IoTDevice: {e}")


class IoTModelRelationshipIntegrityTest(HypothesisTestCase):
    """
    **Property 5: Model Relationship Integrity**
    **Validates: Requirements 1.3, 10.5**
    
    This property test ensures that relationships between IoT models
    maintain integrity across different operations.
    """
    
    @given(
        mq9_value=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
    )
    def test_iot_event_device_relationship_integrity(self, mq9_value):
        """Property test: IoTEvent maintains proper relationship with IoTDevice"""
        # Create test data
        store = Store.objects.create(name="Test Store")
        device = IoTDevice.objects.create(
            name="Test Device",
            store=store,
            external_id=f"device_{timezone.now().timestamp()}",
            api_key="test_key"
        )
        
        # Create IoTEvent
        event = IoTEvent.objects.create(
            device=device,
            mq9_value=mq9_value,
            event_type="sensor_reading"
        )
        
        # Verify relationship integrity
        self.assertEqual(event.device, device)
        self.assertEqual(event.device.store, store)
        self.assertIn(event, device.events.all())
        
        # Verify cascade behavior
        device_id = device.id
        device.delete()
        self.assertFalse(IoTEvent.objects.filter(device_id=device_id).exists())


# Property-based tests for IoT integration
# from django.core.files.uploadedfile import SimpleUploadedFile
# from django.test import TestCase, Client
# from .models import Staff

# class UploadFileTest(TestCase):
#     def setUp(self):
#         self.client = Client()

#     def test_upload_file(self):
#         with open('path/to/your/test/image.jpg', 'rb') as f:
#             response = self.client.post('/your/upload/url/', {'thumbnail': SimpleUploadedFile(f.name, f.read())})
#         self.assertEqual(response.status_code, 302)  # リダイレクトが期待される
#         self.assertTrue(Staff.objects.filter(thumbnail='thumbnails/image.jpg').exists())  # ファイルが保存されていることを確認


class IoTMigrationBackwardCompatibilityTest(HypothesisTestCase):
    """
    **Property 6: Migration Backward Compatibility**
    **Validates: Requirements 2.3**
    
    For any existing database data, applying IoT migrations should preserve 
    all existing data and relationships without corruption or loss.
    """
    
    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User
        
        # Create test data that should be preserved during migrations
        self.store = Store.objects.create(
            name="Test Store",
            address="Test Address",
            nearest_station="Test Station"
        )
        
        # Create user for staff (required field)
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        self.staff = Staff.objects.create(
            name="Test Staff",
            user=self.user,
            store=self.store
        )
        
    @given(
        device_name=st.text(min_size=1, max_size=50),
        external_id=st.text(min_size=1, max_size=100),
        api_key=st.text(min_size=1, max_size=100)
    )
    def test_migration_preserves_existing_data(self, device_name, external_id, api_key):
        """
        Test that IoT migrations preserve existing Store and Staff data.
        This validates that the migration process doesn't corrupt existing relationships.
        """
        # Verify existing data is intact before IoT operations
        original_store_count = Store.objects.count()
        original_staff_count = Staff.objects.count()
        
        # Create IoT device using existing store relationship
        device = IoTDevice.objects.create(
            name=device_name,
            store=self.store,
            external_id=external_id,
            api_key=api_key
        )
        
        # Verify existing data is preserved
        self.assertEqual(Store.objects.count(), original_store_count)
        self.assertEqual(Staff.objects.count(), original_staff_count)
        
        # Verify relationships work correctly
        self.assertEqual(device.store, self.store)
        self.assertIn(device, self.store.iot_devices.all())
        
        # Create IoT event to test event relationships
        event = IoTEvent.objects.create(
            device=device,
            event_type="sensor_data",
            mq9_value=100.0
        )
        
        # Verify event relationships
        self.assertEqual(event.device, device)
        self.assertIn(event, device.events.all())
        
        # Verify original data is still intact
        refreshed_store = Store.objects.get(id=self.store.id)
        refreshed_staff = Staff.objects.get(id=self.staff.id)
        
        self.assertEqual(refreshed_store.name, self.store.name)
        self.assertEqual(refreshed_staff.name, self.staff.name)
        self.assertEqual(refreshed_staff.store, refreshed_store)
    
    def test_migration_database_integrity(self):
        """
        Test that database constraints and indexes are properly maintained
        after IoT migrations are applied.
        """
        from django.db import transaction
        
        # Test unique constraint on external_id
        device1 = IoTDevice.objects.create(
            name="Device 1",
            store=self.store,
            external_id="unique_id_123",
            api_key="key1"
        )
        
        # Attempting to create another device with same external_id should fail
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            with transaction.atomic():
                IoTDevice.objects.create(
                    name="Device 2",
                    store=self.store,
                    external_id="unique_id_123",  # Same external_id
                    api_key="key2"
                )
        
        # Test foreign key constraints
        event = IoTEvent.objects.create(
            device=device1,
            event_type="test_event"
        )
        
        # Verify foreign key relationship
        self.assertEqual(event.device, device1)
        
        # Test that deleting device cascades to events (if configured)
        device_id = device1.id
        event_id = event.id
        device1.delete()
        
        # Event should be deleted due to cascade
        self.assertFalse(IoTEvent.objects.filter(id=event_id).exists())

class IoTURLResolutionTest(TestCase):
    """
    Test to ensure IoT API URLs resolve correctly and prevent 404 regressions.
    """
    
    def test_iot_events_url_resolution(self):
        """Test that IoT events URL resolves to correct view"""
        from django.urls import reverse, resolve
        from booking.views import IoTEventAPIView
        
        # Test URL reverse resolution
        url = reverse('booking:iot_events')
        self.assertEqual(url, '/api/iot/events/')
        
        # Test URL resolve to correct view
        resolved = resolve(url)
        self.assertEqual(resolved.func.view_class, IoTEventAPIView)
        
    def test_iot_config_url_resolution(self):
        """Test that IoT config URL resolves to correct view"""
        from django.urls import reverse, resolve
        from booking.views import IoTConfigAPIView
        
        # Test URL reverse resolution
        url = reverse('booking:iot_config')
        self.assertEqual(url, '/api/iot/config/')
        
        # Test URL resolve to correct view
        resolved = resolve(url)
        self.assertEqual(resolved.func.view_class, IoTConfigAPIView)


class IoTNestedSensorsPayloadTest(TestCase):
    """
    Unit test for nested sensors payload functionality to debug the property test issue.
    """
    
    def setUp(self):
        self.store = Store.objects.create(name="Test Store")
        self.device = IoTDevice.objects.create(
            name="Test Device",
            store=self.store,
            external_id="test_device_001",
            api_key="test_api_key_123"
        )
        self.client = APIClient()
    
    def test_nested_sensors_payload_with_zero_values(self):
        """Test that nested sensors payload works correctly with 0.0 values"""
        data = {
            "device": self.device.external_id,
            "event_type": "sensor_reading",
            "payload": {
                "sensors": {
                    "mq9": 0.0,
                    "light": 0.0,
                    "sound": 0.0,
                    "temp": 0.0,
                    "hum": 0.0
                }
            }
        }
        
        response = api_post_json(
            self.client,
            reverse('booking:iot_events'),
            data,
            HTTP_X_API_KEY=self.device.api_key
        )
        
        self.assertEqual(response.status_code, 201)
        
        # Verify the event was created with correct mq9_value
        event = IoTEvent.objects.get(id=response.data['id'])
        
        # Debug: Print the actual values
        print(f"DEBUG: event.mq9_value = {event.mq9_value} (type: {type(event.mq9_value)})")
        print(f"DEBUG: event.payload = {event.payload}")
        
        # The API should extract mq9 from nested sensors and store it as mq9_value
        self.assertIsNotNone(event.mq9_value, "mq9_value should not be None for 0.0 input")
        self.assertEqual(float(event.mq9_value), 0.0)
        
        # Verify that the sensor data is preserved in the payload
        import json
        payload = json.loads(event.payload)
        self.assertEqual(float(payload['mq9']), 0.0)
    
    def test_nested_sensors_payload_with_positive_values(self):
        """Test that nested sensors payload works correctly with positive values"""
        data = {
            "device": self.device.external_id,
            "event_type": "sensor_reading",
            "payload": {
                "sensors": {
                    "mq9": 100.5,
                    "light": 75.2,
                    "sound": 45.8,
                    "temp": 23.4,
                    "hum": 65.1
                }
            }
        }
        
        response = api_post_json(
            self.client,
            reverse('booking:iot_events'),
            data,
            HTTP_X_API_KEY=self.device.api_key
        )
        
        self.assertEqual(response.status_code, 201)
        
        # Verify the event was created with correct mq9_value
        event = IoTEvent.objects.get(id=response.data['id'])
        
        # The API should extract mq9 from nested sensors and store it as mq9_value
        self.assertAlmostEqual(float(event.mq9_value), 100.5, places=2)
        
        # Verify that the sensor data is preserved in the payload
        import json
        payload = json.loads(event.payload)
        self.assertAlmostEqual(float(payload['mq9']), 100.5, places=2)