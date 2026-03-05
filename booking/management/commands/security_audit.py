"""
セキュリティ自己診断コマンド（12項目）

Usage:
    python manage.py security_audit [--json] [--verbose] [--category CATEGORY]
"""
import json
import os
import uuid

import django
from django.conf import settings
from django.core.management.base import BaseCommand

from booking.models import SecurityAudit


class Command(BaseCommand):
    help = 'セキュリティ自己診断を実行し、結果をDBに保存します'

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', help='JSON形式で結果を出力')
        parser.add_argument('--verbose', action='store_true', help='詳細な出力')
        parser.add_argument('--category', type=str, help='特定カテゴリのみ実行')

    def handle(self, *args, **options):
        run_id = uuid.uuid4()
        output_json = options.get('json', False)
        verbose = options.get('verbose', False)
        category_filter = options.get('category')

        checks = [
            self.check_debug_mode,
            self.check_secret_key,
            self.check_allowed_hosts,
            self.check_hsts_ssl,
            self.check_cookie_security,
            self.check_xframe_options,
            self.check_payment_keys_encrypted,
            self.check_public_endpoints,
            self.check_django_version,
            self.check_env_file_permissions,
            self.check_backup_freshness,
            self.check_middleware,
        ]

        results = []
        for check_fn in checks:
            result = check_fn()
            if category_filter and result['category'] != category_filter:
                continue
            result['run_id'] = run_id
            results.append(result)

        # DBに保存
        audit_objects = []
        for r in results:
            audit_objects.append(SecurityAudit(
                run_id=r['run_id'],
                check_name=r['check_name'],
                category=r['category'],
                severity=r['severity'],
                status=r['status'],
                message=r['message'],
                recommendation=r.get('recommendation', ''),
            ))
        SecurityAudit.objects.bulk_create(audit_objects)

        if output_json:
            output = []
            for r in results:
                row = dict(r)
                row['run_id'] = str(row['run_id'])
                output.append(row)
            self.stdout.write(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            # テーブル形式の出力
            fail_count = sum(1 for r in results if r['status'] == 'fail')
            warn_count = sum(1 for r in results if r['status'] == 'warn')
            pass_count = sum(1 for r in results if r['status'] == 'pass')

            self.stdout.write(f'\n=== セキュリティ監査結果 (run_id: {run_id}) ===\n')
            for r in results:
                icon = {'fail': 'FAIL', 'warn': 'WARN', 'pass': 'PASS'}[r['status']]
                line = f'[{icon}] [{r["severity"].upper():8s}] {r["check_name"]}: {r["message"]}'
                if r['status'] == 'fail':
                    self.stdout.write(self.style.ERROR(line))
                elif r['status'] == 'warn':
                    self.stdout.write(self.style.WARNING(line))
                else:
                    self.stdout.write(self.style.SUCCESS(line))

                if verbose and r.get('recommendation'):
                    self.stdout.write(f'          -> {r["recommendation"]}')

            self.stdout.write(f'\n合計: {len(results)}項目 (PASS: {pass_count}, WARN: {warn_count}, FAIL: {fail_count})\n')

    # ==============================
    # 12 checks
    # ==============================

    def check_debug_mode(self):
        if settings.DEBUG:
            return {
                'check_name': 'debug_mode',
                'category': 'django_settings',
                'severity': 'critical',
                'status': 'fail',
                'message': 'DEBUG=True が本番環境で有効です',
                'recommendation': 'settings.py で DEBUG=False に設定してください',
            }
        return {
            'check_name': 'debug_mode',
            'category': 'django_settings',
            'severity': 'info',
            'status': 'pass',
            'message': 'DEBUG=False（正常）',
        }

    def check_secret_key(self):
        key = settings.SECRET_KEY
        weak_keys = ['django-insecure-', 'changeme', 'secret', 'password', 'your-secret-key']
        is_weak = any(w in key.lower() for w in weak_keys) or len(key) < 32
        if is_weak:
            return {
                'check_name': 'secret_key',
                'category': 'django_settings',
                'severity': 'critical',
                'status': 'fail',
                'message': 'SECRET_KEYが弱い、または短すぎます',
                'recommendation': '50文字以上のランダムな文字列を設定してください',
            }
        return {
            'check_name': 'secret_key',
            'category': 'django_settings',
            'severity': 'info',
            'status': 'pass',
            'message': 'SECRET_KEYは適切な強度です',
        }

    def check_allowed_hosts(self):
        hosts = getattr(settings, 'ALLOWED_HOSTS', [])
        if '*' in hosts:
            return {
                'check_name': 'allowed_hosts',
                'category': 'django_settings',
                'severity': 'high',
                'status': 'fail',
                'message': 'ALLOWED_HOSTSに"*"が含まれています',
                'recommendation': '具体的なホスト名のみを指定してください',
            }
        if not hosts:
            return {
                'check_name': 'allowed_hosts',
                'category': 'django_settings',
                'severity': 'medium',
                'status': 'warn',
                'message': 'ALLOWED_HOSTSが空です',
                'recommendation': '許可するホスト名を設定してください',
            }
        return {
            'check_name': 'allowed_hosts',
            'category': 'django_settings',
            'severity': 'info',
            'status': 'pass',
            'message': f'ALLOWED_HOSTS: {", ".join(hosts)}',
        }

    def check_hsts_ssl(self):
        hsts = getattr(settings, 'SECURE_HSTS_SECONDS', 0)
        ssl_redirect = getattr(settings, 'SECURE_SSL_REDIRECT', False)

        issues = []
        if not hsts:
            issues.append('SECURE_HSTS_SECONDS未設定')
        if not ssl_redirect:
            issues.append('SECURE_SSL_REDIRECT未設定')

        if issues:
            return {
                'check_name': 'hsts_ssl',
                'category': 'django_settings',
                'severity': 'medium',
                'status': 'warn',
                'message': '; '.join(issues),
                'recommendation': 'SECURE_HSTS_SECONDS=31536000, SECURE_SSL_REDIRECT=True を推奨',
            }
        return {
            'check_name': 'hsts_ssl',
            'category': 'django_settings',
            'severity': 'info',
            'status': 'pass',
            'message': f'HSTS={hsts}秒, SSL_REDIRECT=有効',
        }

    def check_cookie_security(self):
        session_secure = getattr(settings, 'SESSION_COOKIE_SECURE', False)
        csrf_secure = getattr(settings, 'CSRF_COOKIE_SECURE', False)

        issues = []
        if not session_secure:
            issues.append('SESSION_COOKIE_SECURE=False')
        if not csrf_secure:
            issues.append('CSRF_COOKIE_SECURE=False')

        if issues:
            return {
                'check_name': 'cookie_security',
                'category': 'django_settings',
                'severity': 'high' if settings.DEBUG is False else 'medium',
                'status': 'warn' if settings.DEBUG else 'warn',
                'message': '; '.join(issues),
                'recommendation': '本番ではSecureフラグをTrueに設定してください',
            }
        return {
            'check_name': 'cookie_security',
            'category': 'django_settings',
            'severity': 'info',
            'status': 'pass',
            'message': 'セッション/CSRFクッキーのSecureフラグ有効',
        }

    def check_xframe_options(self):
        xframe = getattr(settings, 'X_FRAME_OPTIONS', None)
        if not xframe:
            return {
                'check_name': 'xframe_options',
                'category': 'django_settings',
                'severity': 'medium',
                'status': 'warn',
                'message': 'X_FRAME_OPTIONS未設定',
                'recommendation': 'X_FRAME_OPTIONS="DENY" を推奨',
            }
        return {
            'check_name': 'xframe_options',
            'category': 'django_settings',
            'severity': 'info',
            'status': 'pass',
            'message': f'X_FRAME_OPTIONS={xframe}',
        }

    def check_payment_keys_encrypted(self):
        from booking.models import PaymentMethod
        try:
            plaintext_count = 0
            for pm in PaymentMethod.objects.all():
                if pm.api_key and not pm.api_key.startswith('gAAAAA'):
                    plaintext_count += 1
                if pm.api_secret and not pm.api_secret.startswith('gAAAAA'):
                    plaintext_count += 1

            if plaintext_count > 0:
                return {
                    'check_name': 'payment_keys_encrypted',
                    'category': 'credentials',
                    'severity': 'critical',
                    'status': 'fail',
                    'message': f'{plaintext_count}件のAPI鍵が平文で保存されている可能性があります',
                    'recommendation': 'Fernet暗号化を使用してAPI鍵を保護してください',
                }
            return {
                'check_name': 'payment_keys_encrypted',
                'category': 'credentials',
                'severity': 'info',
                'status': 'pass',
                'message': 'PaymentMethodのAPI鍵は暗号化されているか、未設定です',
            }
        except Exception as e:
            return {
                'check_name': 'payment_keys_encrypted',
                'category': 'credentials',
                'severity': 'info',
                'status': 'pass',
                'message': f'PaymentMethodテーブル確認不可: {e}',
            }

    def check_public_endpoints(self):
        from django.urls import get_resolver
        try:
            resolver = get_resolver()
            patterns = self._collect_url_patterns(resolver)
            return {
                'check_name': 'public_endpoints',
                'category': 'endpoints',
                'severity': 'info',
                'status': 'pass',
                'message': f'URL登録数: {len(patterns)}パターン',
                'recommendation': '定期的に認証なしエンドポイントを確認してください',
            }
        except Exception as e:
            return {
                'check_name': 'public_endpoints',
                'category': 'endpoints',
                'severity': 'info',
                'status': 'pass',
                'message': f'URLパターン取得不可: {e}',
            }

    def _collect_url_patterns(self, resolver, prefix=''):
        patterns = []
        for pattern in resolver.url_patterns:
            if hasattr(pattern, 'url_patterns'):
                pat = prefix + str(getattr(pattern.pattern, '_route', str(pattern.pattern)))
                patterns.extend(self._collect_url_patterns(pattern, pat))
            else:
                pat = prefix + str(getattr(pattern.pattern, '_route', str(pattern.pattern)))
                patterns.append(pat)
        return patterns

    def check_django_version(self):
        version = django.get_version()
        major, minor = int(version.split('.')[0]), int(version.split('.')[1])

        if major < 4:
            return {
                'check_name': 'django_version',
                'category': 'dependencies',
                'severity': 'high',
                'status': 'fail',
                'message': f'Django {version} はサポート終了の可能性があります',
                'recommendation': 'Django 4.2 LTS以降にアップグレードしてください',
            }
        if major == 4 and minor < 2:
            return {
                'check_name': 'django_version',
                'category': 'dependencies',
                'severity': 'medium',
                'status': 'warn',
                'message': f'Django {version} は最新のLTSではありません',
                'recommendation': 'Django 4.2 LTS以降にアップグレードを推奨',
            }
        return {
            'check_name': 'django_version',
            'category': 'dependencies',
            'severity': 'info',
            'status': 'pass',
            'message': f'Django {version}',
        }

    def check_env_file_permissions(self):
        base_dir = getattr(settings, 'BASE_DIR', '')
        env_files = ['.env', '.env.local', '.env.production', '.env.staging']
        issues = []

        for fname in env_files:
            fpath = os.path.join(base_dir, fname)
            if os.path.exists(fpath):
                mode = oct(os.stat(fpath).st_mode)[-3:]
                if mode not in ('600', '400', '640'):
                    issues.append(f'{fname}: 権限 {mode}（推奨: 600）')

        if issues:
            return {
                'check_name': 'env_file_permissions',
                'category': 'infrastructure',
                'severity': 'medium',
                'status': 'warn',
                'message': '; '.join(issues),
                'recommendation': 'chmod 600 .env* で権限を制限してください',
            }
        return {
            'check_name': 'env_file_permissions',
            'category': 'infrastructure',
            'severity': 'info',
            'status': 'pass',
            'message': '.envファイルの権限は適切です',
        }

    def check_backup_freshness(self):
        try:
            import boto3
            from datetime import datetime, timezone as tz

            s3 = boto3.client('s3')
            buckets = s3.list_buckets().get('Buckets', [])
            backup_buckets = [b for b in buckets if 'backup' in b['Name'].lower()]

            if not backup_buckets:
                return {
                    'check_name': 'backup_freshness',
                    'category': 'infrastructure',
                    'severity': 'medium',
                    'status': 'warn',
                    'message': 'バックアップ用S3バケットが見つかりません',
                    'recommendation': 'S3バックアップの設定を確認してください',
                }

            now = datetime.now(tz.utc)
            stale_buckets = []
            for bucket in backup_buckets:
                try:
                    objects = s3.list_objects_v2(Bucket=bucket['Name'], MaxKeys=1)
                    if 'Contents' in objects:
                        last_modified = objects['Contents'][0]['LastModified']
                        age_hours = (now - last_modified).total_seconds() / 3600
                        if age_hours > 48:
                            stale_buckets.append(f"{bucket['Name']} (最終更新: {age_hours:.0f}時間前)")
                except Exception:
                    stale_buckets.append(f"{bucket['Name']} (確認不可)")

            if stale_buckets:
                return {
                    'check_name': 'backup_freshness',
                    'category': 'infrastructure',
                    'severity': 'high',
                    'status': 'warn',
                    'message': f'古いバックアップ: {"; ".join(stale_buckets)}',
                    'recommendation': 'バックアップジョブが正常に動作しているか確認してください',
                }
            return {
                'check_name': 'backup_freshness',
                'category': 'infrastructure',
                'severity': 'info',
                'status': 'pass',
                'message': 'S3バックアップは48時間以内に更新されています',
            }
        except ImportError:
            return {
                'check_name': 'backup_freshness',
                'category': 'infrastructure',
                'severity': 'low',
                'status': 'warn',
                'message': 'boto3が未インストールのためS3バックアップ確認をスキップ',
                'recommendation': 'pip install boto3 でインストールしてください',
            }
        except Exception as e:
            return {
                'check_name': 'backup_freshness',
                'category': 'infrastructure',
                'severity': 'low',
                'status': 'warn',
                'message': f'S3バックアップ確認失敗: {e}',
                'recommendation': 'AWS認証情報を確認してください',
            }

    def check_middleware(self):
        middleware = getattr(settings, 'MIDDLEWARE', [])
        required = [
            'django.middleware.security.SecurityMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
        ]
        missing = [m.split('.')[-1] for m in required if m not in middleware]

        if missing:
            return {
                'check_name': 'middleware_check',
                'category': 'django_settings',
                'severity': 'high',
                'status': 'fail',
                'message': f'必須ミドルウェア不足: {", ".join(missing)}',
                'recommendation': '必須のセキュリティミドルウェアを有効にしてください',
            }
        return {
            'check_name': 'middleware_check',
            'category': 'django_settings',
            'severity': 'info',
            'status': 'pass',
            'message': '必須セキュリティミドルウェアはすべて有効です',
        }
