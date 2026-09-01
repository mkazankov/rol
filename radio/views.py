from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic.edit import FormView

from .models import Favorite, Station
from .services import fetch_current_track, record_current_track, refresh_station_db


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
    track = fetch_current_track(station.stream_url)
    if track:
        # Persist the currently playing track (and its station) to build
        # the station playlist. Consecutive repeats are skipped.
        record_current_track(station, track)
    return JsonResponse({"track": track})
