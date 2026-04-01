import urllib.error
from datetime import date, time
from unittest.mock import MagicMock, patch

from django.test import TestCase

from calendar_app.models import RSVP, CalendarUser, Event, Tag
from calendar_app.notifications import (
    _build_event_url,
    notify_rsvps_event_change,
    notify_waitlist_user,
    send_ntfy_notification,
)
from calendar_app.validators import (
    _get_allowed_ntfy_hosts,
    generate_ntfy_topic,
    get_ntfy_url,
    sanitize_guest_name,
)


class GenerateNtfyTopicTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Test Team', color='#000000')

    @patch('calendar_app.validators.settings.SECRET_PATH', '')
    def test_topic_from_name_and_team(self):
        user = CalendarUser(name='Alice', team=self.team)
        topic = generate_ntfy_topic(user)
        self.assertEqual(topic, 'alice_testteam')

    @patch('calendar_app.validators.settings.SECRET_PATH', '')
    def test_special_chars_stripped(self):
        user = CalendarUser(name='Hans Müller', team=self.team)
        topic = generate_ntfy_topic(user)
        self.assertEqual(topic, 'hansmller_testteam')

    @patch('calendar_app.validators.settings.SECRET_PATH', 'mysecret')
    def test_topic_with_secret_path(self):
        user = CalendarUser(name='Bob', team=self.team)
        topic = generate_ntfy_topic(user)
        self.assertEqual(topic, 'mysecret_bob_testteam')

    @patch('calendar_app.validators.settings.SECRET_PATH', '')
    def test_topic_without_secret_path(self):
        user = CalendarUser(name='Bob', team=self.team)
        topic = generate_ntfy_topic(user)
        self.assertEqual(topic, 'bob_testteam')

    @patch('calendar_app.validators.settings.SECRET_PATH', '')
    def test_topic_parts_lowercased(self):
        team = Tag(name='MyTeam')
        user = CalendarUser(name='JohnDoe', team=team)
        topic = generate_ntfy_topic(user)
        self.assertEqual(topic, 'johndoe_myteam')


class GetNtfyUrlTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team', color='#000000')

    def test_disabled_returns_empty(self):
        user = CalendarUser(name='Alice', team=self.team, ntfy_enabled=False)
        self.assertEqual(get_ntfy_url(user), '')

    @patch('calendar_app.validators.settings.SECRET_PATH', '')
    def test_default_server(self):
        user = CalendarUser(name='Alice', team=self.team, ntfy_enabled=True, ntfy_server='')
        url = get_ntfy_url(user)
        self.assertEqual(url, 'https://ntfy.sh/alice_team')

    @patch('calendar_app.validators.settings.SECRET_PATH', '')
    def test_custom_server(self):
        user = CalendarUser(name='Alice', team=self.team, ntfy_enabled=True, ntfy_server='ntfy.example.com')
        url = get_ntfy_url(user)
        self.assertEqual(url, 'https://ntfy.example.com/alice_team')

    @patch('calendar_app.validators.settings.SECRET_PATH', '')
    def test_custom_server_with_scheme(self):
        user = CalendarUser(name='Alice', team=self.team, ntfy_enabled=True, ntfy_server='https://ntfy.example.com')
        url = get_ntfy_url(user)
        self.assertEqual(url, 'https://ntfy.example.com/alice_team')


class GetAllowedNtfyHostsTest(TestCase):
    def test_default_hosts(self):
        hosts = _get_allowed_ntfy_hosts()
        self.assertEqual(hosts, ['ntfy.sh'])

    @patch('calendar_app.validators.settings.NTFY_ALLOWED_HOSTS', 'ntfy.example.com')
    def test_extra_host(self):
        hosts = _get_allowed_ntfy_hosts()
        self.assertEqual(hosts, ['ntfy.sh', 'ntfy.example.com'])

    @patch('calendar_app.validators.settings.NTFY_ALLOWED_HOSTS', 'https://ntfy.example.com')
    def test_extra_host_with_scheme(self):
        hosts = _get_allowed_ntfy_hosts()
        self.assertEqual(hosts, ['ntfy.sh', 'ntfy.example.com'])

    @patch('calendar_app.validators.settings.NTFY_ALLOWED_HOSTS', 'a.com, b.com')
    def test_multiple_hosts(self):
        hosts = _get_allowed_ntfy_hosts()
        self.assertEqual(hosts, ['ntfy.sh', 'a.com', 'b.com'])


