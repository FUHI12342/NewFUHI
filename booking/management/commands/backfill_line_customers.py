"""既存 Schedule の LINE ユーザーを LineCustomer にバックフィル"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from booking.models import Schedule
from booking.models.line_customer import LineCustomer


class Command(BaseCommand):
    help = '既存 Schedule の line_user_hash/enc から LineCustomer を一括生成'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='実行せずに件数だけ表示')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # line_user_hash が設定されている Schedule をグループ化
        schedules_with_line = (
            Schedule.objects
            .filter(line_user_hash__isnull=False)
            .exclude(line_user_hash='')
            .values('line_user_hash')
            .annotate(
                count=Count('id'),
                total=Sum('price'),
            )
        )

        created_count = 0
        skipped_count = 0

        for row in schedules_with_line:
            line_hash = row['line_user_hash']

            if LineCustomer.objects.filter(line_user_hash=line_hash).exists():
                skipped_count += 1
                continue

            # 最新の Schedule から暗号化済み user_id を取得
            latest = (
                Schedule.objects
                .filter(line_user_hash=line_hash, line_user_enc__isnull=False)
                .exclude(line_user_enc='')
                .order_by('-start')
                .first()
            )
            if not latest:
                skipped_count += 1
                continue

            if dry_run:
                created_count += 1
                continue

            store = latest.store or (latest.staff.store if latest.staff else None)
            LineCustomer.objects.create(
                line_user_hash=line_hash,
                line_user_enc=latest.line_user_enc,
                display_name=latest.customer_name or '',
                visit_count=row['count'] or 0,
                total_spent=row['total'] or 0,
                store=store,
            )
            created_count += 1

        action = '作成予定' if dry_run else '作成'
        self.stdout.write(self.style.SUCCESS(
            f'完了: {action}={created_count}, スキップ={skipped_count}'
        ))
