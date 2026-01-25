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
    "check-low-stock-daily": {
        "task": "booking.tasks.check_low_stock_and_notify",
        "schedule": crontab(hour=9, minute=0),  # 毎日 09:00
    },
}

# 互換のため明示（settings.py 側で CELERY_TASK_SERIALIZER などを設定しているなら不要）
app.conf.task_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.broker_connection_retry_on_startup = True