"""
プロジェクトルートの conftest.py

pytest-django の設定とプロジェクト全体で共有するフィクスチャを定義する。
"""
import os
import django
import pytest


# ===========================================================================
# Django 設定
# ===========================================================================

def pytest_configure(config):
    """pytest 起動時に Django 設定を強制的に読み込む"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings.local')

    # テスト用の環境変数が設定されていない場合はダミー値を設定
    _set_test_env_defaults()


def _set_test_env_defaults():
    """テスト実行に必要な環境変数にダミー値を設定する"""
    defaults = {
        'SECRET_KEY': 'test-secret-key-for-testing-only-not-for-production',
        'LINE_CHANNEL_ID': 'test_line_channel_id',
        'LINE_CHANNEL_SECRET': 'test_line_channel_secret',
        'LINE_REDIRECT_URL': 'http://localhost/callback',
        'LINE_ACCESS_TOKEN': 'test_line_access_token',
        'PAYMENT_API_KEY': 'test_payment_api_key',
        'PAYMENT_API_URL': 'http://localhost/api/payment',
        'WEBHOOK_URL_BASE': 'http://localhost',
        'CANCEL_URL': 'http://localhost/cancel',
        'LINE_USER_ID_ENCRYPTION_KEY': 'dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcw==',
        'LINE_USER_ID_HASH_PEPPER': 'test-hash-pepper-for-testing',
        'DEBUG': 'True',
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
