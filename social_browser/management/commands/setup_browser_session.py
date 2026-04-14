"""ブラウザセッション初期設定コマンド

EC2 上で X11 転送付き SSH で実行し、各プラットフォームに手動ログインして
セッション Cookie を保存する。

使い方:
    # 一覧表示
    python manage.py setup_browser_session --list

    # Instagram セッション設定（Store ID=1）
    python manage.py setup_browser_session --store 1 --platform instagram

    # GBP セッション設定
    python manage.py setup_browser_session --store 1 --platform gbp

    # ステータス確認のみ
    python manage.py setup_browser_session --check

    # Playwright 環境チェック
    python manage.py setup_browser_session --check-env
"""
import os
import sys

from django.core.management.base import BaseCommand, CommandError

from social_browser.models import BrowserSession, BROWSER_PLATFORM_CHOICES
from social_browser.services.browser_service import (
    get_profile_dir,
    VALID_PLATFORMS,
)


PLATFORM_URLS = {
    'x': 'https://x.com/login',
    'instagram': 'https://www.instagram.com/accounts/login/',
    'gbp': 'https://business.google.com/',
    'tiktok': 'https://www.tiktok.com/login',
}

LOGIN_SUCCESS_INDICATORS = {
    'x': lambda url: 'home' in url.lower() and 'login' not in url.lower(),
    'instagram': lambda url: 'login' not in url.lower() and 'accounts' not in url.lower(),
    'gbp': lambda url: 'accounts.google.com' not in url,
    'tiktok': lambda url: 'login' not in url.lower(),
}


