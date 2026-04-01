from datetime import date, time

from django.conf import settings
from django.test import Client, TestCase

from calendar_app.models import RSVP, CalendarUser, Event, Tag


def _url(path):
    if settings.SECRET_PATH:
        return f'/{settings.SECRET_PATH}{path}'
    return path


class RSVPTestMixin:
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Test Team', color='#ff0000')
        cls.team2 = Tag.objects.create(name='Other Team', color='#00ff00')

    def _create_user(self, name='Alice', team=None):
        team = team or self.team
        return CalendarUser.objects.create(name=name, team=team)

    def _create_event(self, date_val=None, max_participants=None):
        d = date_val or date(2025, 6, 15)
        return Event.objects.create(
            title='Test Event',
            description='A test event',
            date=d,
            start_time=time(10, 0),
            end_time=time(12, 0),
            max_participants=max_participants,
        )

    def _create_rsvp(self, event, user, status='coming', occurrence_date=None):
        return RSVP.objects.create(
            event=event,
            occurrence_date=occurrence_date or event.date,
            user=user,
            status=status,
        )


class RSVPCreateTest(RSVPTestMixin, TestCase):
    def setUp(self):
        self.client = Client()
        self.user = self._create_user()
        self.event = self._create_event()
        self.url = _url(f'/event/{self.event.id}/rsvp/')

    def test_create_rsvp_coming(self):
        resp = self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'coming',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status_code'], 'coming')
        self.assertEqual(RSVP.objects.count(), 1)

    def test_create_rsvp_maybe(self):
        resp = self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'maybe',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(RSVP.objects.first().status, 'maybe')

    def test_create_rsvp_not_coming(self):
        resp = self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'not_coming',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(RSVP.objects.first().status, 'not_coming')

    def test_invalid_status_rejected(self):
        resp = self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'invalid',
        })
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(RSVP.objects.count(), 0)

    def test_missing_user_id(self):
        resp = self.client.post(self.url, {'status': 'coming'})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn('error', data)

    def test_invalid_user_id(self):
        resp = self.client.post(self.url, {
            'user_id': 99999,
            'status': 'coming',
        })
        self.assertEqual(resp.status_code, 400)

    def test_invalid_user_id_non_numeric(self):
        resp = self.client.post(self.url, {
            'user_id': 'abc',
            'status': 'coming',
        })
        self.assertEqual(resp.status_code, 400)

    def test_get_method_rejected(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_occurrence_date_parsing(self):
        resp = self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'coming',
            'occurrence_date': '2025-06-22',
        })
        self.assertEqual(resp.status_code, 200)
        rsvp = RSVP.objects.first()
        self.assertEqual(rsvp.occurrence_date, date(2025, 6, 22))

    def test_invalid_occurrence_date_falls_back(self):
        resp = self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'coming',
            'occurrence_date': 'not-a-date',
        })
        self.assertEqual(resp.status_code, 200)
        rsvp = RSVP.objects.first()
        self.assertEqual(rsvp.occurrence_date, self.event.date)

    def test_empty_occurrence_date_uses_event_date(self):
        self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'coming',
        })
        rsvp = RSVP.objects.first()
        self.assertEqual(rsvp.occurrence_date, self.event.date)

    def test_rsvp_update_changes_status(self):
        self._create_rsvp(self.event, self.user, 'coming')
        resp = self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'not_coming',
        })
        self.assertEqual(resp.status_code, 200)
        rsvp = RSVP.objects.get(event=self.event, user=self.user)
        self.assertEqual(rsvp.status, 'not_coming')
        self.assertEqual(RSVP.objects.count(), 1)

    def test_rsvp_update_sets_status_updated_at_on_change(self):
        rsvp = self._create_rsvp(self.event, self.user, 'coming')
        old_updated_at = rsvp.status_updated_at

        self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'maybe',
        })
        rsvp.refresh_from_db()
        self.assertNotEqual(rsvp.status_updated_at, old_updated_at)

    def test_rsvp_update_does_not_change_status_updated_at_when_same(self):
        rsvp = self._create_rsvp(self.event, self.user, 'coming')
        old_updated_at = rsvp.status_updated_at

        self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'coming',
        })
        rsvp.refresh_from_db()
        self.assertEqual(rsvp.status_updated_at, old_updated_at)

    def test_comment_saved(self):
        self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'coming',
            'comment': 'Looking forward to it',
        })
        rsvp = RSVP.objects.first()
        self.assertEqual(rsvp.comment, 'Looking forward to it')

    def test_cookie_resent_when_matching_user(self):
        self.client.cookies['calendar_user_id'] = str(self.user.id)
        resp = self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'coming',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('calendar_user_id', resp.cookies)


class RSVPRemoveTest(RSVPTestMixin, TestCase):
    def setUp(self):
        self.client = Client()
        self.user = self._create_user()
        self.event = self._create_event()
        self.url = _url(f'/event/{self.event.id}/rsvp/')

    def test_remove_existing_rsvp(self):
        self._create_rsvp(self.event, self.user, 'coming')
        resp = self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'remove',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['removed'])
        self.assertEqual(RSVP.objects.count(), 0)

    def test_remove_nonexistent_rsvp(self):
        resp = self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'remove',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['removed'])

    def test_remove_rsvp_returns_removed_true(self):
        self._create_rsvp(self.event, self.user, 'maybe')
        resp = self.client.post(self.url, {
            'user_id': self.user.id,
            'status': 'remove',
        })
        self.assertEqual(resp.json()['removed'], True)


