"""仮予約を15分経過で自動キャンセルするコマンド

cron で毎分実行:
  * * * * * cd /home/ubuntu/NewFUHI && .venv/bin/python manage.py cancel_expired_temp_bookings
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from booking.models import Schedule


class Command(BaseCommand):
    help = '15分以上経過した仮予約(is_temporary=True)を自動キャンセルする'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=15)
        expired = Schedule.objects.filter(
            is_temporary=True,
            is_cancelled=False,
        ).filter(
            # temporary_booked_at がある場合はそれで判定、NULLの場合は start で判定
            Q(temporary_booked_at__lt=cutoff, temporary_booked_at__isnull=False)
            | Q(temporary_booked_at__isnull=True, start__lt=cutoff)
        )
        count = expired.count()
        if count:
            expired.update(is_cancelled=True)
            self.stdout.write(self.style.SUCCESS(f'{count} 件の仮予約を自動キャンセルしました'))
        else:
            self.stdout.write('期限切れの仮予約はありません')
