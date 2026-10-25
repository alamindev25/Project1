from django.core.management.base import BaseCommand
from django.core.management import call_command

from apps.cms.seed_data import seed_faq, seed_page
from apps.system_setting.seed_data import seed_system_color, seed_system_setting, seed_social_media, seed_smtp_credentials
from apps.user.seed_users import seed_users
from apps.subscription.seed_data import seed_subscription_plans


class Command(BaseCommand):
    help = 'Seed initial data. Optionally specify one or more app names to seed only those.'

    def add_arguments(self, parser):
        parser.add_argument('apps', nargs='*', help='List of seeders to run (e.g., subscription user)')

    def handle(self, *args, **options):
        selected = options.get('apps') or []

        seed_map = {
            'users': seed_users,
            'system_setting': seed_system_setting,
            'social_media': seed_social_media,
            'smtp': seed_smtp_credentials,
            'system_color': seed_system_color,
            'page': seed_page,
            'faq': seed_faq,
            'subscription': seed_subscription_plans,
            'dashboard': lambda: call_command('seed_dashboard_data'),
            'document_structures': lambda: call_command('seed_document_structures'),
            'landing_content': lambda: call_command('seed_landing_content'),
        }

        if selected:
            for name in selected:
                func = seed_map.get(name)
                if func:
                    self.stdout.write(f"Seeding {name}...")
                    func()
                else:
                    self.stdout.write(self.style.WARNING(f"Unknown seeder: {name}"))
        else:
            # run all
            seed_users()
            seed_system_setting()
            seed_social_media()
            seed_smtp_credentials()
            seed_system_color()
            seed_page()
            seed_faq()

            # subscription plans
            seed_subscription_plans()

            # dashboard defaults and landing content
            call_command('seed_dashboard_data')
            call_command('seed_document_structures')
            call_command('seed_landing_content')

        self.stdout.write(self.style.SUCCESS("Seeding completed."))