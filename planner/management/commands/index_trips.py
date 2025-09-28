from django.core.management.base import BaseCommand
from planner.rag_logic import index_trips

class Command(BaseCommand):
    help = 'Indexes all trip plans into the vector store.'

    def handle(self, *args, **options):
        self.stdout.write('Starting to index trip plans...')
        index_trips()
        self.stdout.write(self.style.SUCCESS('Successfully indexed all trip plans.'))
