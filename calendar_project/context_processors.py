from django.conf import settings


def site_settings(request):
    return {
        'SITE_NAME': settings.SITE_NAME,
        'SITE_LOGO': settings.SITE_LOGO,
        'SECRET_PATH': settings.SECRET_PATH,
    }
