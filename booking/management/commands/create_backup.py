"""手動バックアップ作成コマンド。

Usage:
    python manage.py create_backup
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'SQLiteデータベースの手動バックアップを作成'

    def handle(self, *args, **options):
        from booking.services.backup_service import create_backup

        self.stdout.write('バックアップを作成中...')
        history = create_backup(trigger='manual')

        if history.status == 'success':
            size_kb = history.file_size_bytes / 1024
            self.stdout.write(self.style.SUCCESS(
                f'バックアップ完了: {history.backup_file}\n'
                f'サイズ: {size_kb:.1f} KB / 所要時間: {history.duration_seconds:.1f}秒'
            ))
            if history.s3_uploaded:
                self.stdout.write(f'S3: {history.s3_key}')
        else:
            self.stderr.write(self.style.ERROR(
                f'バックアップ失敗: {history.error_message}'
            ))
