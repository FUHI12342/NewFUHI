"""Backfill cancel_token for existing Schedule records."""
import secrets
import string

from django.db import migrations


def _generate_token(existing_tokens):
    """Generate a unique 8-char uppercase+digit token."""
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(100):
        token = ''.join(secrets.choice(alphabet) for _ in range(8))
        if token not in existing_tokens:
            return token
    raise RuntimeError('cancel_token backfill: unique generation failed')


def backfill_cancel_tokens(apps, schema_editor):
    Schedule = apps.get_model('booking', 'Schedule')
    existing_tokens = set(
        Schedule.objects.exclude(cancel_token__isnull=True)
        .exclude(cancel_token='')
        .values_list('cancel_token', flat=True)
    )
    schedules = Schedule.objects.filter(cancel_token__isnull=True)
    to_update = []
    for schedule in schedules.iterator():
        token = _generate_token(existing_tokens)
        existing_tokens.add(token)
        schedule.cancel_token = token
        to_update.append(schedule)
    if to_update:
        Schedule.objects.bulk_update(to_update, ['cancel_token'], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0105_schedule_cancel_token'),
    ]

    operations = [
        migrations.RunPython(backfill_cancel_tokens, migrations.RunPython.noop),
    ]
