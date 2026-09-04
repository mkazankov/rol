from django.core.management.base import BaseCommand

from radio.models import Station
from radio.services import is_station_stream_available


class Command(BaseCommand):
    help = (
        "Check the audio stream of radio stations and update their active "
        "status. By default only currently active stations are checked and "
        "are marked inactive when their stream is unavailable. Use "
        "--inactive to check only inactive stations and reactivate those "
        "whose stream becomes available again."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--inactive",
            action="store_true",
            help=(
                "Check only currently inactive stations and mark them as "
                "active when their audio stream becomes available again."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum number of stations to process (0 = no limit)",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=15,
            help="Timeout in seconds for each stream check (default: 15)",
        )

    def handle(self, *args, **options):
        check_inactive = options["inactive"]
        limit = options["limit"] if options["limit"] > 0 else None
        timeout = options["timeout"]

        if check_inactive:
            queryset = Station.objects.filter(is_active=False)
        else:
            queryset = Station.objects.filter(is_active=True)

        total = queryset.count()
        if limit is not None:
            station_ids = list(queryset.values_list("id", flat=True)[:limit])
        else:
            station_ids = list(queryset.values_list("id", flat=True))

        self.stdout.write(
            self.style.WARNING(
                f"Checking {len(station_ids)} station(s) "
                f"({'inactive' if check_inactive else 'active'})."
            )
        )

        activated = 0
        deactivated = 0
        unchanged = 0
        errors = 0

        for station_id in station_ids:
            station = Station.objects.get(pk=station_id)
            try:
                available = is_station_stream_available(
                    station.stream_url, timeout=timeout
                )
            except Exception as exc:  # noqa: BLE001 - keep the run going per station
                errors += 1
                self.stderr.write(
                    self.style.WARNING(
                        f"  [{station.name}] check error: {exc}"
                    )
                )
                continue

            if check_inactive:
                if available:
                    station.is_active = True
                    station.save(update_fields=["is_active", "updated_at"])
                    activated += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [{station.name}] stream available -> reactivated"
                        )
                    )
                else:
                    unchanged += 1
                    self.stdout.write(
                        f"  [{station.name}] stream still unavailable"
                    )
            else:
                if not available:
                    station.is_active = False
                    station.save(update_fields=["is_active", "updated_at"])
                    deactivated += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"  [{station.name}] stream unavailable -> deactivated"
                        )
                    )
                else:
                    unchanged += 1
                    self.stdout.write(
                        f"  [{station.name}] stream available"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                "Station check finished. "
                f"Checked: {len(station_ids)}, "
                f"Reactivated: {activated}, Deactivated: {deactivated}, "
                f"Unchanged: {unchanged}, Errors: {errors}."
            )
        )