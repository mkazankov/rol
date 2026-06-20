from django.contrib import admin

from .models import Favorite, Station


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
