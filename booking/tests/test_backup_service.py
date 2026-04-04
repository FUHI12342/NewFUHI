"""Tests for backup service — SQLite backup and retention policy."""
from pathlib import Path
from unittest.mock import patch, MagicMock

from django.test import TestCase

from booking.models import BackupConfig, BackupHistory
from booking.services.backup_service import (
    create_backup,
    _apply_local_retention,
    BACKUP_DIR,
)


class BackupConfigTest(TestCase):
    """Test BackupConfig singleton."""

    def test_singleton_load(self):
        config = BackupConfig.load()
        self.assertEqual(config.pk, 1)
        self.assertEqual(config.interval, 'off')
        self.assertTrue(config.is_active)

    def test_singleton_save_forces_pk1(self):
        config = BackupConfig(pk=99, interval='hourly')
        config.save()
        config.refresh_from_db()
        self.assertEqual(config.pk, 1)

    def test_default_values(self):
        config = BackupConfig.load()
        self.assertEqual(config.s3_bucket, 'mee-newfuhi-backups')
        self.assertEqual(config.local_retention_count, 30)
        self.assertEqual(config.s3_retention_days, 90)
        self.assertTrue(config.exclude_demo_data)
        self.assertTrue(config.line_notify_enabled)


class BackupServiceTest(TestCase):
    """Test backup creation (mocked sqlite3.backup for in-memory test DB)."""

    @patch('booking.services.backup_service._perform_sqlite_backup')
    @patch('booking.services.backup_service._send_backup_notification')
    def test_create_backup_success(self, mock_notify, mock_backup):
        """バックアップ作成が成功する"""
        # モック: 空ファイルを作成
        def fake_backup(src, dest):
            Path(dest).write_bytes(b'\x00' * 1024)
        mock_backup.side_effect = fake_backup

        history = create_backup(trigger='manual')
        self.assertEqual(history.status, 'success')
        self.assertEqual(history.trigger, 'manual')
        self.assertGreater(history.file_size_bytes, 0)
        self.assertIsNotNone(history.completed_at)
        self.assertTrue(history.backup_file.endswith('.sqlite3'))

        # クリーンアップ
        Path(history.backup_file).unlink(missing_ok=True)

    @patch('booking.services.backup_service._perform_sqlite_backup')
    @patch('booking.services.backup_service._send_backup_notification')
    def test_backup_history_created(self, mock_notify, mock_backup):
        """BackupHistoryレコードが作成される"""
        def fake_backup(src, dest):
            Path(dest).write_bytes(b'\x00' * 512)
        mock_backup.side_effect = fake_backup

        initial_count = BackupHistory.objects.count()
        history = create_backup(trigger='scheduled')
        self.assertEqual(BackupHistory.objects.count(), initial_count + 1)
        self.assertEqual(history.trigger, 'scheduled')

        Path(history.backup_file).unlink(missing_ok=True)

    @patch('booking.services.backup_service._perform_sqlite_backup')
    @patch('booking.services.backup_service._send_backup_notification')
    def test_backup_with_s3_disabled(self, mock_notify, mock_backup):
        """S3無効時にS3アップロードがスキップされる"""
        def fake_backup(src, dest):
            Path(dest).write_bytes(b'\x00' * 256)
        mock_backup.side_effect = fake_backup

        config = BackupConfig.load()
        config.s3_enabled = False
        config.save()

        history = create_backup(trigger='manual')
        self.assertFalse(history.s3_uploaded)
        self.assertEqual(history.s3_key, '')

        Path(history.backup_file).unlink(missing_ok=True)

    @patch('booking.services.backup_service._perform_sqlite_backup')
    def test_backup_failure_recorded(self, mock_backup):
        """バックアップ失敗時にエラーが記録される"""
        mock_backup.side_effect = RuntimeError('disk full')

        config = BackupConfig.load()
        config.line_notify_enabled = False
        config.save()

        history = create_backup(trigger='manual')
        self.assertEqual(history.status, 'failed')
        self.assertIn('disk full', history.error_message)
        self.assertIsNotNone(history.completed_at)


class RetentionPolicyTest(TestCase):
    """Test local backup retention policy."""

    def test_retention_deletes_old_files(self):
        """保持数を超えた古いバックアップが削除される"""
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        test_files = []
        for i in range(5):
            path = BACKUP_DIR / f'newfuhi_backup_test_{i:04d}.sqlite3'
            path.write_text(f'test content {i}')
            test_files.append(path)

        _apply_local_retention(max_count=3)

        remaining = list(BACKUP_DIR.glob('newfuhi_backup_test_*.sqlite3'))
        self.assertLessEqual(len(remaining), 3)

        # クリーンアップ
        for f in BACKUP_DIR.glob('newfuhi_backup_test_*.sqlite3'):
            f.unlink(missing_ok=True)
