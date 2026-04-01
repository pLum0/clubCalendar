import re
from urllib.parse import urlparse

from django.conf import settings


def _get_allowed_ntfy_hosts():
    allowed_hosts = ['ntfy.sh']
    extra_hosts = getattr(settings, 'NTFY_ALLOWED_HOSTS', '')
    if extra_hosts:
        for h in extra_hosts.split(','):
            h = h.strip()
            if not h:
                continue
            if '://' in h:
                h = urlparse(h).hostname or h
            allowed_hosts.append(h)
    return allowed_hosts


def _sanitize_topic_part(s):
    return re.sub(r'[^a-zA-Z0-9]', '', s).lower()


def generate_ntfy_topic(user):
    parts = []
    secret = getattr(settings, 'SECRET_PATH', '')
    if secret:
        parts.append(_sanitize_topic_part(secret))
    parts.append(_sanitize_topic_part(user.name))
    parts.append(_sanitize_topic_part(user.team.name))
    return '_'.join(parts)


def get_ntfy_url(user):
    if not user.ntfy_enabled:
        return ''
    server = user.ntfy_server or 'ntfy.sh'
    if '://' not in server:
        server = f'https://{server}'
    topic = generate_ntfy_topic(user)
    return f'{server}/{topic}'


def sanitize_guest_name(name):
    if not name:
        return ''
    name = name.strip()
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    return name[:100]
