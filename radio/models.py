from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Station(models.Model):
    station_uuid = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    stream_url = models.URLField(max_length=1000)
    homepage = models.URLField(max_length=1000, blank=True)
    country = models.CharField(max_length=128, blank=True)
    language = models.CharField(max_length=128, blank=True)
    tags = models.TextField(blank=True)
    genre = models.CharField(max_length=64, blank=True)
    favicon = models.URLField(max_length=1000, blank=True)
    bitrate = models.PositiveIntegerField(default=0)
    clickcount = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-clickcount", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.country or 'Unknown'})"

    @property
    def genre_slug(self) -> str:
        return self.genre.lower().replace(" ", "-") if self.genre else ""

    @property
    def country_slug(self) -> str:
        return self.country.lower().replace(" ", "-") if self.country else ""


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorite_stations")
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "station"], name="unique_user_station_favorite")
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} -> {self.station.name}"


class Track(models.Model):
    """
    Global catalog of tracks shared across all stations.

    Uniqueness is enforced on `full_name`, which is the composed
    `artist - title` string (title-only when no artist is known).
    """
    artist = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255)
    full_name = models.CharField(max_length=512, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def _compose_full_name(self) -> str:
        if self.artist:
            return f"{self.artist} - {self.title}"
        return self.title

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_name = self._compose_full_name()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        self.full_name = self._compose_full_name()

    def __str__(self) -> str:
        return self.full_name


class StationTrack(models.Model):
    """
    One row per played track event for a station (the station playlist).

    `played_at` records when the track was observed on air.
    """
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="playlist")
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="played_on")
    played_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-played_at"]
        indexes = [
            models.Index(fields=["station", "-played_at"], name="idx_station_played_at"),
        ]

    def __str__(self) -> str:
        return f"{self.station.name}: {self.track.full_name}"
