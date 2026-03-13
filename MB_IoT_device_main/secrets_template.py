# secrets_template.py - 秘匿情報テンプレート
# このファイルを secrets.py にコピーして実際の値を入力してください。
# 重要: secrets.py は絶対に Git にコミットしないでください！
#
# 使い方:
#   cp secrets_template.py secrets.py
#   # secrets.py を編集して実際の認証情報を入力

secrets = {
    # WiFi認証情報（初回起動時に使用）
    "ssid": "YOUR_WIFI_SSID_HERE",
    "password": "YOUR_WIFI_PASSWORD_HERE",

    # Django バックエンドAPI設定
    "api_key": "YOUR_API_KEY_HERE",        # X-API-KEY ヘッダー値
    "device": "pico2w_001",                 # デバイス識別子
    "server_base": "https://your-server.com",  # Django サーバーベースURL（末尾スラッシュなし）

    # オプション: エンドポイントのオーバーライド（デフォルトと異なる場合のみ）
    # "events_endpoint": "/booking/api/iot/events/",
    # "config_endpoint": "/booking/api/iot/config/",

    # 診断モード（配線自動検出）
    "DIAGNOSTIC_MODE": False,               # True でフィジカルセンサースキャンモード有効化
}
