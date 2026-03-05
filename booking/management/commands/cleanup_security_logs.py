"""
セキュリティログ自動削除コマンド

Usage:
    python manage.py cleanup_security_logs [--days 90]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from booking.models import SecurityLog


class Command(BaseCommand):
    help = '指定日数より古いセキュリティログを削除します（デフォルト: 90日）'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90, help='保持日数（デフォルト: 90日）')

    def handle(self, *args, **options):
        days = options['days']
        cutoff = timezone.now() - timezone.timedelta(days=days)
        count, _ = SecurityLog.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f'{count}件の{days}日超セキュリティログを削除しました'))
