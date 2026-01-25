from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from booking.models import Staff, Store

class Command(BaseCommand):
    help = 'Bootstrap admin staff with specified username, store_id, manager and developer flags'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='Username for the user')
        parser.add_argument('--store_id', type=int, required=True, help='Store ID to associate')
        parser.add_argument('--manager', action='store_true', help='Set as store manager')
        parser.add_argument('--developer', action='store_true', help='Set as developer')

    def handle(self, *args, **options):
        username = options['username']
        store_id = options['store_id']
        is_manager = options['manager']
        is_developer = options['developer']

        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            raise CommandError(f'Store with id {store_id} does not exist')

        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password('password')  # Set a default password
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'User {username} created'))

        staff, created = Staff.objects.get_or_create(
            user=user,
            defaults={
                'store': store,
                'name': username,
                'is_store_manager': is_manager,
                'is_developer': is_developer,
            }
        )
        if not created:
            staff.store = store
            staff.is_store_manager = is_manager
            staff.is_developer = is_developer
            staff.save()
            self.stdout.write(self.style.SUCCESS(f'Staff {username} updated'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Staff {username} created'))

        self.stdout.write(self.style.SUCCESS('Bootstrap completed'))