from django.test import TestCase

from radio.models import Station
from radio.services import classify_genre_from_tags


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
