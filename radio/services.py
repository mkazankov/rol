from __future__ import annotations

import re
import time
from typing import Any

import requests
from django.db import transaction

from .models import Station, StationTrack, Track

# Prefer all.api (DNS round-robin); fall back to regional mirrors if one host fails.
RADIO_BROWSER_SEARCH_URLS: tuple[str, ...] = (
    "https://all.api.radio-browser.info/json/stations/search",
    "https://de1.api.radio-browser.info/json/stations/search",
    "https://fi1.api.radio-browser.info/json/stations/search",
    "https://nl1.api.radio-browser.info/json/stations/search",
    "https://at1.api.radio-browser.info/json/stations/search",
)
_preferred_radio_browser_search_url: str | None = None
LAST_FETCH_STATIONS_ERROR: str | None = None

DEFAULT_LIST_LIMIT = 40
REFRESH_BATCH_SIZE = 500
MAX_REFRESH_RECORDS = 5000


KNOWN_GENRES = (
    "rock",
    "pop",
    "jazz",
    "blues",
    "classical",
    "country",
    "dance",
    "electronic",
    "house",
    "techno",
    "trance",
    "hip-hop",
    "rap",
    "reggae",
    "metal",
    "ambient",
    "chillout",
    "folk",
    "news",
    "talk",
    "sports",
)

# Whole-tag (lowercase, stripped) -> slug from KNOWN_GENRES
TAG_ALIAS_TO_SLUG: dict[str, str] = {
    "edm": "electronic",
    "electronica": "electronic",
    "dubstep": "electronic",
    "dnb": "electronic",
    "drum and bass": "electronic",
    "drum'n'bass": "electronic",
    "rnb": "pop",
    "r&b": "pop",
    "rhythm and blues": "pop",
    "hip hop": "hip-hop",
    "hiphop": "hip-hop",
}


def _canonical_genre_label(slug: str) -> str:
    return slug.title()


def _slugify_segment(segment: str) -> str:
    s = segment.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def _genre_needle_tokens(slug: str) -> list[str]:
    return [t for t in slug.split("-") if t]


