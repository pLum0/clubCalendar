from datetime import date, time, datetime
from unittest.mock import patch, MagicMock
import urllib.error
from django.test import TestCase
from django.utils import timezone
from calendar_app.models import Tag, CalendarUser, Event, RSVP, OccurrenceDetails
from calendar_app.notifications import (
    send_ntfy_notification,
    notify_waitlist_user,
    notify_rsvps_event_change,
    _build_event_url,
)
from calendar_app.validators import validate_ntfy_topic, sanitize_guest_name


class ValidateNtfyTopicTest(TestCase):
    def test_empty_topic_returns_unchanged(self):
        self.assertEqual(validate_ntfy_topic(''), '')
        self.assertEqual(validate_ntfy_topic(None), None)

    def test_plain_topic_valid(self):
        self.assertEqual(validate_ntfy_topic('my-topic'), 'my-topic')

    def test_plain_topic_with_underscores(self):
        self.assertEqual(validate_ntfy_topic('my_topic'), 'my_topic')

    def test_plain_topic_alphanumeric(self):
        self.assertEqual(validate_ntfy_topic('topic123'), 'topic123')

    def test_plain_topic_invalid_chars(self):
        with self.assertRaises(ValueError):
            validate_ntfy_topic('invalid topic!')

    def test_plain_topic_too_long(self):
        with self.assertRaises(ValueError):
            validate_ntfy_topic('a' * 101)

    def test_url_ntfy_sh_allowed(self):
        self.assertEqual(
            validate_ntfy_topic('https://ntfy.sh/my-topic'),
            'https://ntfy.sh/my-topic',
        )

    def test_url_other_host_rejected(self):
        with self.assertRaises(ValueError):
            validate_ntfy_topic('https://evil.com/topic')

    def test_url_localhost_rejected(self):
        with self.assertRaises(ValueError):
            validate_ntfy_topic('http://localhost:8080/topic')

    def test_topic_stripped(self):
        self.assertEqual(validate_ntfy_topic('  my-topic  '), 'my-topic')

    def test_url_ssrf_aws_metadata(self):
        with self.assertRaises(ValueError):
            validate_ntfy_topic('http://169.254.169.254/latest/meta-data/')

    @patch('calendar_app.validators.settings.NTFY_ALLOWED_HOSTS', 'ntfy.example.com')
    def test_extra_allowed_host(self):
        self.assertEqual(
            validate_ntfy_topic('https://ntfy.example.com/topic'),
            'https://ntfy.example.com/topic',
        )


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
    def test_send_to_plain_topic(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        result = send_ntfy_notification('test-topic', 'Title', 'Message')
        self.assertTrue(result)
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.full_url, 'https://ntfy.sh/test-topic')

    @patch('urllib.request.urlopen')
    def test_send_to_url(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        result = send_ntfy_notification('https://ntfy.sh/topic', 'Title', 'Message')
        self.assertTrue(result)

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
    def test_sends_notification_to_waitlisted_user(self, mock_async):
        user = CalendarUser.objects.create(
            name='Alice', team=self.team, ntfy_topic='test-topic', language='en'
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
        self.assertEqual(args[0], 'test-topic')

    @patch('calendar_app.notifications.send_notification_async')
    def test_no_notification_without_topic(self, mock_async):
        user = CalendarUser.objects.create(name='Bob', team=self.team, ntfy_topic='')
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
        self.user_with_topic = CalendarUser.objects.create(
            name='Alice', team=self.team, ntfy_topic='topic1', language='en'
        )
        self.user_no_topic = CalendarUser.objects.create(
            name='Bob', team=self.team, ntfy_topic='', language='en'
        )
        self.event = Event.objects.create(
            title='Test Event', date=date(2025, 6, 15), start_time=time(10, 0)
        )

    @patch('calendar_app.notifications.send_notification_async')
    def test_cancelled_notifies_coming_users(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_topic, status='coming'
        )
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_no_topic, status='coming'
        )
        notify_rsvps_event_change(self.event, None, 'cancelled', 'Bad weather')
        mock_async.assert_called_once()
        args = mock_async.call_args[0]
        self.assertIn('cancel', args[1].lower())

    @patch('calendar_app.notifications.send_notification_async')
    def test_uncancelled_notification(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_topic, status='coming'
        )
        notify_rsvps_event_change(self.event, None, 'uncancelled')
        mock_async.assert_called_once()
        args = mock_async.call_args[0]
        self.assertIn('restor', args[1].lower())

    @patch('calendar_app.notifications.send_notification_async')
    def test_notice_notification(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_topic, status='maybe'
        )
        notify_rsvps_event_change(self.event, None, 'notice', 'New info')
        mock_async.assert_called_once()

    @patch('calendar_app.notifications.send_notification_async')
    def test_time_changed_notification(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_topic, status='coming'
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
            user=self.user_with_topic, status='coming'
        )
        notify_rsvps_event_change(self.event, None, 'modified')
        mock_async.assert_called_once()

    @patch('calendar_app.notifications.send_notification_async')
    def test_not_coming_users_not_notified(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_topic, status='not_coming'
        )
        notify_rsvps_event_change(self.event, None, 'cancelled')
        mock_async.assert_not_called()

    @patch('calendar_app.notifications.send_notification_async')
    def test_unknown_change_type_skipped(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_topic, status='coming'
        )
        notify_rsvps_event_change(self.event, None, 'unknown_type')
        mock_async.assert_not_called()

    @patch('calendar_app.notifications.send_notification_async')
    def test_occurrence_date_filter(self, mock_async):
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_topic, status='coming'
        )
        RSVP.objects.create(
            event=self.event, occurrence_date=date(2025, 6, 22),
            user=self.user_with_topic, status='coming'
        )
        notify_rsvps_event_change(self.event, date(2025, 6, 22), 'cancelled')
        mock_async.assert_called_once()

    @patch('calendar_app.notifications.send_notification_async')
    def test_language_per_user(self, mock_async):
        user_de = CalendarUser.objects.create(
            name='Klaus', team=self.team, ntfy_topic='de-topic', language='de'
        )
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=user_de, status='coming'
        )
        RSVP.objects.create(
            event=self.event, occurrence_date=self.event.date,
            user=self.user_with_topic, status='coming'
        )
        notify_rsvps_event_change(self.event, None, 'cancelled')
        self.assertEqual(mock_async.call_count, 2)


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