class Command(BaseCommand):
    help = 'ブラウザセッションの初期設定（手動ログイン → Cookie保存）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--store', type=int,
            help='対象の Store ID',
        )
        parser.add_argument(
            '--platform', type=str, choices=sorted(VALID_PLATFORMS),
            help='プラットフォーム (x, instagram, gbp, tiktok)',
        )
        parser.add_argument(
            '--list', action='store_true',
            help='全セッションの状態を一覧表示',
        )
        parser.add_argument(
            '--check', action='store_true',
            help='セッション状態を確認（ログイン試行なし）',
        )
        parser.add_argument(
            '--check-env', action='store_true',
            help='Playwright 環境チェック',
        )
        parser.add_argument(
            '--timeout', type=int, default=120,
            help='ログイン待機タイムアウト（秒、デフォルト: 120）',
        )

    def handle(self, *args, **options):
        if options['check_env']:
            return self._check_environment()

        if options['list']:
            return self._list_sessions()

        if options['check']:
            return self._check_sessions()

        store_id = options.get('store')
        platform = options.get('platform')

        if not store_id or not platform:
            raise CommandError('--store と --platform を指定してください（または --list / --check-env）')

        self._setup_session(store_id, platform, options['timeout'])

    def _check_environment(self):
        """Playwright 環境の動作確認"""
        self.stdout.write(self.style.MIGRATE_HEADING('=== Playwright 環境チェック ==='))

        # Python playwright
        try:
            import playwright
            self.stdout.write(self.style.SUCCESS(
                f'  playwright パッケージ: OK (v{playwright.__version__})'
            ))
        except ImportError:
            self.stdout.write(self.style.ERROR(
                '  playwright パッケージ: 未インストール\n'
                '  → pip install playwright'
            ))
            return

        # Chromium binary
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--disable-gpu'])
                version = browser.version
                browser.close()
                self.stdout.write(self.style.SUCCESS(
                    f'  Chromium ブラウザ: OK (v{version})'
                ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'  Chromium ブラウザ: エラー — {e}\n'
                '  → playwright install chromium --with-deps'
            ))
            return

        # Display check
        display = os.environ.get('DISPLAY', '')
        if display:
            self.stdout.write(self.style.SUCCESS(f'  DISPLAY: {display}'))
        else:
            self.stdout.write(self.style.WARNING(
                '  DISPLAY: 未設定（ヘッドレスのみ利用可能）\n'
                '  → 手動ログインには X11 転送が必要: ssh -X user@host'
            ))

        self.stdout.write(self.style.SUCCESS('\n環境チェック完了'))

    def _list_sessions(self):
        """全セッション一覧"""
        from booking.models import Store

        self.stdout.write(self.style.MIGRATE_HEADING('=== ブラウザセッション一覧 ==='))

        stores = Store.objects.all()
        if not stores.exists():
            self.stdout.write(self.style.WARNING('  店舗が登録されていません'))
            return

        for store in stores:
            self.stdout.write(f'\n  店舗: {store.name} (ID: {store.id})')
            sessions = BrowserSession.objects.filter(store=store)
            if not sessions.exists():
                self.stdout.write('    セッションなし')
                continue
            for session in sessions:
                status_style = {
                    'active': self.style.SUCCESS,
                    'expired': self.style.ERROR,
                    'setup_required': self.style.WARNING,
                }.get(session.status, self.style.WARNING)
                self.stdout.write(
                    f'    {session.get_platform_display():25s} '
                    f'{status_style(session.get_status_display())}'
                    f'  ({session.updated_at:%Y-%m-%d %H:%M})'
                )

    def _check_sessions(self):
        """全セッションの有効性を確認（ブラウザ起動なし）"""
        self.stdout.write(self.style.MIGRATE_HEADING('=== セッション状態チェック ==='))

        sessions = BrowserSession.objects.select_related('store').all()
        if not sessions.exists():
            self.stdout.write(self.style.WARNING('  セッションが登録されていません'))
            return

        for session in sessions:
            profile_dir = session.profile_dir
            state_file = os.path.join(profile_dir, 'storage_state.json')
            has_state = os.path.exists(state_file)
            state_size = os.path.getsize(state_file) if has_state else 0

            status_style = {
                'active': self.style.SUCCESS,
                'expired': self.style.ERROR,
                'setup_required': self.style.WARNING,
            }.get(session.status, self.style.WARNING)

            self.stdout.write(
                f'  {session.store.name} / {session.get_platform_display()}: '
                f'{status_style(session.get_status_display())} '
                f'| state_file: {"あり" if has_state else "なし"} '
                f'({state_size} bytes)'
            )

    def _setup_session(self, store_id, platform, timeout_sec):
        """対話的にブラウザを開き、手動ログイン後にセッションを保存"""
        from booking.models import Store

        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            raise CommandError(f'Store ID {store_id} が見つかりません')

        # DISPLAY 確認
        display = os.environ.get('DISPLAY', '')
        if not display:
            raise CommandError(
                'DISPLAY 環境変数が未設定です。\n'
                'X11 転送で接続してください: ssh -X user@host\n'
                'または Xvfb を起動: Xvfb :99 & export DISPLAY=:99'
            )

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'=== セッション設定: {store.name} / {platform} ==='
        ))

        profile_dir = get_profile_dir(store_id, platform)
        login_url = PLATFORM_URLS.get(platform, '')

        self.stdout.write(f'  プロファイル: {profile_dir}')
        self.stdout.write(f'  ログインURL: {login_url}')
        self.stdout.write(f'  タイムアウト: {timeout_sec}秒')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            '  ブラウザが開きます。手動でログインしてください。'
        ))
        self.stdout.write(self.style.WARNING(
            f'  ログイン完了後、{timeout_sec}秒以内に自動検出されます。'
        ))
        self.stdout.write('')

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise CommandError(
                'playwright が未インストールです。\n'
                'pip install playwright && playwright install chromium --with-deps'
            )

        # BrowserSession レコードを取得 or 作成
        session, created = BrowserSession.objects.get_or_create(
            store=store, platform=platform,
            defaults={
                'profile_dir': profile_dir,
                'status': 'setup_required',
            },
        )
        if not created:
            session.profile_dir = profile_dir
            session.save(update_fields=['profile_dir'])

        success = False
        try:
            from social_browser.services.browser_service import (
                create_browser_context,
                save_storage_state,
            )

            with sync_playwright() as p:
                # ヘッドレス=False（手動ログイン用）
                browser, context = create_browser_context(
                    p, profile_dir, headless=False,
                )
                try:
                    page = context.new_page()
                    page.goto(login_url, wait_until='networkidle', timeout=30000)

                    self.stdout.write('  ブラウザが開きました。ログインしてください...')

                    # ログイン成功をポーリング
                    check_fn = LOGIN_SUCCESS_INDICATORS.get(platform)
                    import time
                    start = time.time()
                    while time.time() - start < timeout_sec:
                        time.sleep(3)
                        current_url = page.url
                        if check_fn and check_fn(current_url):
                            self.stdout.write(self.style.SUCCESS(
                                f'  ログイン検出: {current_url}'
                            ))
                            success = True
                            break
                        elapsed = int(time.time() - start)
                        sys.stdout.write(
                            f'\r  待機中... {elapsed}/{timeout_sec}秒'
                        )
                        sys.stdout.flush()

                    self.stdout.write('')

                    if success:
                        save_storage_state(context, profile_dir)
                        self.stdout.write(self.style.SUCCESS(
                            '  セッション保存完了'
                        ))
                    else:
                        self.stdout.write(self.style.ERROR(
                            f'  タイムアウト ({timeout_sec}秒): ログインが検出されませんでした'
                        ))
                finally:
                    browser.close()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  エラー: {e}'))
            raise CommandError(str(e))

        # DB更新
        if success:
            session.status = 'active'
            session.save(update_fields=['status', 'updated_at'])
            self.stdout.write(self.style.SUCCESS(
                f'\n  セッション "{session}" を有効化しました'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                '\n  セッション設定に失敗しました。再実行してください。'
            ))
