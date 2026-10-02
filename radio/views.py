from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db import models
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic.edit import FormView

from .models import Favorite, Station
from .services import fetch_current_track, fetch_icy_info, record_current_track, refresh_station_db


QUALITY_CHOICES = [
    ("low", "Low (<96 kbps)"),
    ("medium", "Medium (96-191 kbps)"),
    ("high", "High (192-319 kbps)"),
    ("ultra", "Ultra (320+ kbps)"),
]


def _quality_level(bitrate: int) -> str:
    if bitrate < 96:
        return "low"
    if bitrate < 192:
        return "medium"
    if bitrate < 320:
        return "high"
    return "ultra"


def _quality_label(level: str) -> str:
    labels = {
        "low": "LOW",
        "medium": "MEDIUM",
        "high": "HIGH",
        "ultra": "ULTRA",
    }
    return labels.get(level, "UNKNOWN")


def _favorite_ids_for_request(request: HttpRequest) -> set[str]:
    if request.user.is_authenticated:
        return set(
            Favorite.objects.filter(user=request.user).values_list("station__station_uuid", flat=True)
        )
    return set(request.session.get("favorites", []))


def _sync_session_favorites_to_user(request: HttpRequest) -> None:
    if not request.user.is_authenticated:
        return
    session_favorites = set(request.session.get("favorites", []))
    if not session_favorites:
        return

    stations = Station.objects.filter(station_uuid__in=session_favorites)
    for station in stations:
        Favorite.objects.get_or_create(user=request.user, station=station)

    request.session["favorites"] = []
    request.session.modified = True


class HomeView(View):
    template_name = "radio/home.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        query = request.GET.get("q", "").strip()
        country = request.GET.get("country", "").strip()
        genre = request.GET.get("genre", "").strip()
        quality = request.GET.get("quality", "").strip().lower()
        _sync_session_favorites_to_user(request)
        favorites = _favorite_ids_for_request(request)

        stations_qs = Station.objects.filter(is_active=True)
        if query:
            stations_qs = stations_qs.filter(name__icontains=query)
        if country:
            stations_qs = stations_qs.filter(country__iexact=country)
        if genre:
            stations_qs = stations_qs.filter(genre__iexact=genre)
        if quality == "low":
            stations_qs = stations_qs.filter(bitrate__lt=96)
        elif quality == "medium":
            stations_qs = stations_qs.filter(bitrate__gte=96, bitrate__lt=192)
        elif quality == "high":
            stations_qs = stations_qs.filter(bitrate__gte=192, bitrate__lt=320)
        elif quality == "ultra":
            stations_qs = stations_qs.filter(bitrate__gte=320)

        stations = list(stations_qs[:80])
        for station in stations:
            level = _quality_level(station.bitrate)
            station.quality_level = level
            station.quality_label = _quality_label(level)
        countries = (
            Station.objects.filter(is_active=True)
            .exclude(country="")
            .values_list("country", flat=True)
            .distinct()
            .order_by("country")
        )
        genres = (
            Station.objects.filter(is_active=True)
            .exclude(genre="")
            .values_list("genre", flat=True)
            .distinct()
            .order_by("genre")
        )

        context = {
            "query": query,
            "country": country,
            "genre": genre,
            "quality": quality,
            "quality_choices": QUALITY_CHOICES,
            "stations": stations,
            "countries": list(countries),
            "genres": list(genres),
            "favorites": favorites,
        }
        return render(request, self.template_name, context)


class SignupView(FormView):
    template_name = "registration/signup.html"
    form_class = UserCreationForm
    success_url = reverse_lazy("home")

    def form_valid(self, form: UserCreationForm) -> HttpResponse:
        user = form.save()
        login(self.request, user)
        _sync_session_favorites_to_user(self.request)
        messages.success(self.request, "Account created successfully.")
        return super().form_valid(form)


