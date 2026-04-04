"""Add embed_token field to Schedule for iframe booking flow."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0118_add_is_demo_and_demo_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedule',
            name='embed_token',
            field=models.CharField(
                verbose_name='埋め込みトークン',
                max_length=43,
                unique=True,
                null=True,
                blank=True,
                db_index=True,
            ),
        ),
    ]
