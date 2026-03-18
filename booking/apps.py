from django.apps import AppConfig
from django.db import models
from django.utils.translation import gettext_lazy as _


class BookingConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'booking'
    verbose_name = _('登録情報メニュー')
    

