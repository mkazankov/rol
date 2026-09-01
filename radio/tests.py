from django.test import TestCase

from radio.models import Station, StationTrack, Track
from radio.services import classify_genre_from_tags, parse_track_parts, record_current_track


class ClassifyGenreFromTagsTests(TestCase):
    def test_empty_tags(self):
        self.assertEqual(classify_genre_from_tags(""), "")
        self.assertEqual(classify_genre_from_tags("   "), "")

    def test_exact_token(self):
        self.assertEqual(classify_genre_from_tags("jazz, news"), "Jazz")

    def test_multiword_tag_contains_genre(self):
        self.assertEqual(classify_genre_from_tags("classic rock, 80s"), "Rock")

    def test_no_known_genre_returns_empty(self):
        self.assertEqual(classify_genre_from_tags("kpop"), "")
        self.assertEqual(classify_genre_from_tags("easy listening"), "")

    def test_alias_edm(self):
        self.assertEqual(classify_genre_from_tags("edm, dance"), "Electronic")

    def test_alias_hip_space_hop(self):
        self.assertEqual(classify_genre_from_tags("hip hop, urban"), "Hip-Hop")

    def test_longer_genre_preferred_in_token_list(self):
        self.assertEqual(classify_genre_from_tags("metal, rock"), "Metal")

    def test_hyphenated_tag_matches_genre(self):
        self.assertEqual(classify_genre_from_tags("hip-hop"), "Hip-Hop")


class ReclassifyGenresCommandTests(TestCase):
    def test_bulk_updates_genre_from_tags(self):
        Station.objects.create(
            station_uuid="test-uuid-1",
            name="Test",
            stream_url="https://example.com/stream",
            tags="edm, news",
            genre="Wrong",
        )
        from django.core.management import call_command

        call_command("reclassify_genres", batch_size=10)
        station = Station.objects.get(station_uuid="test-uuid-1")
        self.assertEqual(station.genre, "Electronic")


def _make_station(uuid_suffix: str = "1") -> Station:
    return Station.objects.create(
        station_uuid=f"playlist-test-uuid-{uuid_suffix}",
        name=f"Test Station {uuid_suffix}",
        stream_url=f"https://example.com/stream{uuid_suffix}",
    )


class ParseTrackPartsTests(TestCase):
    def test_separator_with_spaces(self):
        self.assertEqual(parse_track_parts("AC/DC - Back In Black"), ("AC/DC", "Back In Black"))

    def test_separator_only_on_right(self):
        self.assertEqual(parse_track_parts("Artist- Title"), ("Artist", "Title"))

    def test_no_separator_is_title_only(self):
        self.assertEqual(parse_track_parts("Just A Title"), ("", "Just A Title"))

    def test_empty_and_blank(self):
        self.assertEqual(parse_track_parts(None), ("", ""))
        self.assertEqual(parse_track_parts("   "), ("", ""))


class RecordCurrentTrackTests(TestCase):
    def test_global_uniqueness_across_stations(self):
        station_a = _make_station("a")
        station_b = _make_station("b")

        track_a = record_current_track(station_a, "Nirvana - Smells Like Teen Spirit")
        track_b = record_current_track(station_b, "Nirvana - Smells Like Teen Spirit")

        self.assertEqual(track_a.pk, track_b.pk)
        self.assertEqual(Track.objects.filter(full_name="Nirvana - Smells Like Teen Spirit").count(), 1)

    def test_skips_consecutive_repeats_on_same_station(self):
        station = _make_station()
        record_current_track(station, "Artist - Song One")
        record_current_track(station, "Artist - Song One")

        self.assertEqual(StationTrack.objects.filter(station=station).count(), 1)

    def test_records_when_track_changes(self):
        station = _make_station()
        record_current_track(station, "Artist - Song One")
        record_current_track(station, "Artist - Song Two")

        entries = StationTrack.objects.filter(station=station)
        self.assertEqual(entries.count(), 2)
        self.assertEqual(entries[0].track.full_name, "Artist - Song Two")
        self.assertEqual(entries[1].track.full_name, "Artist - Song One")

    def test_none_or_blank_returns_none(self):
        station = _make_station()
        self.assertIsNone(record_current_track(station, None))
        self.assertIsNone(record_current_track(station, ""))
        self.assertEqual(StationTrack.objects.filter(station=station).count(), 0)

    def test_repeat_after_gap_creates_new_entry(self):
        station = _make_station()
        record_current_track(station, "Artist - Song One")
        record_current_track(station, "Artist - Song Two")
        record_current_track(station, "Artist - Song One")

        self.assertEqual(StationTrack.objects.filter(station=station).count(), 3)
