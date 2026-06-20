from django.urls import path

from .views import FavoritesView, HomeView, SignupView, current_track, refresh_stations, toggle_favorite

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("signup/", SignupView.as_view(), name="signup"),
    path("favorites/", FavoritesView.as_view(), name="favorites"),
    path("favorite/<str:station_id>/", toggle_favorite, name="toggle_favorite"),
    path("refresh-stations/", refresh_stations, name="refresh_stations"),
    path("current-track/<str:station_id>/", current_track, name="current_track"),
]
