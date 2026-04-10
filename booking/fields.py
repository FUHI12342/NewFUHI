"""Custom encrypted model fields using Fernet symmetric encryption."""
import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

# Static salt for PBKDF2 key derivation — changing this invalidates all
# encrypted data, so treat it as immutable once deployed.
_KDF_SALT = b'NewFUHI-EncryptedCharField-v1'


def _get_fernet():
    """Return a Fernet instance with a key derived via PBKDF2 from SECRET_KEY.

    Uses PBKDF2-HMAC-SHA256 with 480_000 iterations (OWASP 2024 recommendation)
    and a static application-level salt. The resulting 32-byte key is base64-
    encoded for Fernet.
    """
    key_material = settings.SECRET_KEY.encode('utf-8')
    derived = hashlib.pbkdf2_hmac(
        'sha256', key_material, _KDF_SALT, iterations=480_000, dklen=32,
    )
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def _get_fernet_legacy():
    """Legacy Fernet using the old (weak) key derivation.

    Kept only for reading data encrypted before the PBKDF2 migration.
    """
    key_bytes = settings.SECRET_KEY.encode('utf-8')[:32].ljust(32, b'\0')
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


class EncryptedCharField(models.CharField):
    """CharField that transparently encrypts/decrypts values in the DB.

    Values are stored as Fernet-encrypted base64 strings.
    Reading returns plaintext. Blank/empty values pass through unencrypted.

    Encryption always uses the new PBKDF2-derived key. Decryption tries the
    new key first, then falls back to the legacy key for backward compatibility.
    Data re-encrypted with the new key on next save.
    """

    description = _('Encrypted text')

    def get_prep_value(self, value):
        """Encrypt before saving to DB (always uses new PBKDF2 key)."""
        value = super().get_prep_value(value)
        if not value:
            return value
        fernet = _get_fernet()
        return fernet.encrypt(value.encode('utf-8')).decode('utf-8')

    def from_db_value(self, value, expression, connection):
        """Decrypt when reading from DB. Tries new key, then legacy key."""
        if not value:
            return value
        # Try new PBKDF2-derived key first
        try:
            return _get_fernet().decrypt(value.encode('utf-8')).decode('utf-8')
        except Exception:
            pass
        # Fall back to legacy key (pre-migration data)
        try:
            return _get_fernet_legacy().decrypt(
                value.encode('utf-8'),
            ).decode('utf-8')
        except Exception:
            # If both fail, return raw value (unencrypted or corrupt)
            return value
