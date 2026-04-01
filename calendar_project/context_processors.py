from django.conf import settings

from calendar_app.validators import _get_allowed_ntfy_hosts


def site_settings(request):
    return {
        'SITE_NAME': settings.SITE_NAME,
        'SITE_LOGO': settings.SITE_LOGO,
        'SECRET_PATH': settings.SECRET_PATH,
        'NTFY_SERVERS': _get_allowed_ntfy_hosts(),
    }
