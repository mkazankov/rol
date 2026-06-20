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
