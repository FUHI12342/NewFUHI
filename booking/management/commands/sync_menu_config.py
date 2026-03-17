"""AdminMenuConfig と DEFAULT_ALLOWED_MODELS を同期する management command

デプロイ後に実行し、DB 側の許可モデルリストにコード側のデフォルトを
マージすることで、新モデル追加時の反映漏れを防止する。

Usage:
    python manage.py sync_menu_config
    python manage.py sync_menu_config --dry-run
"""
from django.core.management.base import BaseCommand

from booking.admin_site import DEFAULT_ALLOWED_MODELS, GROUPS


class Command(BaseCommand):
    help = 'AdminMenuConfig の allowed_models にコード側のデフォルトをマージする'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='実際には更新せず差分のみ表示',
        )

    def handle(self, *args, **options):
        from booking.models import AdminMenuConfig
        from booking.admin_site import invalidate_menu_config_cache

        dry_run = options['dry_run']

        # GROUPS に登録された全モデルを収集
        all_group_models = set()
        for g in GROUPS:
            all_group_models.update(g['models'])

        updated_count = 0
        for config in AdminMenuConfig.objects.all():
            role = config.role
            current = set(config.allowed_models or [])
            defaults = DEFAULT_ALLOWED_MODELS.get(role)

            if defaults is None:
                # None = 全モデル表示のロール → DB レコードが制限している場合は警告
                self.stdout.write(
                    self.style.WARNING(
                        f"  {role}: DEFAULT_ALLOWED_MODELS=None (全モデル表示) "
                        f"だが DB に {len(current)} モデルの制限あり"
                    )
                )
                if not dry_run:
                    # DB レコードを削除して全モデル表示に戻す
                    config.delete()
                    self.stdout.write(
                        self.style.SUCCESS(f"  {role}: DB レコード削除 → 全モデル表示に復帰")
                    )
                    updated_count += 1
                continue

            defaults_set = set(defaults)
            missing = defaults_set - current
            if missing:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {role}: {len(missing)} モデル不足 → {sorted(missing)}"
                    )
                )
                if not dry_run:
                    merged = sorted(current | defaults_set)
                    config.allowed_models = merged
                    config.save(update_fields=['allowed_models', 'updated_at'])
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  {role}: マージ完了 ({len(current)} → {len(merged)} モデル)")
                    )
            else:
                self.stdout.write(f"  {role}: OK ({len(current)} モデル, 不足なし)")

        if dry_run:
            self.stdout.write(self.style.NOTICE("\n--dry-run: 実際の変更はありません"))
        else:
            invalidate_menu_config_cache()
            self.stdout.write(
                self.style.SUCCESS(f"\n同期完了: {updated_count} ロール更新, キャッシュ無効化済み")
            )
