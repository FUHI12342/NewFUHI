"""
セキュリティ監査テスト

- SecurityAuditモデルのCRUD
- security_auditコマンドがエントリを生成すること
- --json出力の検証
- DEBUG=True検出、HSTS未設定検出
- PaymentMethod平文鍵の検出
- --categoryフィルター動作
- SecurityLog CRUD + 自動削除コマンド
- ミドルウェアのログイン失敗記録
"""
import json
import uuid

from django.test import TestCase, Client, override_settings
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.utils import timezone

from booking.models import SecurityAudit, SecurityLog, CostReport

User = get_user_model()


class TestSecurityAuditModel(TestCase):
    """SecurityAuditモデルのCRUDテスト"""

    def test_create_security_audit(self):
        run_id = uuid.uuid4()
        audit = SecurityAudit.objects.create(
            run_id=run_id,
            check_name='debug_mode',
            category='django_settings',
            severity='critical',
            status='fail',
            message='DEBUG=True',
            recommendation='DEBUG=Falseに設定してください',
        )
        self.assertIsNotNone(audit.pk)
        self.assertEqual(audit.check_name, 'debug_mode')
        self.assertEqual(audit.severity, 'critical')
        self.assertEqual(audit.status, 'fail')

    def test_security_audit_str(self):
        audit = SecurityAudit(
            check_name='debug_mode',
            category='django_settings',
            severity='critical',
            status='fail',
            message='DEBUG=True',
        )
        self.assertIn('debug_mode', str(audit))

    def test_security_audit_ordering(self):
        run_id = uuid.uuid4()
        a1 = SecurityAudit.objects.create(
            run_id=run_id, check_name='check1', category='django_settings',
            severity='info', status='pass', message='ok',
        )
        a2 = SecurityAudit.objects.create(
            run_id=run_id, check_name='check2', category='django_settings',
            severity='info', status='pass', message='ok',
        )
        audits = list(SecurityAudit.objects.all())
        self.assertEqual(audits[0].pk, a2.pk)  # newest first


class TestSecurityAuditCommand(TestCase):
    """security_auditコマンドテスト"""

    def test_command_creates_entries(self):
        call_command('security_audit')
        count = SecurityAudit.objects.count()
        self.assertGreaterEqual(count, 12)

    def test_command_json_output(self):
        from io import StringIO
        out = StringIO()
        call_command('security_audit', '--json', stdout=out)
        data = json.loads(out.getvalue())
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 12)
        for item in data:
            self.assertIn('check_name', item)
            self.assertIn('status', item)
            self.assertIn('severity', item)

    @override_settings(DEBUG=True)
    def test_debug_mode_detection(self):
        SecurityAudit.objects.all().delete()
        call_command('security_audit')
        debug_check = SecurityAudit.objects.filter(check_name='debug_mode').last()
        self.assertIsNotNone(debug_check)
        self.assertEqual(debug_check.status, 'fail')
        self.assertEqual(debug_check.severity, 'critical')

    def test_hsts_detection(self):
        SecurityAudit.objects.all().delete()
        call_command('security_audit')
        hsts_check = SecurityAudit.objects.filter(check_name='hsts_ssl').last()
        self.assertIsNotNone(hsts_check)
        self.assertIn(hsts_check.status, ('warn', 'pass'))

    def test_category_filter(self):
        SecurityAudit.objects.all().delete()
        call_command('security_audit', '--category', 'django_settings')
        for audit in SecurityAudit.objects.all():
            self.assertEqual(audit.category, 'django_settings')

    def test_middleware_check(self):
        SecurityAudit.objects.all().delete()
        call_command('security_audit')
        mw_check = SecurityAudit.objects.filter(check_name='middleware_check').last()
        self.assertIsNotNone(mw_check)
        self.assertEqual(mw_check.status, 'pass')