class FavoritesView(View):
    template_name = "radio/favorites.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            favorites_qs = (
                Favorite.objects.filter(user=request.user)
                .select_related("station")
                .order_by("-created_at")
            )
            stations = [fav.station for fav in favorites_qs]
            favorite_ids = {station.station_uuid for station in stations}
        else:
            favorite_ids = set(request.session.get("favorites", []))
            stations = list(Station.objects.filter(station_uuid__in=favorite_ids))

        for station in stations:
            level = _quality_level(station.bitrate)
            station.quality_level = level
            station.quality_label = _quality_label(level)

        return render(
            request,
            self.template_name,
            {"stations": stations, "favorites": favorite_ids},
        )


class StationDetailView(View):
    template_name = "radio/station_detail.html"
    playlist_limit = 50

    def get(self, request: HttpRequest, station_id: str) -> HttpResponse:
        station = get_object_or_404(Station, station_uuid=station_id)

        level = _quality_level(station.bitrate)
        station.quality_level = level
        station.quality_label = _quality_label(level)

        favorites = _favorite_ids_for_request(request)

        playlist = (
            station.playlist.select_related("track")
            .order_by("-played_at")[: self.playlist_limit]
        )

        similar_stations = (
            Station.objects.filter(genre__iexact=station.genre, is_active=True)
            .exclude(station_uuid=station_id)[:5]
        )
        for s in similar_stations:
            lvl = _quality_level(s.bitrate)
            s.quality_level = lvl
            s.quality_label = _quality_label(lvl)

        return render(
            request,
            self.template_name,
            {
                "station": station,
                "favorites": favorites,
                "playlist": playlist,
                "similar_stations": similar_stations,
            },
        )


class GenresView(View):
    """Lists all genres with station counts."""
    template_name = "radio/genres.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        genres = (
            Station.objects.filter(is_active=True)
            .exclude(genre="")
            .values("genre")
            .annotate(count=models.Count("id"))
            .order_by("genre")
        )
        return render(request, self.template_name, {"genres": genres})


class GenreDetailView(View):
    """Stations for a single genre with country and quality filters."""
    template_name = "radio/genre_detail.html"
    page_size = 80

    def get(self, request: HttpRequest, genre_slug: str) -> HttpResponse:
        genre_display = genre_slug.replace("-", " ").title()

        stations_qs = Station.objects.filter(genre__iexact=genre_slug, is_active=True)

        country = request.GET.get("country", "").strip()
        quality = request.GET.get("quality", "").strip().lower()

        if country:
            stations_qs = stations_qs.filter(country__iexact=country)
        if quality == "low":
            stations_qs = stations_qs.filter(bitrate__lt=96)
        elif quality == "medium":
            stations_qs = stations_qs.filter(bitrate__gte=96, bitrate__lt=192)
        elif quality == "high":
            stations_qs = stations_qs.filter(bitrate__gte=192, bitrate__lt=320)
        elif quality == "ultra":
            stations_qs = stations_qs.filter(bitrate__gte=320)

        stations = list(stations_qs[: self.page_size])
        for station in stations:
            lvl = _quality_level(station.bitrate)
            station.quality_level = lvl
            station.quality_label = _quality_label(lvl)

        favorites = _favorite_ids_for_request(request)

        countries = (
            Station.objects.filter(genre__iexact=genre_slug, is_active=True)
            .exclude(country="")
            .values_list("country", flat=True)
            .distinct()
            .order_by("country")
        )

        return render(
            request,
            self.template_name,
            {
                "genre": genre_display,
                "genre_slug": genre_slug,
                "stations": stations,
                "countries": list(countries),
                "country": country,
                "quality": quality,
                "quality_choices": QUALITY_CHOICES,
                "favorites": favorites,
            },
        )


class CountriesView(View):
    """Lists all countries with station counts."""
    template_name = "radio/countries.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        countries = (
            Station.objects.filter(is_active=True)
            .exclude(country="")
            .values("country")
            .annotate(count=models.Count("id"))
            .order_by("country")
        )
        return render(request, self.template_name, {"countries": countries})


