# RadioLive (Django)

A simple Django website to listen to online radio stations.

## Features

- Search stations by name
- Filter by country
- Filter by genre (derived from station tags)
- Filter by sound quality (derived from station bitrate)
- Play streams directly in browser
- Mark stations as favorites (saved in session)
- User accounts with persistent favorites
- Refresh local station database from radio-browser.info

## Stack

- Python 3.14
- Django 6
- Requests
- Radio Browser public API

## Run locally

1. Create and activate virtual environment:
   - Windows PowerShell:
     - `python -m venv .venv`
     - `.venv\Scripts\Activate.ps1`
2. Install dependencies:
   - `python -m pip install -U pip`
   - `python -m pip install django requests`
3. Apply migrations:
   - `python manage.py migrate`
4. Start server:
   - `python manage.py runserver`
5. Open:
   - `http://127.0.0.1:8000/`

## Refresh stations DB

- From command line:
  - `python manage.py refresh_stations` (no limit)
  - `python manage.py refresh_stations --max-records 5000` (optional cap)
- From UI:
  - Use `Refresh stations DB` button on the home page (no limit)

## Capture station playlists

For every active station, reads the ICY metadata from the live stream to find
the currently playing track and appends it to that station's playlist.
Consecutive repeats of the same track are skipped automatically.

- `python manage.py capture_playlist` (all active stations)
- `python manage.py capture_playlist --limit 50` (cap the number of stations)
- `python manage.py capture_playlist --station <station-uuid>` (single station)

Tip: schedule this command on a timer (e.g. every minute via cron / Task
Scheduler) to keep a continuous history of played tracks.

## Notes

- Station data comes from [Radio Browser](https://www.radio-browser.info/).
- Some streams can be unavailable or blocked by source servers.