class WaitlistPromotionTest(RSVPTestMixin, TestCase):
    def setUp(self):
        self.client = Client()
        self.event = self._create_event(max_participants=2)
        self.url = _url(f'/event/{self.event.id}/rsvp/')

    def _create_waitlist_scenario(self):
        user1 = self._create_user('User1')
        user2 = self._create_user('User2')
        user3 = self._create_user('User3')
        user3.ntfy_enabled = True
        user3.ntfy_server = 'ntfy.sh'
        user3.save()

        self._create_rsvp(self.event, user1, 'coming')
        self._create_rsvp(self.event, user2, 'coming')
        self._create_rsvp(self.event, user3, 'coming')
        return user1, user2, user3

    def test_confirmed_user_removed_triggers_waitlist_notification(self):
        user1, user2, user3 = self._create_waitlist_scenario()

        resp = self.client.post(self.url, {
            'user_id': user1.id,
            'status': 'remove',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(RSVP.objects.filter(status='coming').count(), 2)

    def test_waitlisted_user_removed_no_notification(self):
        user1, user2, user3 = self._create_waitlist_scenario()

        RSVP.objects.filter(user=user1).delete()
        resp = self.client.post(self.url, {
            'user_id': user3.id,
            'status': 'remove',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(RSVP.objects.filter(status='coming').count(), 1)

    def test_status_change_from_coming_triggers_waitlist(self):
        user1, user2, user3 = self._create_waitlist_scenario()

        resp = self.client.post(self.url, {
            'user_id': user1.id,
            'status': 'not_coming',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(RSVP.objects.filter(status='coming').count(), 2)

    def test_status_change_from_maybe_no_waitlist_trigger(self):
        user1 = self._create_user('User1')
        user2 = self._create_user('User2')
        self._create_rsvp(self.event, user1, 'coming')
        self._create_rsvp(self.event, user2, 'maybe')

        resp = self.client.post(self.url, {
            'user_id': user2.id,
            'status': 'not_coming',
        })
        self.assertEqual(resp.status_code, 200)

    def test_no_max_participants_no_waitlist(self):
        event = self._create_event(max_participants=None)
        user1 = self._create_user('User1')
        self._create_rsvp(event, user1, 'coming')

        resp = self.client.post(_url(f'/event/{event.id}/rsvp/'), {
            'user_id': user1.id,
            'status': 'remove',
        })
        self.assertEqual(resp.status_code, 200)


class GuestRSVPTest(RSVPTestMixin, TestCase):
    def setUp(self):
        self.client = Client()
        self.event = self._create_event()
        self.url = _url(f'/event/{self.event.id}/guest-rsvp/')

    def test_guest_rsvp_coming(self):
        resp = self.client.post(self.url, {
            'guest_name': 'Guest One',
            'status': 'coming',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'coming')

        self.event.refresh_from_db()
        self.assertEqual(len(self.event.guests), 1)
        self.assertEqual(self.event.guests[0]['name'], 'Guest One')

    def test_guest_name_required(self):
        resp = self.client.post(self.url, {
            'guest_name': '',
            'status': 'coming',
        })
        self.assertEqual(resp.status_code, 400)

    def test_guest_name_whitespace_only(self):
        resp = self.client.post(self.url, {
            'guest_name': '   ',
            'status': 'coming',
        })
        self.assertEqual(resp.status_code, 400)

    def test_guest_name_sanitized(self):
        resp = self.client.post(self.url, {
            'guest_name': '  Guest\x00Name\x01  ',
            'status': 'coming',
        })
        self.assertEqual(resp.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.guests[0]['name'], 'GuestName')

    def test_guest_name_too_long_truncated(self):
        resp = self.client.post(self.url, {
            'guest_name': 'A' * 101,
            'status': 'coming',
        })
        self.assertEqual(resp.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(len(self.event.guests[0]['name']), 100)

    def test_guest_name_exactly_100_chars(self):
        resp = self.client.post(self.url, {
            'guest_name': 'A' * 100,
            'status': 'coming',
        })
        self.assertEqual(resp.status_code, 200)

    def test_guest_invalid_status(self):
        resp = self.client.post(self.url, {
            'guest_name': 'Guest',
            'status': 'invalid',
        })
        self.assertEqual(resp.status_code, 400)

    def test_guest_update_existing_status(self):
        self.client.post(self.url, {'guest_name': 'Guest', 'status': 'coming'})
        resp = self.client.post(self.url, {'guest_name': 'Guest', 'status': 'not_coming'})
        self.assertEqual(resp.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(len(self.event.guests), 1)
        self.assertEqual(self.event.guests[0]['status'], 'not_coming')

    def test_guest_remove(self):
        self.client.post(self.url, {'guest_name': 'Guest', 'status': 'coming'})
        resp = self.client.post(self.url, {
            'guest_name': 'Guest',
            'action': 'remove',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['removed'])
        self.event.refresh_from_db()
        self.assertEqual(len(self.event.guests), 0)

    def test_guest_occurrence_date(self):
        occ_date = '2025-06-22'
        resp = self.client.post(self.url, {
            'guest_name': 'Guest',
            'status': 'coming',
            'occurrence_date': occ_date,
        })
        self.assertEqual(resp.status_code, 200)

    def test_get_method_rejected(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)
