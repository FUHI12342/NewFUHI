from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
from celery.schedules import crontab

# Django settings を Celery 起動時に確実に参照できるようにする
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

# プロジェクト名は何でもよいが、-A project と合わせるなら 'project' が分かりやすい
app = Celery("project")

# Django の settings.py から CELERY_* を読む
app.config_from_object("django.conf:settings", namespace="CELERY")

# タスクを自動検出（booking/tasks.py など）
app.autodiscover_tasks()

# Beat スケジューラ（必要なら有効化）
# NOTE: booking.views 内の関数を直接 task として呼ぶより、booking/tasks.py に @shared_task を置くのが安全。
app.conf.beat_schedule = {
    "delete-every-minute": {
        "task": "booking.tasks.delete_temporary_schedules",
        "schedule": 60.0,
    },
    "check-low-stock-hourly": {
        "task": "booking.tasks.check_low_stock_and_notify",
        "schedule": crontab(minute=0),  # 毎時 00分
    },
    "check-property-alerts": {
        "task": "booking.tasks.check_property_alerts",
        "schedule": 300.0,  # 5分ごと
    },
    "security-audit-daily": {
        "task": "booking.tasks.run_security_audit",
        "schedule": crontab(hour=3, minute=0),  # 毎日 03:00
    },
    "cleanup-security-logs-weekly": {
        "task": "booking.tasks.cleanup_security_logs",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),  # 毎週日曜 04:00
    },
    "check-aws-costs-daily": {
        "task": "booking.tasks.check_aws_costs",
        "schedule": crontab(hour=6, minute=0),  # 毎日 06:00
    },
    # SNS自動投稿
    "post-daily-staff": {
        "task": "booking.tasks.task_post_daily_staff",
        "schedule": crontab(hour=9, minute=30),
    },
    "post-weekly-schedule": {
        "task": "booking.tasks.task_post_weekly_schedule",
        "schedule": crontab(hour=10, minute=0, day_of_week=1),
    },
    "refresh-social-tokens": {
        "task": "booking.tasks.task_refresh_social_tokens",
        "schedule": crontab(hour=3, minute=30),
    },
    # SNS 下書き自動生成（毎日 08:00）
    "generate-daily-drafts": {
        "task": "booking.tasks.task_generate_daily_drafts",
        "schedule": crontab(hour=8, minute=0),
    },
    # 予約投稿チェック（5分ごと）
    "check-scheduled-posts": {
        "task": "booking.tasks.task_check_scheduled_posts",
        "schedule": 300.0,
    },
    # LINE リマインダー
    "line-reminder-day-before": {
        "task": "booking.tasks.send_day_before_reminders",
        "schedule": crontab(hour=18, minute=0),  # 毎日18:00 JST
    },
    "line-reminder-same-day": {
        "task": "booking.tasks.send_same_day_reminders",
        "schedule": crontab(minute='*/30'),  # 30分ごと
    },
    # LINE セグメント日次更新
    "line-recompute-segments": {
        "task": "booking.tasks.recompute_customer_segments",
        "schedule": crontab(hour=4, minute=30),  # 毎日04:30
    },
    # デモデータ自動生成（30分毎）
    "generate-live-demo-data": {
        "task": "booking.tasks.generate_live_demo_data_task",
        "schedule": crontab(minute='*/30'),
    },
    # 自動バックアップ（毎分実行、内部で間隔判定）
    "run-scheduled-backup": {
        "task": "booking.tasks.run_scheduled_backup",
        "schedule": 60.0,
    },
}

# 互換のため明示（settings.py 側で CELERY_TASK_SERIALIZER などを設定しているなら不要）
app.conf.task_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.broker_connection_retry_on_startup = True

# タスクルーティング
app.conf.task_routes = {
    'booking.tasks.task_post_to_x': {'queue': 'x_api'},
    'social_browser.tasks.task_browser_post': {'queue': 'browser_posting'},
}