from django.urls import path

from .views import (
    CountriesView,
    CountryDetailView,
    FavoritesView,
    GenreDetailView,
    GenresView,
    HomeView,
    SignupView,
    StationDetailView,
    current_track,
    download_favorites_m3u,
    refresh_stations,
    toggle_favorite,
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("signup/", SignupView.as_view(), name="signup"),
    path("favorites/", FavoritesView.as_view(), name="favorites"),
    path("favorites/download.m3u", download_favorites_m3u, name="download_favorites_m3u"),
    path("genres/", GenresView.as_view(), name="genres"),
    path("genre/<str:genre_slug>/", GenreDetailView.as_view(), name="genre_detail"),
    path("countries/", CountriesView.as_view(), name="countries"),
    path("country/<str:country_slug>/", CountryDetailView.as_view(), name="country_detail"),
    path("station/<str:station_id>/", StationDetailView.as_view(), name="station_detail"),
    path("favorite/<str:station_id>/", toggle_favorite, name="toggle_favorite"),
    path("refresh-stations/", refresh_stations, name="refresh_stations"),
    path("current-track/<str:station_id>/", current_track, name="current_track"),
]
