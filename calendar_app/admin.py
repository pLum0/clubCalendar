from datetime import datetime, timedelta

from django import forms
from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext as _

from .admin_site import custom_admin_site
from .models import RSVP, CalendarUser, Event, OccurrenceDetails, Tag
from .notifications import notify_rsvps_event_change


class OccurrenceDetailsForm(forms.ModelForm):
    occurrence_select = forms.ChoiceField(
        required=False,
        label=_('Select occurrence'),
        help_text=_('Choose from upcoming occurrences (recurring events only)')
    )

    class Meta:
        model = OccurrenceDetails
        fields = ['event', 'occurrence_select', 'occurrence_date', 'cancelled', 'reason', 'override_start_time', 'override_end_time', 'guests']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['occurrence_select'].choices = [('', '-- Enter date manually or select from list --')]

        if 'event' in self.data:
            try:
                event_id = int(self.data.get('event'))
                event = Event.objects.get(pk=event_id)
                self._populate_occurrences(event)
            except (ValueError, Event.DoesNotExist):
                pass
        elif self.instance.pk and self.instance.event:
            self._populate_occurrences(self.instance.event)

    def _populate_occurrences(self, event):
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
                self.fields['occurrence_select'].choices.append(
                    (date_val.isoformat(), date_val.strftime('%A, %B %d, %Y'))
                )

    def clean(self):
        cleaned_data = super().clean()
        occurrence_select = cleaned_data.get('occurrence_select')
        occurrence_date = cleaned_data.get('occurrence_date')

        if occurrence_select:
            cleaned_data['occurrence_date'] = occurrence_select
        elif not occurrence_date:
            raise forms.ValidationError(_('Please select an occurrence or enter a date.'))

        return cleaned_data


@admin.register(Tag, site=custom_admin_site)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color']
    search_fields = ['name']


@admin.register(OccurrenceDetails, site=custom_admin_site)
class OccurrenceDetailsAdmin(admin.ModelAdmin):
    form = OccurrenceDetailsForm
    list_display = ['event', 'occurrence_date', 'cancelled', 'override_start_time', 'override_end_time', 'reason']
    list_filter = ['occurrence_date', 'event', 'cancelled']
    search_fields = ['event__title', 'reason']
    date_hierarchy = 'occurrence_date'
    fieldsets = (
        ('Occurrence', {
            'fields': ('event', 'occurrence_select', 'occurrence_date')
        }),
        ('Options', {
            'fields': ('cancelled', 'reason', 'override_start_time', 'override_end_time', 'guests')
        }),
    )

    class Media:
        js = ('admin/js/occurrence_details.js',)

    def save_model(self, request, obj, form, change):
        old_cancelled = False
        old_reason = ''
        old_start_time = None
        old_end_time = None

        if change and obj.pk:
            try:
                old = OccurrenceDetails.objects.get(pk=obj.pk)
                old_cancelled = old.cancelled
                old_reason = old.reason
                old_start_time = old.override_start_time
                old_end_time = old.override_end_time
            except OccurrenceDetails.DoesNotExist:
                pass

        super().save_model(request, obj, form, change)

        if obj.cancelled and not old_cancelled:
            notify_rsvps_event_change(obj.event, obj.occurrence_date, 'cancelled', obj.reason)
        elif not obj.cancelled and old_cancelled:
            notify_rsvps_event_change(obj.event, obj.occurrence_date, 'uncancelled')
        elif obj.reason and obj.reason != old_reason:
            if obj.cancelled:
                notify_rsvps_event_change(obj.event, obj.occurrence_date, 'cancelled', obj.reason)
            else:
                notify_rsvps_event_change(obj.event, obj.occurrence_date, 'notice', obj.reason)
        elif (obj.override_start_time != old_start_time or obj.override_end_time != old_end_time) and not obj.cancelled:
            notify_rsvps_event_change(obj.event, obj.occurrence_date, 'time_changed', start_time=obj.override_start_time, end_time=obj.override_end_time)


@admin.register(Event, site=custom_admin_site)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'start_time', 'end_time', 'location', 'is_recurring', 'cancelled']
    list_filter = ['date', 'tags', 'cancelled']
    search_fields = ['title', 'description', 'location']
    filter_horizontal = ['tags']
    actions = ['cancel_events', 'uncancel_events']

    def is_recurring(self, obj):
        return obj.is_recurring
    is_recurring.boolean = True
    is_recurring.short_description = _('Recurring')

    def save_model(self, request, obj, form, change):
        old_cancelled = False
        old_cancel_reason = ''

        if change and obj.pk:
            try:
                old = Event.objects.get(pk=obj.pk)
                old_cancelled = old.cancelled
                old_cancel_reason = old.cancel_reason
            except Event.DoesNotExist:
                pass

        super().save_model(request, obj, form, change)

        if not obj.is_recurring:
            if obj.cancelled and not old_cancelled:
                notify_rsvps_event_change(obj, obj.date, 'cancelled', obj.cancel_reason)
            elif not obj.cancelled and old_cancelled:
                notify_rsvps_event_change(obj, obj.date, 'uncancelled')
            elif obj.cancel_reason and obj.cancel_reason != old_cancel_reason:
                if obj.cancelled:
                    notify_rsvps_event_change(obj, obj.date, 'cancelled', obj.cancel_reason)
                else:
                    notify_rsvps_event_change(obj, obj.date, 'notice', obj.cancel_reason)

    def cancel_events(self, request, queryset):
        to_notify = list(queryset.filter(recurrence=None, cancelled=False))
        count = queryset.update(cancelled=True)
        for event in to_notify:
            event.refresh_from_db()
            notify_rsvps_event_change(event, event.date, 'cancelled')
        self.message_user(request, f'{count} event(s) marked as cancelled.')
    cancel_events.short_description = _('Cancel selected events')

    def uncancel_events(self, request, queryset):
        to_notify = list(queryset.filter(recurrence=None, cancelled=True))
        count = queryset.update(cancelled=False, cancel_reason='')
        for event in to_notify:
            event.refresh_from_db()
            notify_rsvps_event_change(event, event.date, 'uncancelled')
        self.message_user(request, f'{count} event(s) uncancelled.')
    uncancel_events.short_description = _('Uncancel selected events')


@admin.register(RSVP, site=custom_admin_site)
class RSVPAdmin(admin.ModelAdmin):
    list_display = ['user_display', 'event', 'status', 'created_at']
    list_filter = ['status', 'event', 'created_at']
    search_fields = ['user__name', 'event__title', 'comment']

    def user_display(self, obj):
        if obj.user:
            return f"{obj.user.name} ({obj.user.team.name})"
        return "-"
    user_display.short_description = _('User')


@admin.register(CalendarUser, site=custom_admin_site)
class CalendarUserAdmin(admin.ModelAdmin):
    list_display = ['name', 'team', 'language', 'ntfy_enabled', 'ntfy_server']
    list_filter = ['team', 'language']
    search_fields = ['name', 'team__name']
    ordering = ['name', 'team']
