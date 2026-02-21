"""
Migration 0039: Backfill light_value and sound_value from existing IoTEvent.payload JSON.
"""
import json
from django.db import migrations


def backfill_sensor_values(apps, schema_editor):
    IoTEvent = apps.get_model('booking', 'IoTEvent')
    batch_size = 500
    updated = 0

    # Only update events that have payload but no light/sound values yet
    qs = IoTEvent.objects.filter(
        light_value__isnull=True,
        sound_value__isnull=True,
    ).exclude(payload='').exclude(payload__isnull=True)

    for event in qs.iterator(chunk_size=batch_size):
        try:
            data = json.loads(event.payload)
        except (json.JSONDecodeError, TypeError):
            continue

        changed = False
        light = data.get('light')
        sound = data.get('sound')

        if light is not None:
            try:
                event.light_value = float(light)
                changed = True
            except (ValueError, TypeError):
                pass

        if sound is not None:
            try:
                event.sound_value = float(sound)
                changed = True
            except (ValueError, TypeError):
                pass

        # Also check for pir
        pir = data.get('pir')
        if pir is not None:
            event.pir_triggered = bool(pir)
            changed = True

        if changed:
            event.save(update_fields=['light_value', 'sound_value', 'pir_triggered'])
            updated += 1

    print(f"Backfilled {updated} IoTEvent records with light/sound/pir values")


def reverse_backfill(apps, schema_editor):
    # No-op: don't null out values on reverse
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0038_iotevent_light_sound_pir_store_language_choices'),
    ]

    operations = [
        migrations.RunPython(backfill_sensor_values, reverse_backfill),
    ]
