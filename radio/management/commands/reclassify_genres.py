from django.core.management.base import BaseCommand

from radio.models import Station
from radio.services import classify_genre_from_tags


class Command(BaseCommand):
    help = "Recompute Station.genre from Station.tags using classify_genre_from_tags"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of rows per bulk_update batch",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        pending: list[Station] = []
        updated = 0

        for station in Station.objects.all().iterator(chunk_size=batch_size):
            new_genre = classify_genre_from_tags(station.tags or "")[:64]
            if new_genre != station.genre:
                station.genre = new_genre
                pending.append(station)
            if len(pending) >= batch_size:
                Station.objects.bulk_update(pending, ["genre"])
                updated += len(pending)
                pending = []

        if pending:
            Station.objects.bulk_update(pending, ["genre"])
            updated += len(pending)

        self.stdout.write(self.style.SUCCESS(f"Updated genre for {updated} station(s)."))
