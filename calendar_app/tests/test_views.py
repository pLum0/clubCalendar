from datetime import date, time, datetime, timedelta
from unittest.mock import patch
from django.test import TestCase, Client
from django.conf import settings
from django.contrib.auth.models import User
from recurrence import Recurrence, Rule
import recurrence as rec_module
from calendar_app.models import Tag, CalendarUser, Event, RSVP, OccurrenceDetails


def _url(path):
    if settings.SECRET_PATH:
        return f'/{settings.SECRET_PATH}{path}'
    return path


class CalendarViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team1', color='#ff0000')
        cls.user = CalendarUser.objects.create(name='Alice', team=cls.team)

    def setUp(self):
        self.client = Client()
        self.url = _url('/')

    def test_calendar_view_ok(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_calendar_view_with_month_params(self):
        resp = self.client.get(self.url, {'year': '2025', 'month': '6'})
        self.assertEqual(resp.status_code, 200)

    def test_calendar_view_invalid_year(self):
        resp = self.client.get(self.url, {'year': 'abc', 'month': '6'})
        self.assertEqual(resp.status_code, 400)

    def test_calendar_view_invalid_month(self):
        resp = self.client.get(self.url, {'year': '2025', 'month': 'abc'})
        self.assertEqual(resp.status_code, 400)

    def test_calendar_view_month_overflow(self):
        resp = self.client.get(self.url, {'year': '2025', 'month': '13'})
        self.assertEqual(resp.status_code, 200)

    def test_calendar_view_month_underflow(self):
        resp = self.client.get(self.url, {'year': '2025', 'month': '0'})
        self.assertEqual(resp.status_code, 200)

    def test_calendar_view_shows_events(self):
        Event.objects.create(
            title='June Event',
            date=date(2025, 6, 15),
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        resp = self.client.get(self.url, {'year': '2025', 'month': '6'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'June Event')

    def test_calendar_view_tag_filter(self):
        Event.objects.create(
            title='Tagged Event',
            date=date(2025, 6, 15),
            start_time=time(10, 0),
        )
        resp = self.client.get(self.url, {'year': '2025', 'month': '6', 'tags': 'Team1'})
        self.assertEqual(resp.status_code, 200)

    def test_calendar_view_logged_in_no_all_users(self):
        self.client.cookies['calendar_user_id'] = str(self.user.id)
        resp = self.client.get(self.url, {'year': '2025', 'month': '6'})
        self.assertEqual(resp.status_code, 200)


class EventDetailViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team1', color='#ff0000')
        cls.user = CalendarUser.objects.create(name='Alice', team=cls.team)

    def setUp(self):
        self.client = Client()
        self.event = Event.objects.create(
            title='Test Event',
            date=date(2025, 6, 15),
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        self.url = _url(f'/event/{self.event.id}/')

    def test_event_detail_ok(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_event_detail_with_date_param(self):
        resp = self.client.get(self.url, {'date': '2025-06-15'})
        self.assertEqual(resp.status_code, 200)

    def test_event_detail_invalid_date_uses_event_date(self):
        resp = self.client.get(self.url, {'date': 'invalid'})
        self.assertEqual(resp.status_code, 200)

    def test_event_detail_nonexistent_event(self):
        resp = self.client.get(_url('/event/99999/'))
        self.assertEqual(resp.status_code, 404)

    def test_event_detail_with_user_rsvp(self):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user, status='coming'
        )
        self.client.cookies['calendar_user_id'] = str(self.user.id)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_event_detail_cancelled(self):
        self.event.cancelled = True
        self.event.cancel_reason = 'Rain'
        self.event.save()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)


class UpcomingEventsViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team1', color='#ff0000')

    def setUp(self):
        self.client = Client()
        self.url = _url('/upcoming/')

    def test_upcoming_events_ok(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_upcoming_shows_future_events(self):
        today = date.today()
        Event.objects.create(
            title='Future Event',
            date=today + timedelta(days=5),
            start_time=time(10, 0),
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Future Event')

    def test_upcoming_hides_past_events(self):
        Event.objects.create(
            title='Past Event',
            date=date(2020, 1, 1),
            start_time=time(10, 0),
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Past Event')

    def test_upcoming_tag_filter(self):
        Event.objects.create(
            title='Upcoming Event',
            date=date.today() + timedelta(days=5),
            start_time=time(10, 0),
        )
        resp = self.client.get(self.url, {'tags': 'Team1'})
        self.assertEqual(resp.status_code, 200)

    def test_upcoming_recurring_event(self):
        r = Recurrence()
        r.rrules.append(Rule(rec_module.WEEKLY, dtstart=datetime.combine(date.today(), time.min)))
        Event.objects.create(
            title='Recurring',
            date=date.today() - timedelta(days=30),
            start_time=time(10, 0),
            recurrence=r,
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Recurring')


class UpdateOccurrenceViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team', color='#000000')

    def setUp(self):
        self.client = Client()
        r = Recurrence()
        r.rrules.append(Rule(rec_module.WEEKLY, dtstart=datetime.combine(date(2025, 6, 1), time.min)))
        self.event = Event.objects.create(
            title='Recurring Event',
            date=date(2025, 6, 1),
            start_time=time(10, 0),
            recurrence=r,
        )
        self.url = _url(f'/event/{self.event.id}/update-occurrence/')

    def test_unauthenticated_rejected(self):
        resp = self.client.post(self.url, {
            'occurrence_date': '2025-06-08',
            'cancelled': 'true',
        })
        self.assertEqual(resp.status_code, 403)

    def test_invalid_date(self):
        admin = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        self.client.login(username='admin', password='pass')
        resp = self.client.post(self.url, {'occurrence_date': 'invalid'})
        self.assertEqual(resp.status_code, 400)

    @patch('calendar_app.views.notify_rsvps_event_change')
    def test_cancel_occurrence(self, mock_notify):
        admin = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        self.client.login(username='admin', password='pass')
        resp = self.client.post(self.url, {
            'occurrence_date': '2025-06-08',
            'cancelled': 'true',
            'reason': 'Holiday',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['cancelled'])
        details = OccurrenceDetails.objects.get(event=self.event, occurrence_date=date(2025, 6, 8))
        self.assertTrue(details.cancelled)
        self.assertEqual(details.reason, 'Holiday')
        mock_notify.assert_called_once()

    @patch('calendar_app.views.notify_rsvps_event_change')
    def test_uncancel_occurrence(self, mock_notify):
        admin = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        self.client.login(username='admin', password='pass')

        OccurrenceDetails.objects.create(
            event=self.event, occurrence_date=date(2025, 6, 8),
            cancelled=True, reason='Holiday',
        )
        resp = self.client.post(self.url, {
            'occurrence_date': '2025-06-08',
            'cancelled': 'false',
        })
        self.assertEqual(resp.status_code, 200)
        details = OccurrenceDetails.objects.get(event=self.event, occurrence_date=date(2025, 6, 8))
        self.assertFalse(details.cancelled)

    def test_time_override(self):
        admin = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        self.client.login(username='admin', password='pass')
        resp = self.client.post(self.url, {
            'occurrence_date': '2025-06-08',
            'cancelled': 'false',
            'start_time': '14:00',
            'end_time': '16:00',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['start_time'], '14:00:00')
        self.assertEqual(data['end_time'], '16:00:00')

    def test_invalid_start_time(self):
        admin = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        self.client.login(username='admin', password='pass')
        resp = self.client.post(self.url, {
            'occurrence_date': '2025-06-08',
            'cancelled': 'false',
            'start_time': 'not-a-time',
        })
        self.assertEqual(resp.status_code, 400)

    def test_get_rejected(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)
