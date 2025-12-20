# booking/context_processors.py

from django.conf import settings


def global_context(request):
    """
    全テンプレートで共通して使いたい値があればここに足す。
    とりあえず今はダミーで最低限だけ返しておく。
    """
    return {
        # 例: フッターにバージョン出したくなったらこんな感じ
        # "PROJECT_VERSION": getattr(settings, "PROJECT_VERSION", "dev"),
    }