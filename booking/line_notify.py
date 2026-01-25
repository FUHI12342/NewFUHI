import os
import requests
from django.conf import settings


def send_line_notify(message: str) -> bool:
    """
    LINE Notify APIを使ってメッセージを送信。
    .env.local / .env.production / .env から LINE_NOTIFY_TOKEN を読み込む。
    失敗しても例外を投げず、Falseを返す。
    """
    token = getattr(settings, 'LINE_NOTIFY_TOKEN', None)
    if not token:
        print("LINE_NOTIFY_TOKEN is not set")
        return False

    url = "https://notify-api.line.me/api/notify"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "message": message,
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            return True
        else:
            print(f"LINE Notify failed: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"LINE Notify error: {e}")
        return False