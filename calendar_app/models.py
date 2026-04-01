from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from recurrence.fields import RecurrenceField


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default='#3498db', help_text='Hex color code, e.g., #3498db')
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class CalendarUser(models.Model):
    name = models.CharField(max_length=100)
    team = models.ForeignKey(Tag, on_delete=models.PROTECT, related_name='users')
    ntfy_enabled = models.BooleanField(default=False, help_text='Enable push notifications via ntfy')
    ntfy_server = models.CharField(max_length=255, blank=True, default='', help_text='ntfy server hostname (e.g., ntfy.sh)')
    language = models.CharField(max_length=10, blank=True, default='en', help_text='User language preference')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['name', 'team']
        ordering = ['name', 'team']
    
    def __str__(self):
        return f"{self.name} ({self.team.name})"


class Event(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(blank=True, null=True)
    location = models.CharField(max_length=200, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name='events')
    recurrence = RecurrenceField(blank=True, null=True)
    cancelled = models.BooleanField(default=False)
    cancel_reason = models.TextField(blank=True)
    max_participants = models.PositiveIntegerField(blank=True, null=True)
    guests = models.JSONField(default=list, blank=True, help_text='Guest RSVPs: [{"name": "...", "status": "coming"}]')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['date', 'start_time']
    
    def __str__(self):
        return f"{self.title} - {self.date} {self.start_time}"
    
    @property
    def is_recurring(self):
        return bool(self.recurrence)


class RSVP(models.Model):
    STATUS_CHOICES = [
        ('coming', 'Coming'),
        ('not_coming', 'Not Coming'),
        ('maybe', 'Maybe'),
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='rsvps')
    occurrence_date = models.DateField(help_text='The specific date of the occurrence (for recurring events)')
    user = models.ForeignKey(CalendarUser, on_delete=models.CASCADE, related_name='rsvps')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status_updated_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['event', 'occurrence_date', 'user']
        ordering = ['status_updated_at']
    
    def __str__(self):
        return f"{self.user.name} ({self.user.team.name}) - {self.get_status_display()} for {self.event.title} on {self.occurrence_date}"


class OccurrenceDetails(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='occurrence_details')
    occurrence_date = models.DateField(help_text='The specific date of this occurrence')
    cancelled = models.BooleanField(default=False)
    reason = models.TextField(blank=True, help_text='Cancellation reason or general notice')
    override_start_time = models.TimeField(blank=True, null=True, help_text='Override default start time (optional)')
    override_end_time = models.TimeField(blank=True, null=True, help_text='Override default end time (optional)')
    guests = models.JSONField(default=list, blank=True, help_text='Guest RSVPs for this occurrence')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Occurrence details'
        unique_together = ['event', 'occurrence_date']
        ordering = ['occurrence_date']
    
    def __str__(self):
        status = "Cancelled" if self.cancelled else "Modified"
        return f"{status}: {self.event.title} on {self.occurrence_date}"
