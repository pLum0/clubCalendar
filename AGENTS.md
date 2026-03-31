# AGENTS.md - AI Agent Guide

## Project Overview

clubCalendar is a Django 4.2 sports club event calendar with RSVP functionality, recurring events, team tagging, and push notifications via ntfy. Users can create events, RSVP, and receive notifications. There is no user registration — authentication is cookie-based via a `CalendarUser` model (name + team).

## Running Commands

**All management commands must be run inside the Docker container**, not on the host. This includes `makemigrations`, `migrate`, and any file operations on migration files — running these on the host will cause permission issues since the Docker container owns the mounted volume files. Use:

```bash
docker compose exec web python manage.py <command>
```

Common commands:

```bash
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py makemessages -l de
docker compose exec web python manage.py compilemessages
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py test calendar_app.tests --verbosity=2
```

To start the stack:

```bash
docker compose up --build
```

The app is served at `http://localhost:8000`. PostgreSQL runs on the `db` service.

## Django Project Structure

- `calendar_project/` — Django project configuration (settings, URLs, WSGI)
  - `settings.py` — Database (PostgreSQL), i18n (en/de), static files via WhiteNoise
  - `urls.py` — Root URL conf, includes `calendar_app.urls` under `SECRET_PATH` if set
  - `context_processors.py` — Exposes `SITE_NAME`, `SITE_LOGO`, `SITE_URL` to templates
- `calendar_app/` — Main application
  - `models.py` — `Tag` (teams), `CalendarUser` (cookie-auth users), `Event`, `RSVP`, `OccurrenceDetails`
  - `views.py` — All views: calendar, event detail, RSVP, login/logout, admin wrapper, upcoming events
  - `notifications.py` — Shared notification functions (ntfy send, waitlist, event change)
  - `validators.py` — Input validation (ntfy topic, guest name sanitization)
  - `urls.py` — App URL patterns
  - `templates/calendar_app/` — All templates (`calendar.html`, `event_detail.html`, `upcoming.html`, `base.html`)
  - `static/calendar_app/css/style.css` — Single stylesheet
  - `templatetags/` — Custom template tags (`recurrence_utils.py`)
  - `tests/` — Test suite (`test_rsvp.py`, `test_occurrences.py`, `test_auth.py`, `test_notifications.py`, `test_views.py`, `test_admin.py`)
  - `middleware.py` — Custom `AdminXFrameOptionsMiddleware`
  - `admin.py` / `admin_site.py` — Django admin configuration
- `locale/` — Translation files
  - `de/LC_MESSAGES/django.po` — German translations

## Key Architecture Details

- **Authentication**: No Django auth. Users enter name + team, a `CalendarUser` is created/fetched, and a cookie (`calendar_user_id`) is set. `unique_together = ['name', 'team']`.
- **Recurring Events**: Uses `django-recurrence` (`RecurrenceField`). Individual occurrences can be cancelled or have time overrides via `OccurrenceDetails`.
- **RSVP**: Per event + occurrence date + user. Supports "coming", "maybe", "not_coming". Optional max participants with waitlist.
- **Notifications**: Optional push via ntfy.sh. Users configure a topic in their settings.
- **i18n**: English (default) and German. Uses Django's `{% trans %}` and `{% blocktrans %}` template tags.

## Internationalization (IMPORTANT)

The app supports English and German. **Any user-facing text change requires a German translation.**

When adding or modifying translatable strings:

1. Use `{% trans "..." %}` or `{% blocktrans %}` in templates, `gettext()` / `gettext_lazy()` in Python
2. Regenerate the message file:
   ```bash
   docker compose exec web python manage.py makemessages -l de
   ```
3. Add/edit the German translation in `locale/de/LC_MESSAGES/django.po`
4. Compile the translations:
   ```bash
   docker compose exec web python manage.py compilemessages
   ```

Never skip step 3 — always provide the German `msgstr` for every new/changed `msgid`.

## Conventions

- Single CSS file: `calendar_app/static/calendar_app/css/style.css`
- Templates extend `base.html` and use Django's i18n tags
- No JavaScript framework — vanilla JS inline in templates
- Environment variables configured via `.env` file (see `.env_example`)
- `SECRET_PATH` env var can prefix all URLs (e.g., `/mysecret/`)
