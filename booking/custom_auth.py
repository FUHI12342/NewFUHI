# booking/custom_auth.py
from django.contrib.auth.apps import AuthConfig
from django.utils.translation import gettext_lazy as _


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
    verbose_name = _("アカウント管理")