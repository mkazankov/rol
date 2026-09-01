from django.contrib import admin

from .models import Favorite, Station, StationTrack, Track


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "bitrate", "clickcount", "is_active", "updated_at")
    list_filter = ("country", "is_active")
    search_fields = ("name", "station_uuid", "tags")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "station", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "station__name", "station__station_uuid")


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ("full_name", "artist", "title", "created_at")
    search_fields = ("full_name", "artist", "title")
    ordering = ("full_name",)


@admin.register(StationTrack)
class StationTrackAdmin(admin.ModelAdmin):
    list_display = ("station", "track", "played_at")
    list_filter = ("station", "played_at")
    search_fields = (
        "station__name",
        "station__station_uuid",
        "track__full_name",
        "track__artist",
        "track__title",
    )
    autocomplete_fields = ("track",)
    ordering = ("-played_at",)
