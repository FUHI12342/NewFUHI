"""Add layout field to CustomPage."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0101_custom_pages'),
    ]

    operations = [
        migrations.AddField(
            model_name='custompage',
            name='layout',
            field=models.CharField(
                choices=[('standard', '標準'), ('full_width', 'フルワイド')],
                default='standard',
                help_text='フルワイドはサイドバーなしのランディングページ向け',
                max_length=20,
                verbose_name='レイアウト',
            ),
        ),
    ]