class CountryDetailView(View):
    """Stations for a single country with genre and quality filters."""
    template_name = "radio/country_detail.html"
    page_size = 80

    def get(self, request: HttpRequest, country_slug: str) -> HttpResponse:
        country_display = country_slug.replace("-", " ").title()

        stations_qs = Station.objects.filter(country__iexact=country_display, is_active=True)

        genre = request.GET.get("genre", "").strip()
        quality = request.GET.get("quality", "").strip().lower()

        if genre:
            stations_qs = stations_qs.filter(genre__iexact=genre)
        if quality == "low":
            stations_qs = stations_qs.filter(bitrate__lt=96)
        elif quality == "medium":
            stations_qs = stations_qs.filter(bitrate__gte=96, bitrate__lt=192)
        elif quality == "high":
            stations_qs = stations_qs.filter(bitrate__gte=192, bitrate__lt=320)
        elif quality == "ultra":
            stations_qs = stations_qs.filter(bitrate__gte=320)

        stations = list(stations_qs[: self.page_size])
        for station in stations:
            lvl = _quality_level(station.bitrate)
            station.quality_level = lvl
            station.quality_label = _quality_label(lvl)

        favorites = _favorite_ids_for_request(request)

        genres = (
            Station.objects.filter(country__iexact=country_display, is_active=True)
            .exclude(genre="")
            .values_list("genre", flat=True)
            .distinct()
            .order_by("genre")
        )

        return render(
            request,
            self.template_name,
            {
                "country": country_display,
                "country_slug": country_slug,
                "stations": stations,
                "genres": list(genres),
                "genre": genre,
                "quality": quality,
                "quality_choices": QUALITY_CHOICES,
                "favorites": favorites,
            },
        )


def toggle_favorite(request: HttpRequest, station_id: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("home")

    station = get_object_or_404(Station, station_uuid=station_id)

    if request.user.is_authenticated:
        favorite = Favorite.objects.filter(user=request.user, station=station)
        if favorite.exists():
            favorite.delete()
        else:
            Favorite.objects.create(user=request.user, station=station)
    else:
        favorites = set(request.session.get("favorites", []))
        if station_id in favorites:
            favorites.remove(station_id)
        else:
            favorites.add(station_id)
        request.session["favorites"] = list(favorites)
        request.session.modified = True
    return redirect(f"{request.META.get('HTTP_REFERER', '/')}")


def refresh_stations(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("home")

    stats = refresh_station_db(max_records=None)
    messages.success(
        request,
        (
            "Stations refreshed. "
            f"Created: {stats['created']}, Updated: {stats['updated']}, Deleted: {stats['deleted']}."
        ),
    )
    return redirect("home")


def current_track(request: HttpRequest, station_id: str) -> JsonResponse:
    station = get_object_or_404(Station, station_uuid=station_id)
    title, icy_bitrate = fetch_icy_info(station.stream_url)
    if title:
        record_current_track(station, title)
    return JsonResponse({"track": title, "bitrate": icy_bitrate})


def download_favorites_m3u(request: HttpRequest) -> HttpResponse:
    """Download favorites as an M3U playlist file."""
    if request.user.is_authenticated:
        fav_qs = Favorite.objects.filter(user=request.user).select_related("station")
        stations = [fav.station for fav in fav_qs]
    else:
        fav_ids = set(request.session.get("favorites", []))
        stations = list(Station.objects.filter(station_uuid__in=fav_ids))

    lines = ["#EXTM3U"]
    for station in stations:
        lines.append(f"#EXTINF:-1,{station.name}")
        lines.append(station.stream_url)

    content = "\n".join(lines) + "\n"
    response = HttpResponse(content, content_type="audio/x-mpegurl")
    response["Content-Disposition"] = 'attachment; filename="favorites.m3u"'
    return response