class SanitizeGuestNameTest(TestCase):
    def test_empty_name(self):
        self.assertEqual(sanitize_guest_name(''), '')
        self.assertEqual(sanitize_guest_name(None), '')

    def test_strips_whitespace(self):
        self.assertEqual(sanitize_guest_name('  hello  '), 'hello')

    def test_removes_control_chars(self):
        self.assertEqual(sanitize_guest_name('hello\x00world'), 'helloworld')
        self.assertEqual(sanitize_guest_name('test\x01\x02'), 'test')
        self.assertEqual(sanitize_guest_name('a\x7fb'), 'ab')

    def test_truncates_to_100(self):
        self.assertEqual(len(sanitize_guest_name('a' * 200)), 100)

    def test_normal_name_unchanged(self):
        self.assertEqual(sanitize_guest_name('John Doe'), 'John Doe')


class SendNtfyNotificationTest(TestCase):
    @patch('urllib.request.urlopen')
    def test_send_to_generated_url(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        result = send_ntfy_notification('https://ntfy.sh/alice_team', 'Title', 'Message')
        self.assertTrue(result)
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.full_url, 'https://ntfy.sh/alice_team')

    @patch('urllib.request.urlopen')
    def test_send_to_plain_topic(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        result = send_ntfy_notification('test-topic', 'Title', 'Message')
        self.assertTrue(result)
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.full_url, 'https://ntfy.sh/test-topic')

    def test_empty_topic_returns_false(self):
        self.assertFalse(send_ntfy_notification('', 'Title', 'Message'))
        self.assertFalse(send_ntfy_notification(None, 'Title', 'Message'))

    @patch('urllib.request.urlopen')
    def test_disallowed_host_returns_false(self, mock_urlopen):
        result = send_ntfy_notification('https://evil.com/topic', 'Title', 'Message')
        self.assertFalse(result)
        mock_urlopen.assert_not_called()

    @patch('urllib.request.urlopen', side_effect=urllib.error.URLError('fail'))
    def test_network_error_returns_false(self, mock_urlopen):
        result = send_ntfy_notification('test-topic', 'Title', 'Message')
        self.assertFalse(result)

    @patch('urllib.request.urlopen')
    def test_click_url_header(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        send_ntfy_notification('topic', 'T', 'M', click_url='http://example.com')
        req = mock_urlopen.call_args[0][0]
        self.assertIn('Click', req.headers)

    @patch('urllib.request.urlopen')
    def test_tags_header(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        send_ntfy_notification('topic', 'T', 'M', tags='tada')
        req = mock_urlopen.call_args[0][0]
        self.assertIn('Tags', req.headers)


class NotifyWaitlistUserTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team', color='#000000')

    @patch('calendar_app.notifications.send_notification_async')
    def test_sends_notification_to_enabled_user(self, mock_async):
        user = CalendarUser.objects.create(
            name='Alice', team=self.team, ntfy_enabled=True, ntfy_server='ntfy.sh', language='en'
        )
        event = Event.objects.create(
            title='Test', date=date(2025, 6, 15), start_time=time(10, 0)
        )
        rsvp = RSVP.objects.create(
            event=event, occurrence_date=event.date, user=user, status='coming'
        )
        notify_waitlist_user(rsvp, event, event.date)
        mock_async.assert_called_once()
        args = mock_async.call_args[0]
        self.assertIn('ntfy.sh', args[0])
        self.assertIn('alice', args[0])

    @patch('calendar_app.notifications.send_notification_async')
    def test_no_notification_when_disabled(self, mock_async):
        user = CalendarUser.objects.create(name='Bob', team=self.team, ntfy_enabled=False)
        event = Event.objects.create(
            title='Test', date=date(2025, 6, 15), start_time=time(10, 0)
        )
        rsvp = RSVP.objects.create(
            event=event, occurrence_date=event.date, user=user, status='coming'
        )
        notify_waitlist_user(rsvp, event, event.date)
        mock_async.assert_not_called()


class NotifyRsvpsEventChangeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Tag.objects.create(name='Team', color='#000000')

    def setUp(self):
        self.user_with_ntfy = CalendarUser.objects.create(
            name='Alice', team=self.team, ntfy_enabled=True, ntfy_server='ntfy.sh', language='en'
        )
        self.user_no_ntfy = CalendarUser.objects.create(
            name='Bob', team=self.team, ntfy_enabled=False, language='en'
        )
        self.event = Event.objects.create(
            title='Test Event', date=date(2025, 6, 15), start_time=time(10, 0)
        )

    @patch('calendar_app.notifications.send_notification_async')
    def test_cancelled_notifies_enabled_users(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_ntfy, status='coming'
        )
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_no_ntfy, status='coming'
        )
        notify_rsvps_event_change(self.event, None, 'cancelled', 'Bad weather')
        mock_async.assert_called_once()
        args = mock_async.call_args[0]
        self.assertIn('cancel', args[1].lower())

    @patch('calendar_app.notifications.send_notification_async')
    def test_uncancelled_notification(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_ntfy, status='coming'
        )
        notify_rsvps_event_change(self.event, None, 'uncancelled')
        mock_async.assert_called_once()
        args = mock_async.call_args[0]
        self.assertIn('restor', args[1].lower())

    @patch('calendar_app.notifications.send_notification_async')
    def test_notice_notification(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_ntfy, status='maybe'
        )
        notify_rsvps_event_change(self.event, None, 'notice', 'New info')
        mock_async.assert_called_once()

    @patch('calendar_app.notifications.send_notification_async')
    def test_time_changed_notification(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_ntfy, status='coming'
        )
        notify_rsvps_event_change(
            self.event, None, 'time_changed',
            start_time=time(14, 0), end_time=time(16, 0)
        )
        mock_async.assert_called_once()

    @patch('calendar_app.notifications.send_notification_async')
    def test_modified_notification(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_ntfy, status='coming'
        )
        notify_rsvps_event_change(self.event, None, 'modified')
        mock_async.assert_called_once()

    @patch('calendar_app.notifications.send_notification_async')
    def test_not_coming_users_not_notified(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_ntfy, status='not_coming'
        )
        notify_rsvps_event_change(self.event, None, 'cancelled')
        mock_async.assert_not_called()

    @patch('calendar_app.notifications.send_notification_async')
    def test_unknown_change_type_skipped(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_ntfy, status='coming'
        )
        notify_rsvps_event_change(self.event, None, 'unknown_type')
        mock_async.assert_not_called()

    @patch('calendar_app.notifications.send_notification_async')
    def test_occurrence_date_filter(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_ntfy, status='coming'
        )
        RSVP.objects.create(
            event=self.event, occurrence_date=date(2025, 6, 22),
            user=self.user_with_ntfy, status='coming'
        )
        notify_rsvps_event_change(self.event, date(2025, 6, 22), 'cancelled')
        mock_async.assert_called_once()

    @patch('calendar_app.notifications.send_notification_async')
    def test_language_per_user(self, mock_async):
        user_de = CalendarUser.objects.create(
            name='Klaus', team=self.team, ntfy_enabled=True, ntfy_server='ntfy.sh', language='de'
        )
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=user_de, status='coming'
        )
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_ntfy, status='coming'
        )
        notify_rsvps_event_change(self.event, None, 'cancelled')
        self.assertEqual(mock_async.call_count, 2)

    @patch('calendar_app.notifications.send_notification_async')
    def test_disabled_users_not_included(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_no_ntfy, status='coming'
        )
        notify_rsvps_event_change(self.event, None, 'cancelled')
        mock_async.assert_not_called()


class BuildEventUrlTest(TestCase):
    @patch('calendar_app.notifications.settings.SITE_URL', 'https://example.com')
    @patch('calendar_app.notifications.settings.SECRET_PATH', '')
    def test_url_without_secret_path(self):
        event = MagicMock()
        event.id = 42
        url = _build_event_url(event, '2025-06-15')
        self.assertEqual(url, 'https://example.com/event/42/?date=2025-06-15')

    @patch('calendar_app.notifications.settings.SITE_URL', 'https://example.com')
    @patch('calendar_app.notifications.settings.SECRET_PATH', 'secret')
    def test_url_with_secret_path(self):
        event = MagicMock()
        event.id = 42
        url = _build_event_url(event, '2025-06-15')
        self.assertEqual(url, 'https://example.com/secret/event/42/?date=2025-06-15')

    @patch('calendar_app.notifications.settings.SITE_URL', '')
    def test_no_site_url(self):
        event = MagicMock()
        event.id = 42
        url = _build_event_url(event, '2025-06-15')
        self.assertEqual(url, '')
