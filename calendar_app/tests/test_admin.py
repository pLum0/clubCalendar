from datetime import date, time, datetime, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from recurrence import Recurrence, Rule
import recurrence as rec_module
from calendar_app.models import Tag, CalendarUser, Event, RSVP, OccurrenceDetails
from calendar_app.admin import EventAdmin, OccurrenceDetailsAdmin
from calendar_app.admin_site import custom_admin_site


class EventAdminActionsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team', color='#000000')

    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        self.event_admin = EventAdmin(Event, custom_admin_site)
        self.factory = RequestFactory()

    def test_cancel_events(self):
        event1 = Event.objects.create(
            title='Event1', date='2025-06-15', start_time=time(10, 0),
        )
        event2 = Event.objects.create(
            title='Event2', date='2025-06-16', start_time=time(10, 0),
        )
        request = self.factory.get('/')
        request.user = self.admin_user

        queryset = Event.objects.filter(id__in=[event1.id, event2.id])
        with patch.object(self.event_admin, 'message_user'):
            self.event_admin.cancel_events(request, queryset)

        event1.refresh_from_db()
        event2.refresh_from_db()
        self.assertTrue(event1.cancelled)
        self.assertTrue(event2.cancelled)

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_cancel_events_notifies_non_recurring(self, mock_notify):
        event = Event.objects.create(
            title='Event', date='2025-06-15', start_time=time(10, 0),
        )
        request = self.factory.get('/')
        request.user = self.admin_user

        with patch.object(self.event_admin, 'message_user'):
            self.event_admin.cancel_events(request, Event.objects.filter(id=event.id))

        mock_notify.assert_called_once_with(event, date(2025, 6, 15), 'cancelled')

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_cancel_events_skips_recurring(self, mock_notify):
        r = Recurrence()
        r.rrules.append(Rule(rec_module.WEEKLY))
        event = Event.objects.create(
            title='Recurring', date='2025-06-15', start_time=time(10, 0),
            recurrence=r,
        )
        request = self.factory.get('/')
        request.user = self.admin_user

        with patch.object(self.event_admin, 'message_user'):
            self.event_admin.cancel_events(request, Event.objects.filter(id=event.id))

        mock_notify.assert_not_called()

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_cancel_events_skips_already_cancelled(self, mock_notify):
        event = Event.objects.create(
            title='Event', date='2025-06-15', start_time=time(10, 0),
            cancelled=True,
        )
        request = self.factory.get('/')
        request.user = self.admin_user

        with patch.object(self.event_admin, 'message_user'):
            self.event_admin.cancel_events(request, Event.objects.filter(id=event.id))

        mock_notify.assert_not_called()

    def test_uncancel_events(self):
        event = Event.objects.create(
            title='Event', date='2025-06-15', start_time=time(10, 0),
            cancelled=True, cancel_reason='Rain',
        )
        request = self.factory.get('/')
        request.user = self.admin_user

        with patch.object(self.event_admin, 'message_user'):
            self.event_admin.uncancel_events(request, Event.objects.filter(id=event.id))

        event.refresh_from_db()
        self.assertFalse(event.cancelled)
        self.assertEqual(event.cancel_reason, '')

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_uncancel_events_notifies(self, mock_notify):
        event = Event.objects.create(
            title='Event', date='2025-06-15', start_time=time(10, 0),
            cancelled=True,
        )
        request = self.factory.get('/')
        request.user = self.admin_user

        with patch.object(self.event_admin, 'message_user'):
            self.event_admin.uncancel_events(request, Event.objects.filter(id=event.id))

        mock_notify.assert_called_once_with(event, date(2025, 6, 15), 'uncancelled')

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_uncancel_events_skips_non_cancelled(self, mock_notify):
        event = Event.objects.create(
            title='Event', date='2025-06-15', start_time=time(10, 0),
        )
        request = self.factory.get('/')
        request.user = self.admin_user

        with patch.object(self.event_admin, 'message_user'):
            self.event_admin.uncancel_events(request, Event.objects.filter(id=event.id))

        mock_notify.assert_not_called()


class EventAdminSaveModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team', color='#000000')

    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        self.event_admin = EventAdmin(Event, custom_admin_site)
        self.factory = RequestFactory()

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_save_new_event_no_notification(self, mock_notify):
        event = Event(
            title='New Event', date='2025-06-15', start_time=time(10, 0),
        )
        request = self.factory.get('/')
        request.user = self.admin_user
        form = MagicMock()

        self.event_admin.save_model(request, event, form, change=False)
        mock_notify.assert_not_called()

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_save_cancel_non_recurring(self, mock_notify):
        event = Event.objects.create(
            title='Event', date='2025-06-15', start_time=time(10, 0),
        )
        event.cancelled = True

        request = self.factory.get('/')
        request.user = self.admin_user
        form = MagicMock()

        self.event_admin.save_model(request, event, form, change=True)
        mock_notify.assert_called_once_with(event, event.date, 'cancelled', '')

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_save_cancel_recurring_no_notification(self, mock_notify):
        r = Recurrence()
        r.rrules.append(Rule(rec_module.WEEKLY))
        event = Event.objects.create(
            title='Recurring', date='2025-06-15', start_time=time(10, 0),
            recurrence=r,
        )
        event.cancelled = True

        request = self.factory.get('/')
        request.user = self.admin_user
        form = MagicMock()

        self.event_admin.save_model(request, event, form, change=True)
        mock_notify.assert_not_called()


class OccurrenceDetailsAdminSaveTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        self.occ_admin = OccurrenceDetailsAdmin(OccurrenceDetails, custom_admin_site)
        self.factory = RequestFactory()
        r = Recurrence()
        r.rrules.append(Rule(rec_module.WEEKLY))
        self.event = Event.objects.create(
            title='Recurring', date='2025-06-01', start_time=time(10, 0),
            recurrence=r,
        )

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_cancel_occurrence(self, mock_notify):
        details = OccurrenceDetails(
            event=self.event, occurrence_date=date(2025, 6, 8),
            cancelled=True, reason='Holiday',
        )
        request = self.factory.get('/')
        request.user = self.admin_user
        form = MagicMock()

        self.occ_admin.save_model(request, details, form, change=False)
        mock_notify.assert_called_once_with(
            self.event, date(2025, 6, 8), 'cancelled', 'Holiday'
        )

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_uncancel_occurrence(self, mock_notify):
        details = OccurrenceDetails.objects.create(
            event=self.event, occurrence_date=date(2025, 6, 8),
            cancelled=True,
        )
        details.cancelled = False

        request = self.factory.get('/')
        request.user = self.admin_user
        form = MagicMock()

        self.occ_admin.save_model(request, details, form, change=True)
        mock_notify.assert_called_once_with(
            self.event, date(2025, 6, 8), 'uncancelled'
        )

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_reason_change_sends_notice(self, mock_notify):
        details = OccurrenceDetails.objects.create(
            event=self.event, occurrence_date=date(2025, 6, 8),
            reason='Old reason',
        )
        details.reason = 'New reason'

        request = self.factory.get('/')
        request.user = self.admin_user
        form = MagicMock()

        self.occ_admin.save_model(request, details, form, change=True)
        mock_notify.assert_called_once_with(
            self.event, date(2025, 6, 8), 'notice', 'New reason'
        )

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_time_change_sends_notification(self, mock_notify):
        details = OccurrenceDetails.objects.create(
            event=self.event, occurrence_date=date(2025, 6, 8),
        )
        details.override_start_time = time(14, 0)

        request = self.factory.get('/')
        request.user = self.admin_user
        form = MagicMock()

        self.occ_admin.save_model(request, details, form, change=True)
        mock_notify.assert_called_once()

    @patch('calendar_app.admin.notify_rsvps_event_change')
    def test_no_change_no_notification(self, mock_notify):
        details = OccurrenceDetails.objects.create(
            event=self.event, occurrence_date=date(2025, 6, 8),
            reason='Same reason',
        )
        details.reason = 'Same reason'

        request = self.factory.get('/')
        request.user = self.admin_user
        form = MagicMock()

        self.occ_admin.save_model(request, details, form, change=True)
        mock_notify.assert_not_called()