def _tokenize_part(part: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", part.lower())


def _has_token_subsequence(tokens: list[str], needle: list[str]) -> bool:
    if not needle:
        return False
    nlen = len(needle)
    for i in range(len(tokens) - nlen + 1):
        if tokens[i : i + nlen] == needle:
            return True
    return False


def classify_genre_from_tags(tags: str) -> str:
    """
    Map comma-separated station tags to a single label from KNOWN_GENRES, or "".
    """
    if not tags or not tags.strip():
        return ""

    parts = [p.strip().lower() for p in tags.split(",") if p.strip()]

    for part in parts:
        slug = TAG_ALIAS_TO_SLUG.get(part)
        if slug:
            return _canonical_genre_label(slug)

    genre_by_length = sorted(
        range(len(KNOWN_GENRES)),
        key=lambda i: (-len(KNOWN_GENRES[i]), i),
    )
    for idx in genre_by_length:
        genre = KNOWN_GENRES[idx]
        for part in parts:
            if _slugify_segment(part) == genre:
                return _canonical_genre_label(genre)

    for idx in genre_by_length:
        genre = KNOWN_GENRES[idx]
        needle = _genre_needle_tokens(genre)
        if not needle:
            continue
        for part in parts:
            tokens = _tokenize_part(part)
            if _has_token_subsequence(tokens, needle):
                return _canonical_genre_label(genre)

    return ""


def _station_uuid_from_item(item: dict[str, Any]) -> str:
    u = item.get("stationuuid") or item.get("stationUuid") or item.get("station_uuid")
    return str(u).strip() if u else ""


def _normalize_station(item: dict[str, Any]) -> dict[str, Any]:
    tags = item.get("tags", "")
    return {
        "station_uuid": _station_uuid_from_item(item),
        "name": item.get("name", "Unknown station")[:255],
        "stream_url": (item.get("url_resolved") or item.get("urlResolved") or item.get("url") or "")[:1000],
        "homepage": (item.get("homepage") or "")[:1000],
        "country": (item.get("country") or "")[:128],
        "language": (item.get("language") or "")[:128],
        "tags": tags,
        "genre": classify_genre_from_tags(tags)[:64],
        "favicon": (item.get("favicon") or "")[:1000],
        "bitrate": int(item.get("bitrate") or 0),
        "clickcount": int(item.get("clickcount") or 0),
        "is_active": True,
    }


def fetch_stations(
    name: str = "",
    country: str = "",
    limit: int = DEFAULT_LIST_LIMIT,
    offset: int = 0,
) -> list[dict[str, Any]]:
    global _preferred_radio_browser_search_url, LAST_FETCH_STATIONS_ERROR

    params = {
        "hidebroken": "true",
        "limit": limit,
        "order": "clickcount",
        "reverse": "true",
        "offset": offset,
    }
    if name:
        params["name"] = name
    if country:
        params["country"] = country

    urls: list[str] = []
    if _preferred_radio_browser_search_url:
        urls.append(_preferred_radio_browser_search_url)
    urls.extend(u for u in RADIO_BROWSER_SEARCH_URLS if u not in urls)

    last_exc: Exception | None = None
    for url in urls:
        for attempt in range(2):
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                time.sleep(0.35 * (attempt + 1))
                continue

            if not isinstance(payload, list):
                last_exc = ValueError(
                    f"Expected a JSON list from {url}, got {type(payload).__name__}"
                )
                time.sleep(0.35 * (attempt + 1))
                continue

            if len(payload) == 0:
                _preferred_radio_browser_search_url = url
                LAST_FETCH_STATIONS_ERROR = None
                return []

            filtered = [item for item in payload if _station_uuid_from_item(item)]
            if not filtered:
                last_exc = ValueError(
                    f"{url} returned {len(payload)} objects but none had a usable station UUID"
                )
                time.sleep(0.35 * (attempt + 1))
                continue

            _preferred_radio_browser_search_url = url
            LAST_FETCH_STATIONS_ERROR = None

            return filtered

    if last_exc is not None:
        LAST_FETCH_STATIONS_ERROR = (
            f"All radio-browser mirrors failed ({len(urls)} hosts). Last error: "
            f"{type(last_exc).__name__}: {last_exc!s}"
        )
    else:
        LAST_FETCH_STATIONS_ERROR = (
            f"All radio-browser mirrors failed ({len(urls)} hosts) with no specific error recorded."
        )
    return []


def refresh_station_db(max_records: int | None = None) -> dict[str, int]:
    offset = 0
    seen_station_ids: set[str] = set()
    created_count = 0
    updated_count = 0

    record_limit = max_records if max_records and max_records > 0 else None
    primed_inactive = False

    while True:
        chunk = fetch_stations(limit=REFRESH_BATCH_SIZE, offset=offset)
        if not chunk:
            break
        if record_limit is not None:
            remaining = record_limit - offset
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                chunk = chunk[:remaining]

        incoming: dict[str, dict[str, Any]] = {}
        for raw in chunk:
            normalized = _normalize_station(raw)
            if normalized["station_uuid"] and normalized["stream_url"]:
                incoming[normalized["station_uuid"]] = normalized

        if incoming:
            if not primed_inactive:
                Station.objects.all().update(is_active=False)
                primed_inactive = True
            incoming_ids = set(incoming.keys())
            seen_station_ids.update(incoming_ids)
            existing = Station.objects.in_bulk(incoming_ids, field_name="station_uuid")

            to_create: list[Station] = []
            to_update: list[Station] = []
            for station_uuid, payload in incoming.items():
                instance = existing.get(station_uuid)
                if instance is None:
                    to_create.append(Station(**payload))
                    continue

                for field, value in payload.items():
                    setattr(instance, field, value)
                to_update.append(instance)

            with transaction.atomic():
                if to_create:
                    Station.objects.bulk_create(to_create, batch_size=200)
                if to_update:
                    Station.objects.bulk_update(
                        to_update,
                        fields=[
                            "name",
                            "stream_url",
                            "homepage",
                            "country",
                            "language",
                            "tags",
                            "genre",
                            "favicon",
                            "bitrate",
                            "clickcount",
                            "is_active",
                            "updated_at",
                        ],
                        batch_size=200,
                    )

            created_count += len(to_create)
            updated_count += len(to_update)

        offset += len(chunk)
        if len(chunk) < REFRESH_BATCH_SIZE:
            break
        if record_limit is not None and offset >= record_limit:
            break

    if primed_inactive:
        deleted_count, _ = Station.objects.filter(is_active=False).delete()
    else:
        deleted_count = 0

    return {
        "created": created_count,
        "updated": updated_count,
        "deleted": deleted_count,
        "total": len(seen_station_ids),
    }


def is_station_stream_available(stream_url: str, timeout: int = 15) -> bool:
    """
    Return True when the station's audio stream responds with media data.

    The check performs a streaming GET and reads a small chunk from the
    body, so an unresponsive server, a broken URL, or an empty payload is
    treated as "not available".
    """
    if not stream_url:
        return False

    headers = {"User-Agent": "RadioLive/1.0"}
    try:
        with requests.get(
            stream_url, headers=headers, stream=True, timeout=timeout
        ) as response:
            if response.status_code != 200:
                return False
            chunk = response.raw.read(1024)
            if not chunk:
                return False
            content_type = response.headers.get("content-type", "").lower()
            if content_type and "audio" in content_type:
                return True
            # Some servers omit a useful content-type but still stream audio.
            return True
    except (requests.RequestException, ValueError, OSError):
        return False


def fetch_current_track(stream_url: str) -> str | None:
    """
    Read ICY metadata from stream and return StreamTitle if present.
    """
    headers = {
        "Icy-MetaData": "1",
        "User-Agent": "RadioLive/1.0",
    }
    try:
        with requests.get(stream_url, headers=headers, stream=True, timeout=10) as response:
            response.raise_for_status()
            metaint_raw = response.headers.get("icy-metaint")
            if not metaint_raw:
                return None

            metaint = int(metaint_raw)
            if metaint <= 0:
                return None

            stream = response.raw
            stream.read(metaint)
            metadata_length_byte = stream.read(1)
            if not metadata_length_byte:
                return None

            metadata_length = metadata_length_byte[0] * 16
            if metadata_length <= 0:
                return None

            metadata_bytes = stream.read(metadata_length)
            metadata_text = metadata_bytes.decode("utf-8", errors="ignore").strip("\x00")
            for part in metadata_text.split(";"):
                if part.lower().startswith("streamtitle="):
                    value = part.split("=", 1)[1].strip().strip("'")
                    return value or None
    except (requests.RequestException, ValueError):
        return None

    return None


def fetch_icy_info(stream_url: str) -> tuple[str | None, str | None]:
    """
    Read ICY metadata from stream.

    Returns (stream_title, icy_bitrate) where icy_bitrate is the
    actual stream bitrate reported by the server (e.g. "128", "320").
    """
    headers = {
        "Icy-MetaData": "1",
        "User-Agent": "RadioLive/1.0",
    }
    title: str | None = None
    bitrate: str | None = None

    try:
        with requests.get(stream_url, headers=headers, stream=True, timeout=10) as response:
            response.raise_for_status()
            bitrate = response.headers.get("icy-br")

            metaint_raw = response.headers.get("icy-metaint")
            if not metaint_raw:
                return title, bitrate

            metaint = int(metaint_raw)
            if metaint <= 0:
                return title, bitrate

            stream = response.raw
            stream.read(metaint)
            metadata_length_byte = stream.read(1)
            if not metadata_length_byte:
                return title, bitrate

            metadata_length = metadata_length_byte[0] * 16
            if metadata_length <= 0:
                return title, bitrate

            metadata_bytes = stream.read(metadata_length)
            metadata_text = metadata_bytes.decode("utf-8", errors="ignore").strip("\x00")
            for part in metadata_text.split(";"):
                if part.lower().startswith("streamtitle="):
                    value = part.split("=", 1)[1].strip().strip("'")
                    title = value or None
    except (requests.RequestException, ValueError):
        return title, bitrate

    return title, bitrate


def parse_track_parts(raw: str | None) -> tuple[str, str]:
    """
    Split a raw StreamTitle into (artist, title).

    The artist is the part before the first separator (" - ", " -",
    "- ", or en-dash "–"); anything without a separator is treated as
    the title only.
    """
    if not raw:
        return "", ""

    value = raw.strip()
    if not value:
        return "", ""

    for sep in (" - ", " – ", " -", "- ", "–", "-"):
        if sep in value:
            artist, title = value.split(sep, 1)
            return artist.strip(), title.strip()

    return "", value


def _compose_full_name(artist: str, title: str) -> str:
    """Build the composite full name used for global uniqueness."""
    if artist:
        return f"{artist} - {title}"
    return title


def record_current_track(station: Station, raw: str | None) -> Track | None:
    """
    Persist the currently playing track for a station.

    The Track is created globally (get_or_create by full_name), so the
    same song played on different stations resolves to one catalog row.
    A StationTrack playlist row is inserted only when the track differs
    from the station's most recently recorded track (consecutive repeats
    are skipped).

    Returns the Track, or None when there is nothing to record.
    """
    if not raw or not raw.strip():
        return None

    artist, title = parse_track_parts(raw)
    full_name = _compose_full_name(artist, title)

    track, _ = Track.objects.get_or_create(full_name=full_name, defaults={"artist": artist, "title": title})

    latest = (
        station.playlist.select_related("track")
        .order_by("-played_at")
        .values_list("track__full_name", flat=True)
        .first()
    )
    if latest == track.full_name:
        return track

    StationTrack.objects.create(station=station, track=track)
    return track