class TestSecurityLogModel(TestCase):
    """SecurityLogモデルのCRUDテスト"""

    def test_create_security_log(self):
        log = SecurityLog.objects.create(
            event_type='login_fail',
            severity='warning',
            username='testuser',
            ip_address='192.168.1.1',
            path='/login/',
            method='POST',
            detail='ログイン失敗',
        )
        self.assertIsNotNone(log.pk)
        self.assertEqual(log.event_type, 'login_fail')

    def test_security_log_str(self):
        log = SecurityLog(
            event_type='login_fail',
            severity='warning',
            username='testuser',
            ip_address='192.168.1.1',
        )
        self.assertIn('testuser', str(log))

    def test_security_log_with_user(self):
        import uuid as _uuid
        uname = f'logtest_{_uuid.uuid4().hex[:8]}'
        user = User.objects.create_user(username=uname, password='pass123')
        log = SecurityLog.objects.create(
            event_type='login_success',
            severity='info',
            user=user,
            username=uname,
            ip_address='127.0.0.1',
            path='/login/',
            method='POST',
        )
        self.assertEqual(log.user, user)


class TestCleanupSecurityLogs(TestCase):
    """cleanup_security_logsコマンドテスト"""

    def test_cleanup_old_logs(self):
        old_log = SecurityLog.objects.create(
            event_type='login_fail',
            severity='warning',
            username='old',
            ip_address='1.2.3.4',
        )
        SecurityLog.objects.filter(pk=old_log.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=91)
        )

        new_log = SecurityLog.objects.create(
            event_type='login_success',
            severity='info',
            username='new',
            ip_address='5.6.7.8',
        )

        call_command('cleanup_security_logs', '--days', '90')

        self.assertFalse(SecurityLog.objects.filter(pk=old_log.pk).exists())
        self.assertTrue(SecurityLog.objects.filter(pk=new_log.pk).exists())


class TestSecurityMiddleware(TestCase):
    """セキュリティミドルウェアテスト"""

    def test_login_fail_creates_log(self):
        SecurityLog.objects.all().delete()
        response = self.client.post('/login/', {'username': 'nonexistent', 'password': 'wrongpass'})
        logs = SecurityLog.objects.filter(event_type='login_fail')
        self.assertTrue(logs.exists())

    def test_api_without_auth_creates_log(self):
        SecurityLog.objects.all().delete()
        response = self.client.get('/api/iot/config/')
        if response.status_code in (401, 403):
            logs = SecurityLog.objects.filter(event_type='api_auth_fail')
            self.assertTrue(logs.exists())


class TestCostReportModel(TestCase):
    """CostReportモデルのCRUDテスト"""

    def test_create_cost_report(self):
        report = CostReport.objects.create(
            run_id=uuid.uuid4(),
            check_name='ec2_instances',
            resource_type='ec2',
            resource_id='i-12345',
            status='ok',
            estimated_monthly_cost=11.52,
            detail='t2.micro (稼働中)',
        )
        self.assertIsNotNone(report.pk)
        self.assertEqual(report.resource_type, 'ec2')

    def test_cost_report_str(self):
        report = CostReport(
            check_name='ec2_instances',
            resource_type='ec2',
            status='ok',
        )
        self.assertIn('ec2_instances', str(report))


class TestPaymentKeyCheck(TestCase):
    """PaymentMethod平文鍵検出テスト"""

    def test_plaintext_key_detection(self):
        from booking.models import PaymentMethod, Store
        store = Store.objects.create(name='テスト', address='東京')
        PaymentMethod.objects.create(
            store=store,
            method_type='paypay',
            display_name='PayPay',
            api_key='sk_live_plaintext_key_12345',
            api_secret='secret_plaintext_12345',
        )

        SecurityAudit.objects.all().delete()
        call_command('security_audit', '--category', 'credentials')
        check = SecurityAudit.objects.filter(check_name='payment_keys_encrypted').last()
        self.assertIsNotNone(check)
        self.assertEqual(check.status, 'fail')
        self.assertEqual(check.severity, 'critical')
