# clubCalendar

A Django-based calendar application for sports clubs with recurring and non-recurring events, team tagging, and RSVP functionality.

## Features

- **Calendar View**: Monthly calendar showing all events
- **Recurring Events**: Support for weekly recurring events (e.g., regular trainings)
  - Edit individual occurrences: cancel, add notes, or change time for specific dates
- **Non-recurring Events**: One-time events (e.g., sports club summer party)
- **Team Tags**: Tag events with team names for easy filtering
- **RSVP System**: Users can RSVP (coming/not coming/maybe) with optional comments
  - RSVPs are identified by name + team combination to prevent collisions when multiple people share the same name
  - RSVPs are specific to each occurrence of a recurring event
  - Users can RSVP differently for different dates of the same recurring event
- **No Login Required**: User names and preferences saved in cookies
- **Multilingual**: Support for English and German (extensible to other languages)
- **Push Notifications**: Optional notifications via ntfy when events change or users move off waitlist

## Quick Start

### Run with Docker Compose

```bash
docker compose up
```

The application will be available at http://localhost:8000

### Admin Access

Admin credentials are configured via environment variables (see below). Default from `.env_example`:
- Username: `admin`
- Password: `change_me_in_production`

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `False` |
| `SECRET_KEY` | Django secret key | (change in production!) |
| `SITE_NAME` | Name displayed in header and title | `Sports Club Calendar` |
| `SITE_LOGO` | Path to logo image | (empty) |
| `SITE_URL` | Full URL of your site (used for notification links and CSRF) | (empty) |
| `SECRET_PATH` | Optional path prefix for all URLs | (empty) |
| `DJANGO_ADMIN_USERNAME` | Admin username | `admin` |
| `DJANGO_ADMIN_EMAIL` | Admin email | `admin@example.com` |
| `DJANGO_ADMIN_PASSWORD` | Admin password | `change_me_in_production` |
| `POSTGRES_DB` | PostgreSQL database name | `calendar` |
| `POSTGRES_USER` | PostgreSQL user | `calendar` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `change_me_in_production` |
| `POSTGRES_HOST` | PostgreSQL host | `db` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `NTFY_ALLOWED_HOSTS` | Comma-separated list of additional allowed ntfy server hosts (besides ntfy.sh) | (empty) |

### Docker Compose Example

```yaml
environment:
  - DEBUG=False
  - SECRET_KEY=your-secret-key-change-in-production
  - SITE_NAME=My Sports Club Calendar
  - SITE_URL=https://calendar.example.com
  - POSTGRES_PASSWORD=your-secure-password
```

## Usage

### Creating Tags (Teams)

1. Go to Admin > Calendar App > Tags
2. Add tags like "Volleyball Team 1", "Football Team", etc.
3. Assign colors to distinguish teams visually

### Creating Events

1. Go to Admin > Calendar App > Events
2. Create events with:
   - Title and description
   - Date and time
   - Location
   - Team tags
   - Recurrence rules (for weekly trainings)

### Editing Occurrence Details

For recurring events, you can modify individual occurrences without affecting the entire series:

1. Go to Admin > Calendar App > Occurrence Details
2. Select the specific occurrence you want to modify
3. You can:
   - **Cancel** the occurrence (e.g., skip a training on a holiday)
   - **Add a note** (e.g., "Training moved to Hall B")
   - **Change the time** for just that occurrence

### User Features

- Users enter their name and select their team (saved in cookies)
- Users can filter events by team tags
- Users can RSVP to events with their attendance status
- Optional comments can be added to RSVPs
- For recurring events, users can RSVP to each occurrence separately
  - Example: A user can say "Coming" to this Thursday's training, but "Not Coming" to next Thursday's
- Anyone can RSVP on behalf of others by changing the name in settings

### Push Notifications

The application supports push notifications via [ntfy](https://ntfy.sh/) - a free, open-source notification service.

**When notifications are sent:**
- **Waitlist**: When a user moves off the waitlist (for events with max participants)
- **Event changes**: When an event is cancelled, uncancelled, or has a notice added
- **Time changes**: When the time of an occurrence is modified

**Who receives notifications:**
- Only users with status "Coming" or "Maybe" receive event change notifications
- Users with "Not Coming" status do not receive notifications
- Notifications are sent in the user's selected language

**How to set up:**
1. Install the ntfy app:
   - [Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   - [F-Droid](https://f-droid.org/packages/io.heckel.ntfy/)
   - [Apple App Store](https://apps.apple.com/us/app/ntfy/id1625396347)
2. Choose a unique topic name
3. Enter the topic name in the event RSVP form
4. Subscribe to the same topic in the ntfy app

**Configuration:**
- By default, notifications use the public `ntfy.sh` server (just enter a topic name)
- For self-hosted ntfy servers, enter the full URL (e.g., `https://ntfy.example.com/mytopic`)
- Set `SITE_URL` in your environment variables so notification links work correctly
- Notifications are sent asynchronously using background threads, so sending many notifications won't block the application

## Development

### Project Structure

```
.
├── calendar_app/           # Main application
│   ├── models.py          # Event, Tag, RSVP models
│   ├── views.py           # Calendar views
│   ├── notifications.py   # Shared notification functions
│   ├── validators.py      # Input validation (ntfy topic, guest names)
│   ├── admin.py           # Admin configuration
│   ├── tests/             # Test suite (156 tests)
│   ├── templates/         # HTML templates
│   ├── static/            # CSS, JS, images
│   └── templatetags/      # Custom template tags
├── calendar_project/       # Django project settings
├── locale/                 # Translation files
├── docker-compose.yml      # Docker Compose configuration
├── docker-entrypoint.sh   # Docker entrypoint script
├── Dockerfile             # Docker image definition
├── .env_example           # Example environment variables
├── manage.py              # Django management script
├── LICENSE                # MIT License
└── requirements.txt       # Python dependencies
```

## Testing

Run the test suite inside the Docker container:

```bash
docker compose exec web python manage.py test calendar_app.tests --verbosity=2
```

The test suite covers RSVP logic, occurrence handling, authentication, notifications, views, and admin actions.

## Translations

The application supports multiple languages. Currently available:
- English (default)
- German

To add a new language:
1. Add the language code to `LANGUAGES` in `calendar_project/settings.py`
2. Create translation files: `python manage.py makemessages -l <language_code>`
3. Translate the strings in `locale/<language_code>/LC_MESSAGES/django.po`
4. Compile: `python manage.py compilemessages`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
