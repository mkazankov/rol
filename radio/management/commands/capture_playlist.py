from django.core.management.base import BaseCommand

from radio.models import Station
from radio.services import fetch_current_track, record_current_track


class Command(BaseCommand):
    help = (
        "Capture the currently playing track for each active station and "
        "append it to the station's playlist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum number of stations to process (0 = no limit)",
        )
        parser.add_argument(
            "--station",
            dest="station_uuid",
            default="",
            help="Only process the station with the given station UUID",
        )

    def handle(self, *args, **options):
        limit = options["limit"] if options["limit"] > 0 else None
        station_uuid = options["station_uuid"]

        queryset = Station.objects.filter(is_active=True)
        if station_uuid:
            queryset = queryset.filter(station_uuid=station_uuid)
        if limit is not None:
            queryset = queryset[:limit]

        recorded = 0
        repeated = 0
        no_metadata = 0
        failed = 0

        for station in queryset.iterator(chunk_size=200):
            try:
                raw = fetch_current_track(station.stream_url)
            except Exception as exc:  # noqa: BLE001 - keep the run going per station
                failed += 1
                self.stderr.write(
                    self.style.WARNING(f"  [{station.name}] stream error: {exc}")
                )
                continue

            if not raw or not raw.strip():
                no_metadata += 1
                self.stdout.write(f"  [{station.name}] no metadata")
                continue

            prev_latest = (
                station.playlist.select_related("track")
                .order_by("-played_at")
                .values_list("track__full_name", flat=True)
                .first()
            )
            track = record_current_track(station, raw)
            if track is None:
                failed += 1
                self.stderr.write(
                    self.style.WARNING(f"  [{station.name}] failed to record track")
                )
                continue

            if prev_latest == track.full_name:
                # record_current_track skipped the row (consecutive repeat).
                repeated += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [{station.name}] {track.full_name} (repeat, skipped)"
                    )
                )
            else:
                recorded += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  [{station.name}] {track.full_name}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Playlist capture finished. "
                f"Recorded: {recorded}, Repeats skipped: {repeated}, "
                f"No metadata: {no_metadata}, Errors: {failed}."
            )
        )