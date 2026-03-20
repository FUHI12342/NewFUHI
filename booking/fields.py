"""Custom encrypted model fields using Fernet symmetric encryption."""
import base64

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


def _get_fernet():
    """Return a Fernet instance derived from SECRET_KEY."""
    key_bytes = settings.SECRET_KEY.encode('utf-8')[:32].ljust(32, b'\0')
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


class EncryptedCharField(models.CharField):
    """CharField that transparently encrypts/decrypts values in the DB.

    Values are stored as Fernet-encrypted base64 strings.
    Reading returns plaintext. Blank/empty values pass through unencrypted.
    """

    description = _('Encrypted text')

    def get_prep_value(self, value):
        """Encrypt before saving to DB."""
        value = super().get_prep_value(value)
        if not value:
            return value
        fernet = _get_fernet()
        return fernet.encrypt(value.encode('utf-8')).decode('utf-8')

    def from_db_value(self, value, expression, connection):
        """Decrypt when reading from DB."""
        if not value:
            return value
        try:
            fernet = _get_fernet()
            return fernet.decrypt(value.encode('utf-8')).decode('utf-8')
        except Exception:
            # If decryption fails, return raw value (for migration period)
            return value
