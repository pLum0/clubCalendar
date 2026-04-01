from django.conf import settings
from django.urls import include, path

from calendar_app.admin_site import custom_admin_site

urlpatterns = []

if settings.SECRET_PATH:
    urlpatterns += [
        path(f'{settings.SECRET_PATH}/', include('calendar_app.urls')),
        path(f'{settings.SECRET_PATH}/admin/', custom_admin_site.urls),
        path(f'{settings.SECRET_PATH}/i18n/', include('django.conf.urls.i18n')),
    ]
else:
    urlpatterns += [
        path('', include('calendar_app.urls')),
        path('admin/', custom_admin_site.urls),
        path('i18n/', include('django.conf.urls.i18n')),
    ]
