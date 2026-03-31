from datetime import date, time, datetime, timedelta
from django.test import TestCase
from recurrence import Recurrence, Rule
import recurrence as rec_module
from calendar_app.models import Tag, CalendarUser, Event, RSVP, OccurrenceDetails
from calendar_app.views import get_event_occurrences, _prefetch_rsvps


class OccurrenceTestMixin:
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team', color='#000000')

    def _create_event(self, date_val=None, recurrence=None, **kwargs):
        d = date_val or date(2025, 6, 15)
        defaults = {
            'title': 'Test Event',
            'description': '',
            'date': d,
            'start_time': time(10, 0),
            'end_time': time(12, 0),
        }
        defaults.update(kwargs)
        event = Event.objects.create(**defaults)
        if recurrence is not None:
            event.recurrence = recurrence
            event.save()
        return event

    def _create_user(self, name='User'):
        return CalendarUser.objects.create(name=name, team=self.team)

    def _weekly_recurrence(self, start_date=None):
        start = start_date or date(2025, 6, 15)
        r = Recurrence()
        r.rrules.append(Rule(rec_module.WEEKLY, dtstart=datetime.combine(start, time.min)))
        return r


class NonRecurringOccurrenceTest(OccurrenceTestMixin, TestCase):
    def test_single_event_in_range(self):
        event = self._create_event(date_val=date(2025, 6, 15))
        start = date(2025, 6, 1)
        end = date(2025, 6, 30)
        occs = get_event_occurrences(event, start, end)
        self.assertEqual(len(occs), 1)
        self.assertEqual(occs[0]['date'], date(2025, 6, 15))
        self.assertFalse(occs[0]['is_recurring'])

    def test_single_event_out_of_range(self):
        event = self._create_event(date_val=date(2025, 5, 15))
        start = date(2025, 6, 1)
        end = date(2025, 6, 30)
        occs = get_event_occurrences(event, start, end)
        self.assertEqual(len(occs), 0)

    def test_event_at_range_start(self):
        event = self._create_event(date_val=date(2025, 6, 1))
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30))
        self.assertEqual(len(occs), 1)

    def test_event_at_range_end(self):
        event = self._create_event(date_val=date(2025, 6, 30))
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30))
        self.assertEqual(len(occs), 1)

    def test_cancelled_event(self):
        event = self._create_event(date_val=date(2025, 6, 15), cancelled=True, cancel_reason='Rain')
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30))
        self.assertEqual(len(occs), 1)
        self.assertTrue(occs[0]['cancelled'])
        self.assertEqual(occs[0]['cancel_reason'], 'Rain')

    def test_rsvp_count_without_prefetch(self):
        event = self._create_event(date_val=date(2025, 6, 15))
        user1 = self._create_user('U1')
        user2 = self._create_user('U2')
        RSVP.objects.create(event=event, occurrence_date=event.date, user=user1, status='coming')
        RSVP.objects.create(event=event, occurrence_date=event.date, user=user2, status='maybe')
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30))
        self.assertEqual(occs[0]['rsvp_count'], 1)

    def test_user_rsvp_status_without_prefetch(self):
        event = self._create_event(date_val=date(2025, 6, 15))
        user = self._create_user()
        RSVP.objects.create(event=event, occurrence_date=event.date, user=user, status='maybe')
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30), calendar_user=user)
        self.assertEqual(occs[0]['user_rsvp_status'], 'maybe')

    def test_user_no_rsvp_without_prefetch(self):
        event = self._create_event(date_val=date(2025, 6, 15))
        user = self._create_user()
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30), calendar_user=user)
        self.assertIsNone(occs[0]['user_rsvp_status'])

    def test_guest_count_included(self):
        event = self._create_event(date_val=date(2025, 6, 15))
        event.guests = [{'name': 'Guest', 'status': 'coming'}]
        event.save()
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30))
        self.assertEqual(occs[0]['rsvp_count'], 1)


