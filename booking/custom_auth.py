# booking/custom_auth.py
from django.contrib.auth.apps import AuthConfig


class CustomAuthConfig(AuthConfig):
    """Django標準 auth の表示名だけ差し替えるための AppConfig。

    重要:
      - `name` は必ず `django.contrib.auth`
      - `label` は既存と同じ `auth`
    これにより、INSTALLED_APPS で `django.contrib.auth` を直接入れずに
    このConfigで置き換えられる。
    """

    name = "django.contrib.auth"
    label = "auth"
    verbose_name = "アカウント管理"  # 左メニューに出る名前