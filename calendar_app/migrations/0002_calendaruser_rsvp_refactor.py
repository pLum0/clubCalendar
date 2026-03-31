# Generated migration for CalendarUser and RSVP refactoring

from django.db import migrations, models
import django.db.models.deletion


def create_calendar_users_and_link_rsvps(apps, schema_editor):
    CalendarUser = apps.get_model('calendar_app', 'CalendarUser')
    RSVP = apps.get_model('calendar_app', 'RSVP')
    
    rsvps = RSVP.objects.all().select_related('team').order_by('-updated_at')
    
    user_map = {}
    for rsvp in rsvps:
        key = (rsvp.user_name, rsvp.team_id)
        if key not in user_map:
            user_map[key] = {
                'name': rsvp.user_name,
                'team_id': rsvp.team_id,
                'ntfy_topic': rsvp.ntfy_topic or '',
                'language': rsvp.language or 'en',
            }
    
    created_users = {}
    for key, data in user_map.items():
        user = CalendarUser.objects.create(
            name=data['name'],
            team_id=data['team_id'],
            ntfy_topic=data['ntfy_topic'],
            language=data['language'],
        )
        created_users[key] = user
    
    for rsvp in RSVP.objects.all():
        key = (rsvp.user_name, rsvp.team_id)
        if key in created_users:
            rsvp.user = created_users[key]
            rsvp.save(update_fields=['user'])


class Migration(migrations.Migration):
    dependencies = [
        ('calendar_app', '0001_squashed_merged'),
    ]

    operations = [
        migrations.CreateModel(
            name='CalendarUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('ntfy_topic', models.CharField(blank=True, default='', help_text='ntfy.sh topic for push notifications', max_length=255)),
                ('language', models.CharField(blank=True, default='en', help_text='User language preference', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='users', to='calendar_app.tag')),
            ],
            options={'ordering': ['name', 'team'], 'unique_together': {('name', 'team')}},
        ),
        migrations.AddField(model_name='rsvp', name='user', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='rsvps', to='calendar_app.calendaruser')),
        migrations.RunPython(create_calendar_users_and_link_rsvps, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(name='rsvp', unique_together=set()),
        migrations.RemoveField(model_name='rsvp', name='user_name'),
        migrations.RemoveField(model_name='rsvp', name='team'),
        migrations.RemoveField(model_name='rsvp', name='ntfy_topic'),
        migrations.RemoveField(model_name='rsvp', name='language'),
        migrations.AlterField(model_name='rsvp', name='user', field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rsvps', to='calendar_app.calendaruser')),
        migrations.AlterUniqueTogether(name='rsvp', unique_together={('event', 'occurrence_date', 'user')}),
    ]
