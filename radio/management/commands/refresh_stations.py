from django.core.management.base import BaseCommand

from radio.services import LAST_FETCH_STATIONS_ERROR, refresh_station_db


class Command(BaseCommand):
    help = "Refresh radio stations database from radio-browser.info"

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-records",
            type=int,
            default=0,
            help="Maximum number of stations to fetch (0 = no limit)",
        )

    def handle(self, *args, **options):
        max_records = options["max_records"] if options["max_records"] > 0 else None
        stats = refresh_station_db(max_records=max_records)
        self.stdout.write(
            self.style.SUCCESS(
                "Stations refreshed. "
                f"Created: {stats['created']}, Updated: {stats['updated']}, Deleted: {stats['deleted']}, "
                f"Total: {stats['total']}."
            )
        )
        if stats["total"] == 0 and stats["created"] == 0 and stats["updated"] == 0:
            if LAST_FETCH_STATIONS_ERROR:
                self.stdout.write(self.style.WARNING(LAST_FETCH_STATIONS_ERROR + "\n"))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "No stations were imported or updated. The API may have returned an empty page, "
                        "or the run was limited. Check your network if this persists.\n"
                    )
                )
