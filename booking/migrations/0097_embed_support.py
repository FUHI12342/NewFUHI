from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0096_feature_visibility_toggles'),
    ]

    operations = [
        migrations.AddField(
            model_name='store',
            name='embed_api_key',
            field=models.CharField(
                blank=True, default='', help_text='WordPress等の外部サイトにiframe埋め込みする際のAPIキー',
                max_length=64, verbose_name='埋め込みAPIキー',
            ),
        ),
        migrations.AddField(
            model_name='store',
            name='embed_allowed_domains',
            field=models.TextField(
                blank=True, default='',
                help_text='iframe埋め込みを許可するドメイン（1行1ドメ���ン）。空の場合は全ドメイン許可',
                verbose_name='埋め込み許可ドメイン',
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='embed_enabled',
            field=models.BooleanField(
                default=False,
                help_text='ONにするとWordPress等からのiframe埋め込みが利用可能になります',
                verbose_name='外部埋め込みを有効化',
            ),
        ),
    ]
