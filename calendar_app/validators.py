import re
from urllib.parse import urlparse
from django.conf import settings


def validate_ntfy_topic(topic):
    if not topic:
        return topic

    topic = topic.strip()

    if topic.startswith('http://') or topic.startswith('https://'):
        parsed = urlparse(topic)
        hostname = parsed.hostname or ''

        allowed_hosts = ['ntfy.sh']
        extra_hosts = getattr(settings, 'NTFY_ALLOWED_HOSTS', '')
        if extra_hosts:
            allowed_hosts.extend(h.strip() for h in extra_hosts.split(',') if h.strip())

        if hostname not in allowed_hosts:
            raise ValueError(f'Host "{hostname}" is not allowed. Allowed: {", ".join(allowed_hosts)}')

        return topic

    if not re.match(r'^[a-zA-Z0-9_-]+$', topic):
        raise ValueError('Topic name can only contain letters, numbers, hyphens, and underscores.')

    if len(topic) > 100:
        raise ValueError('Topic name must be 100 characters or less.')

    return topic


def sanitize_guest_name(name):
    if not name:
        return ''
    name = name.strip()
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    return name[:100]
