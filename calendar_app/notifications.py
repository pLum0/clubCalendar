import urllib.request
import urllib.error
import threading
from urllib.parse import urlparse
from django.conf import settings
from django.utils import translation
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from .models import RSVP
from .validators import _get_allowed_ntfy_hosts, get_ntfy_url


def send_ntfy_notification(topic, title, message, click_url=None, tags=None):
    if not topic:
        return False
    if topic.startswith('http://') or topic.startswith('https://'):
        parsed = urlparse(topic)
        if parsed.hostname not in _get_allowed_ntfy_hosts():
            return False
        url = topic
    else:
        url = f'https://ntfy.sh/{topic}'
    try:
        headers = {
            'Title': title.encode('utf-8'),
            'Content-Type': 'text/plain; charset=utf-8'
        }
        if click_url:
            headers['Click'] = click_url
        if tags:
            headers['Tags'] = tags
        data = message.encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=5):
            return True
    except (urllib.error.URLError, urllib.error.HTTPError):
        return False


def send_notification_async(topic, title, message, click_url=None, tags=None):
    thread = threading.Thread(target=send_ntfy_notification, args=(topic, title, message, click_url, tags))
    thread.daemon = True
    thread.start()


def notify_waitlist_user(rsvp, event, occurrence_date):
    user = rsvp.user
    if not user or not user.ntfy_enabled:
        return
    ntfy_url = get_ntfy_url(user)
    if not ntfy_url:
        return

    with translation.override(user.language or 'en'):
        date_iso = occurrence_date.strftime('%Y-%m-%d')
        date_str = date_format(occurrence_date, 'DATE_FORMAT')
        title = _("You're off the waitlist!")

        event_url = ''
        if settings.SITE_URL:
            path = f'/event/{event.id}/?date={date_iso}'
            if settings.SECRET_PATH:
                path = f'/{settings.SECRET_PATH}{path}'
            event_url = f'{settings.SITE_URL}{path}'

        message = _("You have moved off the waitlist for '%(event_title)s' on %(date)s. You are now confirmed!") % {
            'event_title': event.title,
            'date': date_str
        }

        send_notification_async(ntfy_url, title, message, event_url or None, 'tada')


def _build_event_url(event, date_iso):
    if not settings.SITE_URL:
        return ''
    path = f'/event/{event.id}/?date={date_iso}'
    if settings.SECRET_PATH:
        path = f'/{settings.SECRET_PATH}{path}'
    return f'{settings.SITE_URL}{path}'


def notify_rsvps_event_change(event, occurrence_date=None, change_type='modified', reason=None, start_time=None, end_time=None):
    rsvps = RSVP.objects.filter(event=event, status__in=['coming', 'maybe']).select_related('user')
    rsvps = [r for r in rsvps if r.user and r.user.ntfy_enabled]
    if occurrence_date:
        rsvps = [r for r in rsvps if r.occurrence_date == occurrence_date]
    else:
        rsvps = [r for r in rsvps if r.occurrence_date == event.date]

    date_iso = (occurrence_date or event.date).strftime('%Y-%m-%d')
    event_url = _build_event_url(event, date_iso)

    for rsvp in rsvps:
        with translation.override(rsvp.user.language or 'en'):
            date_str = date_format(occurrence_date or event.date, 'DATE_FORMAT')

            if change_type == 'cancelled':
                title = _("Event cancelled: %(event_title)s") % {'event_title': event.title}
                message = _("'%(event_title)s' on %(date)s has been cancelled.") % {
                    'event_title': event.title,
                    'date': date_str
                }
                if reason:
                    message += "\n\n" + _("Reason: %(reason)s") % {'reason': reason}
                ntfy_tags = 'no_entry_sign'
            elif change_type == 'uncancelled':
                title = _("Event restored: %(event_title)s") % {'event_title': event.title}
                message = _("'%(event_title)s' on %(date)s is no longer cancelled.") % {
                    'event_title': event.title,
                    'date': date_str
                }
                ntfy_tags = 'tada'
            elif change_type == 'notice':
                title = _("Event notice: %(event_title)s") % {'event_title': event.title}
                message = _("'%(event_title)s' on %(date)s has a notice:\n\n%(reason)s") % {
                    'event_title': event.title,
                    'date': date_str,
                    'reason': reason
                }
                ntfy_tags = 'loudspeaker'
            elif change_type == 'time_changed':
                title = _("Time changed: %(event_title)s") % {'event_title': event.title}
                time_parts = []
                if start_time:
                    time_parts.append(start_time.strftime('%H:%M'))
                if end_time:
                    time_parts.append(end_time.strftime('%H:%M'))
                if time_parts:
                    time_str = " - ".join(time_parts)
                    message = _("The time for '%(event_title)s' on %(date)s has been changed to %(time)s.") % {
                        'event_title': event.title,
                        'date': date_str,
                        'time': time_str
                    }
                else:
                    message = _("The time for '%(event_title)s' on %(date)s has been changed.") % {
                        'event_title': event.title,
                        'date': date_str
                    }
                ntfy_tags = 'warning'
            elif change_type == 'modified':
                title = _("Event modified: %(event_title)s") % {'event_title': event.title}
                message = _("'%(event_title)s' on %(date)s has been modified.") % {
                    'event_title': event.title,
                    'date': date_str
                }
                ntfy_tags = None
            else:
                continue

            ntfy_url = get_ntfy_url(rsvp.user)
            if not ntfy_url:
                continue
            send_notification_async(ntfy_url, title, message, event_url or None, ntfy_tags)