class RecurringOccurrenceTest(OccurrenceTestMixin, TestCase):
    def test_weekly_recurrence_generates_occurrences(self):
        event = self._create_event(
            date_val=date(2025, 6, 1),
            recurrence=self._weekly_recurrence(date(2025, 6, 1)),
        )
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30))
        self.assertGreaterEqual(len(occs), 4)
        for occ in occs:
            self.assertTrue(occ['is_recurring'])

    def test_cancelled_occurrence(self):
        event = self._create_event(
            date_val=date(2025, 6, 1),
            recurrence=self._weekly_recurrence(date(2025, 6, 1)),
        )
        OccurrenceDetails.objects.create(
            event=event,
            occurrence_date=date(2025, 6, 8),
            cancelled=True,
            reason='Holiday',
        )
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30))
        cancelled = [o for o in occs if o['date'] == date(2025, 6, 8)]
        self.assertEqual(len(cancelled), 1)
        self.assertTrue(cancelled[0]['cancelled'])
        self.assertEqual(cancelled[0]['cancel_reason'], 'Holiday')

    def test_time_override(self):
        event = self._create_event(
            date_val=date(2025, 6, 1),
            recurrence=self._weekly_recurrence(date(2025, 6, 1)),
        )
        OccurrenceDetails.objects.create(
            event=event,
            occurrence_date=date(2025, 6, 8),
            override_start_time=time(14, 0),
            override_end_time=time(16, 0),
        )
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30))
        overridden = [o for o in occs if o['date'] == date(2025, 6, 8)]
        self.assertEqual(len(overridden), 1)
        self.assertEqual(overridden[0]['start_time'], time(14, 0))
        self.assertEqual(overridden[0]['end_time'], time(16, 0))
        self.assertTrue(overridden[0]['time_changed'])

    def test_no_time_override_uses_event_time(self):
        event = self._create_event(
            date_val=date(2025, 6, 1),
            recurrence=self._weekly_recurrence(date(2025, 6, 1)),
        )
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30))
        self.assertEqual(occs[0]['start_time'], time(10, 0))
        self.assertFalse(occs[0]['time_changed'])

    def test_occurrence_guest_count(self):
        event = self._create_event(
            date_val=date(2025, 6, 1),
            recurrence=self._weekly_recurrence(date(2025, 6, 1)),
        )
        OccurrenceDetails.objects.create(
            event=event,
            occurrence_date=date(2025, 6, 8),
            guests=[{'name': 'G1', 'status': 'coming'}, {'name': 'G2', 'status': 'maybe'}],
        )
        occs = get_event_occurrences(event, date(2025, 6, 1), date(2025, 6, 30))
        june_8 = [o for o in occs if o['date'] == date(2025, 6, 8)]
        self.assertEqual(june_8[0]['rsvp_count'], 1)


class PrefetchRSVPsTest(OccurrenceTestMixin, TestCase):
    def test_prefetch_counts(self):
        event = self._create_event(date_val=date(2025, 6, 15))
        u1 = self._create_user('U1')
        u2 = self._create_user('U2')
        RSVP.objects.create(event=event, occurrence_date=event.date, user=u1, status='coming')
        RSVP.objects.create(event=event, occurrence_date=event.date, user=u2, status='coming')
        u3 = self._create_user('U3')
        RSVP.objects.create(event=event, occurrence_date=event.date, user=u3, status='maybe')

        data = _prefetch_rsvps([event], None)
        self.assertEqual(data[event.id]['count_by_date'][event.date], 2)

    def test_prefetch_user_status(self):
        event = self._create_event(date_val=date(2025, 6, 15))
        user = self._create_user()
        RSVP.objects.create(event=event, occurrence_date=event.date, user=user, status='maybe')

        data = _prefetch_rsvps([event], user)
        self.assertEqual(data[event.id]['user_by_date'][event.date], 'maybe')

    def test_prefetch_empty_events(self):
        data = _prefetch_rsvps([], None)
        self.assertEqual(data, {})

    def test_prefetch_no_user(self):
        event = self._create_event(date_val=date(2025, 6, 15))
        data = _prefetch_rsvps([event], None)
        self.assertEqual(data[event.id]['user_by_date'], {})

    def test_prefetch_used_in_get_event_occurrences(self):
        event = self._create_event(date_val=date(2025, 6, 15))
        u1 = self._create_user('U1')
        u2 = self._create_user('U2')
        RSVP.objects.create(event=event, occurrence_date=event.date, user=u1, status='coming')
        RSVP.objects.create(event=event, occurrence_date=event.date, user=u2, status='coming')

        data = _prefetch_rsvps([event], u1)
        occs = get_event_occurrences(
            event, date(2025, 6, 1), date(2025, 6, 30),
            calendar_user=u1, rsvp_data=data.get(event.id),
        )
        self.assertEqual(occs[0]['rsvp_count'], 2)
        self.assertEqual(occs[0]['user_rsvp_status'], 'coming')
