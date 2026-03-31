from django.contrib import admin
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Event


def get_event_occurrences(request, event_id):
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        return JsonResponse({'occurrences': []})
    
    occurrences = []
    if event.recurrence:
        today = timezone.now().date()
        end_date = today + timedelta(days=365)
        dates = event.recurrence.between(
            datetime.combine(today, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time()),
            dtstart=datetime.combine(event.date, datetime.min.time()),
            inc=True
        )[:10]
        for occ_date in dates:
            date_val = occ_date.date()
            occurrences.append({
                'date': date_val.isoformat(),
                'label': date_val.strftime('%A, %B %d, %Y')
            })
    
    return JsonResponse({'occurrences': occurrences})


class CustomAdminSite(admin.AdminSite):
    def each_context(self, request):
        context = super().each_context(request)
        context['SECRET_PATH'] = settings.SECRET_PATH
        return context
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('get-occurrences/<int:event_id>/', get_event_occurrences, name='get_event_occurrences'),
        ]
        return custom_urls + urls


custom_admin_site = CustomAdminSite(name='custom_admin')
