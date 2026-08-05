import re

from django.conf import settings
from django.utils.html import strip_tags

from calendar_app.validators import _get_allowed_ntfy_hosts

_BR_TAG = re.compile(r'<br\s*/?>', re.IGNORECASE)


def _plain_site_name(site_name):
    """SITE_NAME without markup, for <title> and alt text.

    SITE_NAME may contain <br /> so the header can span two lines. Line breaks
    become spaces rather than being dropped, so "A<br />B" reads "A B" and not "AB".
    """
    return ' '.join(strip_tags(_BR_TAG.sub(' ', site_name)).split())


def site_settings(request):
    return {
        'SITE_NAME': settings.SITE_NAME,
        'SITE_NAME_PLAIN': _plain_site_name(settings.SITE_NAME),
        'SITE_LOGO': settings.SITE_LOGO,
        'SECRET_PATH': settings.SECRET_PATH,
        'NTFY_SERVERS': _get_allowed_ntfy_hosts(),
        'GITHUB_URL': settings.GITHUB_URL,
    }
