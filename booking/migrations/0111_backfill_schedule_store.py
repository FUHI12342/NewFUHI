"""Backfill Schedule.store from staff.store for all existing records."""
from django.db import migrations


def backfill_schedule_store(apps, schema_editor):
    Schedule = apps.get_model('booking', 'Schedule')
    for schedule in Schedule.objects.filter(store__isnull=True).select_related('staff'):
        if schedule.staff_id and schedule.staff.store_id:
            schedule.store_id = schedule.staff.store_id
            schedule.save(update_fields=['store_id'])


class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0110_shiftassignment_store_schedule_store'),
    ]

    operations = [
        migrations.RunPython(
            backfill_schedule_store,
            migrations.RunPython.noop,
        ),
    ]
