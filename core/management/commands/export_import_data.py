import os
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings


class Command(BaseCommand):
    help = 'Export data from PostgreSQL to JSON or import from JSON'

    def add_arguments(self, parser):
        parser.add_argument(
            '--export',
            action='store_true',
            help='Export data to JSON file'
        )
        parser.add_argument(
            '--import',
            action='store_true',
            dest='import_data',
            help='Import data from JSON file'
        )
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Path to JSON file (e.g., data.json)'
        )
        parser.add_argument(
            '--app',
            type=str,
            default='core',
            help='Django app name (default: core)'
        )
        parser.add_argument(
            '--model',
            type=str,
            help='Specific model name (optional, exports all models of app if not specified)'
        )

    def handle(self, *args, **options):
        export = options['export']
        import_data = options['import_data']
        file_path = options['file']
        app = options['app']
        model = options.get('model')

        if export == import_data:
            raise CommandError('You must specify either --export or --import')

        # Ensure directory exists
        dirname = os.path.dirname(file_path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)

        if export:
            self.stdout.write(f'Exporting data to {file_path}...')
            if model:
                output = call_command('dumpdata', f'{app}.{model}', indent=2, stdout=None)
            else:
                output = call_command('dumpdata', app, indent=2, stdout=None)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(output)
            self.stdout.write(self.style.SUCCESS(f'Data exported to {file_path}'))

        elif import_data:
            if not os.path.exists(file_path):
                raise CommandError(f'File {file_path} does not exist')
            self.stdout.write(f'Importing data from {file_path}...')
            call_command('loaddata', file_path, app_label=app)
            self.stdout.write(self.style.SUCCESS('Data imported successfully'))
            