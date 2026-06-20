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

## Deploy to server

Развертывание на Ubuntu 24.04 + nginx (`r.mkazankov.ru`): [DEPLOY.md](DEPLOY.md)

## Refresh stations DB

- From command line:
  - `python manage.py refresh_stations` (no limit)
  - `python manage.py refresh_stations --max-records 5000` (optional cap)
- From UI:
  - Use `Refresh stations DB` button on the home page (no limit)

## Notes

- Station data comes from [Radio Browser](https://www.radio-browser.info/).
- Some streams can be unavailable or blocked by source servers.
