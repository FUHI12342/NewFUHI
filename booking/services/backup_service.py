"""SQLite backup service — atomic backup with optional S3 upload."""
import logging
import os
import sqlite3
import time
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(settings.BASE_DIR) / 'backups'


def create_backup(trigger='manual'):
    """SQLiteデータベースのアトミックバックアップを作成する。

    Returns:
        BackupHistory instance
    """
    from booking.models import BackupConfig, BackupHistory

    config = BackupConfig.load()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    history = BackupHistory.objects.create(
        trigger=trigger,
        status='running',
    )

    start_time = time.monotonic()
    try:
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'newfuhi_backup_{timestamp}.sqlite3'
        backup_path = BACKUP_DIR / filename

        db_path = settings.DATABASES['default']['NAME']
        _perform_sqlite_backup(db_path, str(backup_path))

        file_size = backup_path.stat().st_size
        duration = time.monotonic() - start_time

        history.backup_file = str(backup_path)
        history.file_size_bytes = file_size
        history.duration_seconds = round(duration, 2)
        history.status = 'success'
        history.completed_at = timezone.now()

        # S3アップロード
        if config.s3_enabled:
            s3_key = _upload_to_s3(backup_path, config.s3_bucket, filename)
            if s3_key:
                history.s3_uploaded = True
                history.s3_key = s3_key

        history.save()

        # ローカル保持ポリシー適用
        _apply_local_retention(config.local_retention_count)

        # LINE通知
        if config.line_notify_enabled:
            _send_backup_notification(history)

        logger.info(
            'Backup completed: %s (%.1f KB, %.2fs)',
            filename, file_size / 1024, duration,
        )
        return history

    except Exception as e:
        duration = time.monotonic() - start_time
        history.status = 'failed'
        history.error_message = str(e)[:2000]
        history.duration_seconds = round(duration, 2)
        history.completed_at = timezone.now()
        history.save()

        logger.error('Backup failed: %s', e)

        from booking.models import BackupConfig
        config = BackupConfig.load()
        if config.line_notify_enabled:
            _send_backup_failure_notification(history)

        return history


def _perform_sqlite_backup(source_path, dest_path):
    """Python sqlite3.backup() でアトミックバックアップ。"""
    source_conn = sqlite3.connect(source_path)
    dest_conn = sqlite3.connect(dest_path)
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        source_conn.close()


def _upload_to_s3(backup_path, bucket, filename):
    """S3にバックアップファイルをアップロード。boto3が無い場合はスキップ。"""
    try:
        import boto3
        s3_key = f'backups/{filename}'
        s3 = boto3.client('s3')
        s3.upload_file(str(backup_path), bucket, s3_key)
        logger.info('Uploaded to S3: s3://%s/%s', bucket, s3_key)
        return s3_key
    except ImportError:
        logger.warning('boto3 not installed — S3 upload skipped')
        return ''
    except Exception as e:
        logger.error('S3 upload failed: %s', e)
        return ''


def _apply_local_retention(max_count):
    """ローカルバックアップの保持数制限を適用。古いファイルから削除。"""
    if not BACKUP_DIR.exists():
        return

    backups = sorted(
        BACKUP_DIR.glob('newfuhi_backup_*.sqlite3'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for old_backup in backups[max_count:]:
        try:
            old_backup.unlink()
            logger.info('Deleted old backup: %s', old_backup.name)
        except OSError as e:
            logger.warning('Failed to delete old backup %s: %s', old_backup.name, e)


def _send_backup_notification(history):
    """バックアップ成功通知をLINE Notifyで送信。"""
    try:
        from booking.line_notify import send_line_notify
        size_kb = history.file_size_bytes / 1024
        msg = (
            f'[バックアップ完了] {history.backup_file}\n'
            f'サイズ: {size_kb:.1f} KB / 所要時間: {history.duration_seconds:.1f}秒'
        )
        if history.s3_uploaded:
            msg += f'\nS3: {history.s3_key}'
        send_line_notify(msg)
    except Exception as e:
        logger.warning('Backup notification failed: %s', e)


def _send_backup_failure_notification(history):
    """バックアップ失敗通知。"""
    try:
        from booking.line_notify import send_line_notify
        msg = f'[バックアップ失敗] {history.error_message[:200]}'
        send_line_notify(msg)
    except Exception as e:
        logger.warning('Backup failure notification failed: %s', e)
