from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.db.models import Q
from django.conf import settings
from datetime import datetime, timedelta
from calendar import monthcalendar, monthrange
from urllib.parse import unquote
from collections import defaultdict
import json

from .models import Event, Tag, RSVP, OccurrenceDetails, CalendarUser
from .notifications import notify_waitlist_user, notify_rsvps_event_change
from .validators import validate_ntfy_topic, sanitize_guest_name


def get_cookie_path():
    if settings.SECRET_PATH:
        return f'/{settings.SECRET_PATH}/'
    return '/'


def _is_secure():
    return not settings.DEBUG


def get_user_preferences(request):
    user_id = request.COOKIES.get('calendar_user_id', '')
    preferred_tags = request.COOKIES.get('preferred_tags', '')
    if preferred_tags:
        preferred_tags = unquote(preferred_tags)
        preferred_tags = [tag.strip() for tag in preferred_tags.split(',') if tag.strip()]
    else:
        preferred_tags = []

    calendar_user = None
    if user_id:
        try:
            calendar_user = CalendarUser.objects.select_related('team').get(id=int(user_id))
        except (CalendarUser.DoesNotExist, ValueError):
            pass

    return {
        'calendar_user': calendar_user,
        'preferred_tags': preferred_tags,
    }


def get_guests(event, occurrence_date):
    if event.is_recurring:
        try:
            details = event.occurrence_details.get(occurrence_date=occurrence_date)
            return details.guests or []
        except OccurrenceDetails.DoesNotExist:
            return []
    else:
        return event.guests or []


def set_guests(event, occurrence_date, guests):
    if event.is_recurring:
        details, _ = OccurrenceDetails.objects.get_or_create(
            event=event, occurrence_date=occurrence_date,
        )
        details.guests = guests
        details.save(update_fields=['guests', 'updated_at'])
    else:
        event.guests = guests
        event.save(update_fields=['guests', 'updated_at'])


def get_event_occurrences(event, start_date, end_date, calendar_user=None, rsvp_data=None):
    occurrences = []
    if event.recurrence:
        recurrence_dates = event.recurrence.between(
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time()),
            dtstart=datetime.combine(event.date, datetime.min.time()),
            inc=True
        )
        occurrence_details = {
            od.occurrence_date: od
            for od in event.occurrence_details.all()
        }
        for occ_date in recurrence_dates:
            occ_date_only = occ_date.date()

            if rsvp_data is not None:
                rsvp_count = rsvp_data['count_by_date'].get(occ_date_only, 0)
                user_rsvp_status = rsvp_data['user_by_date'].get(occ_date_only)
            else:
                rsvp_count = event.rsvps.filter(occurrence_date=occ_date_only, status='coming').count()
                user_rsvp_status = None
                if calendar_user:
                    try:
                        user_rsvp = RSVP.objects.get(
                            event=event,
                            occurrence_date=occ_date_only,
                            user=calendar_user
                        )
                        user_rsvp_status = user_rsvp.status
                    except RSVP.DoesNotExist:
                        pass

            details = occurrence_details.get(occ_date_only)
            guests = details.guests if details else []
            guest_coming = sum(1 for g in (guests or []) if g.get('status') == 'coming')
            rsvp_count += guest_coming
            is_cancelled = details.cancelled if details else False
            reason = details.reason if details else ''
            start_time = details.override_start_time if details and details.override_start_time else event.start_time
            end_time = details.override_end_time if details and details.override_end_time else event.end_time

            time_changed = False
            if details:
                if details.override_start_time and details.override_start_time != event.start_time:
                    time_changed = True
                if details.override_end_time and details.override_end_time != event.end_time:
                    time_changed = True

            occ = {
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'date': occ_date_only,
                'start_time': start_time,
                'end_time': end_time,
                'location': event.location,
                'tags': event.tags.all(),
                'is_recurring': True,
                'original_event': event,
                'rsvp_count': rsvp_count,
                'user_rsvp_status': user_rsvp_status,
                'cancelled': is_cancelled,
                'cancel_reason': reason,
                'time_changed': time_changed,
            }
            occurrences.append(occ)
    else:
        if start_date <= event.date <= end_date:
            if rsvp_data is not None:
                rsvp_count = rsvp_data['count_by_date'].get(event.date, 0)
                user_rsvp_status = rsvp_data['user_by_date'].get(event.date)
            else:
                rsvp_count = event.rsvps.filter(occurrence_date=event.date, status='coming').count()
                user_rsvp_status = None
                if calendar_user:
                    try:
                        user_rsvp = RSVP.objects.get(
                            event=event,
                            occurrence_date=event.date,
                            user=calendar_user
                        )
                        user_rsvp_status = user_rsvp.status
                    except RSVP.DoesNotExist:
                        pass

            guest_coming = sum(1 for g in (event.guests or []) if g.get('status') == 'coming')
            rsvp_count += guest_coming
            occ = {
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'date': event.date,
                'start_time': event.start_time,
                'end_time': event.end_time,
                'location': event.location,
                'tags': event.tags.all(),
                'is_recurring': False,
                'original_event': event,
                'rsvp_count': rsvp_count,
                'user_rsvp_status': user_rsvp_status,
                'cancelled': event.cancelled,
                'cancel_reason': event.cancel_reason,
            }
            occurrences.append(occ)
    return occurrences


def _prefetch_rsvps(events, calendar_user):
    if not events:
        return {}

    event_ids = [e.id for e in events]
    rsvp_qs = RSVP.objects.filter(
        event_id__in=event_ids,
        status='coming'
    ).values_list('event_id', 'occurrence_date')

    count_by_event_date = defaultdict(lambda: defaultdict(int))
    for event_id, occ_date in rsvp_qs:
        count_by_event_date[event_id][occ_date] += 1

    user_rsvps = {}
    if calendar_user:
        user_rsvp_qs = RSVP.objects.filter(
            event_id__in=event_ids,
            user=calendar_user
        ).values_list('event_id', 'occurrence_date', 'status')
        for event_id, occ_date, status in user_rsvp_qs:
            user_rsvps[(event_id, occ_date)] = status

    result = {}
    for event in events:
        result[event.id] = {
            'count_by_date': dict(count_by_event_date.get(event.id, {})),
            'user_by_date': {
                date: status
                for (eid, date), status in user_rsvps.items()
                if eid == event.id
            }
        }
    return result


@ensure_csrf_cookie
def calendar_view(request):
    now = timezone.now()
    try:
        year = int(request.GET.get('year', now.year))
        month = int(request.GET.get('month', now.month))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid year or month parameter'}, status=400)

    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    first_day = datetime(year, month, 1).date()
    if month == 12:
        last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)

    user_prefs = get_user_preferences(request)
    tag_filter_param = request.GET.get('tags', '')

    if tag_filter_param:
        active_tags = [t.strip() for t in tag_filter_param.split(',') if t.strip()]
    else:
        active_tags = user_prefs['preferred_tags']

    events = Event.objects.all().prefetch_related('tags', 'occurrence_details')

    non_recurring_filter = Q(date__range=(first_day, last_day), recurrence=None)
    recurring_filter = Q(recurrence__isnull=False)
    events = events.filter(non_recurring_filter | recurring_filter)

    if active_tags:
        events = events.filter(Q(tags__name__in=active_tags) | Q(tags__isnull=True)).distinct()

    calendar_data = monthcalendar(year, month)
    week_numbers = []
    for week in calendar_data:
        first_nonzero_day = next((d for d in week if d != 0), 1)
        week_num = datetime(year, month, first_nonzero_day).isocalendar()[1]
        week_numbers.append(week_num)

    calendar_user = user_prefs.get('calendar_user')
    events_list = list(events)
    rsvp_data = _prefetch_rsvps(events_list, calendar_user)

    events_by_day = {}
    for event in events_list:
        occurrences = get_event_occurrences(
            event, first_day, last_day, calendar_user,
            rsvp_data=rsvp_data.get(event.id)
        )
        for occ in occurrences:
            day = occ['date'].day
            if day not in events_by_day:
                events_by_day[day] = []
            events_by_day[day].append(occ)

    tags = Tag.objects.all()
    user_prefs['preferred_tags'] = active_tags

    all_users_data = []
    if not calendar_user:
        all_users_data = list(
            CalendarUser.objects.select_related('team').values('id', 'name', 'team_id', 'team__name')
        )

    context = {
        'year': year,
        'month': month,
        'month_name': date_format(datetime(year, month, 1), format='F'),
        'calendar_data': calendar_data,
        'week_numbers': week_numbers,
        'today': now.date(),
        'events_by_day': events_by_day,
        'tags': tags,
        'user_prefs': user_prefs,
        'all_users': all_users_data,
        'prev_month': month - 1 if month > 1 else 12,
        'prev_year': year if month > 1 else year - 1,
        'next_month': month + 1 if month < 12 else 1,
        'next_year': year if month < 12 else year + 1,
        'tag_filter': ','.join(active_tags) if active_tags else '',
    }
    return render(request, 'calendar_app/calendar.html', context)


def event_detail(request, event_id):
    event = get_object_or_404(Event.objects.prefetch_related('tags', 'occurrence_details'), pk=event_id)
    user_prefs = get_user_preferences(request)

    occurrence_date = request.GET.get('date')
    if occurrence_date:
        try:
            occurrence_date = datetime.strptime(occurrence_date, '%Y-%m-%d').date()
        except ValueError:
            occurrence_date = None

    if not occurrence_date:
        occurrence_date = event.date

    is_cancelled = False
    cancel_reason = ''
    start_time = event.start_time
    end_time = event.end_time
    time_changed = False

    if event.cancelled and occurrence_date == event.date and not event.is_recurring:
        is_cancelled = True
        cancel_reason = event.cancel_reason
    elif event.is_recurring:
        try:
            details = event.occurrence_details.get(occurrence_date=occurrence_date)
            is_cancelled = details.cancelled
            cancel_reason = details.reason
            if details.override_start_time:
                start_time = details.override_start_time
                if start_time != event.start_time:
                    time_changed = True
            if details.override_end_time:
                end_time = details.override_end_time
                if end_time != event.end_time:
                    time_changed = True
        except OccurrenceDetails.DoesNotExist:
            pass

    calendar_user = user_prefs.get('calendar_user')

    all_rsvps = list(
        RSVP.objects.filter(event=event, occurrence_date=occurrence_date)
        .select_related('user__team')
    )

    user_rsvp = None
    if calendar_user:
        user_rsvp = next(
            (r for r in all_rsvps if r.user_id == calendar_user.id),
            None,
        )

    rsvps_by_status = {'coming': [], 'not_coming': [], 'maybe': []}
    rsvp_status_map = {}
    for r in all_rsvps:
        rsvps_by_status[r.status].append(r)
        rsvp_status_map[r.user_id] = r.status

    guests = get_guests(event, occurrence_date)
    guests_by_status = {
        'coming': [g for g in guests if g.get('status') == 'coming'],
        'not_coming': [g for g in guests if g.get('status') == 'not_coming'],
        'maybe': [g for g in guests if g.get('status') == 'maybe'],
    }

    team_players = CalendarUser.objects.filter(
        team__in=event.tags.all()
    ).select_related('team').order_by('name')
    if calendar_user:
        team_players = team_players.exclude(id=calendar_user.id)

    all_users = CalendarUser.objects.select_related('team').order_by('name')
    if calendar_user:
        all_users = all_users.exclude(id=calendar_user.id)

    other_players_data = [
        {
            'id': p.id,
            'label': f"{p.name} ({p.team.name})",
            'status': rsvp_status_map.get(p.id, ''),
        }
        for p in team_players
    ]
    all_users_data = [
        {
            'id': p.id,
            'label': f"{p.name} ({p.team.name})",
            'status': rsvp_status_map.get(p.id, ''),
        }
        for p in all_users
    ]
    guests_data = {g['name']: g['status'] for g in guests}

    tags = Tag.objects.all()
    is_admin = request.user.is_authenticated and request.user.is_staff

    context = {
        'event': event,
        'occurrence_date': occurrence_date,
        'user_prefs': user_prefs,
        'user_rsvp': user_rsvp,
        'rsvps_by_status': rsvps_by_status,
        'is_cancelled': is_cancelled,
        'cancel_reason': cancel_reason,
        'start_time': start_time,
        'end_time': end_time,
        'start_time_str': start_time.strftime('%H:%M'),
        'end_time_str': end_time.strftime('%H:%M') if end_time else '',
        'default_start_time_str': event.start_time.strftime('%H:%M'),
        'default_end_time_str': event.end_time.strftime('%H:%M') if event.end_time else '',
        'time_changed': time_changed,
        'max_participants': event.max_participants,
        'tags': tags,
        'is_admin': is_admin,
        'guests_by_status': guests_by_status,
        'all_guests': guests,
        'team_players': team_players,
        'other_players_data': other_players_data,
        'all_users_data': all_users_data,
        'guests_data': guests_data,
    }
    return render(request, 'calendar_app/event_detail.html', context)


@require_POST
def rsvp(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    user_id = request.POST.get('user_id', '').strip()
    status = request.POST.get('status', 'maybe')
    comment = request.POST.get('comment', '').strip()
    occurrence_date_str = request.POST.get('occurrence_date', '')

    if not user_id:
        return JsonResponse({'error': 'User ID is required'}, status=400)

    try:
        calendar_user = CalendarUser.objects.get(id=int(user_id))
    except (CalendarUser.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Invalid user'}, status=400)

    if not occurrence_date_str:
        occurrence_date = event.date
    else:
        try:
            occurrence_date = datetime.strptime(occurrence_date_str, '%Y-%m-%d').date()
        except ValueError:
            occurrence_date = event.date

    if status == 'remove':
        existing_rsvp = RSVP.objects.filter(
            event=event,
            occurrence_date=occurrence_date,
            user=calendar_user
        ).first()
        was_coming = existing_rsvp and existing_rsvp.status == 'coming'

        RSVP.objects.filter(
            event=event,
            occurrence_date=occurrence_date,
            user=calendar_user
        ).delete()

        if event.max_participants and was_coming:
            coming_rsvps = list(RSVP.objects.filter(
                event=event,
                occurrence_date=occurrence_date,
                status='coming'
            ).select_related('user').order_by('status_updated_at'))

            if len(coming_rsvps) > event.max_participants:
                r = coming_rsvps[event.max_participants]
                notify_waitlist_user(r, event, occurrence_date)

        return JsonResponse({'success': True, 'removed': True})

    valid_statuses = [choice[0] for choice in RSVP.STATUS_CHOICES]
    if status not in valid_statuses:
        return JsonResponse({'error': 'Invalid status'}, status=400)

    existing_rsvp = RSVP.objects.filter(
        event=event,
        occurrence_date=occurrence_date,
        user=calendar_user
    ).first()
    old_status = existing_rsvp.status if existing_rsvp else None

    defaults = {
        'status': status,
        'comment': comment,
    }
    if old_status != status:
        defaults['status_updated_at'] = timezone.now()

    rsvp_obj, created = RSVP.objects.update_or_create(
        event=event,
        occurrence_date=occurrence_date,
        user=calendar_user,
        defaults=defaults
    )

    if event.max_participants and old_status == 'coming' and status != 'coming':
        coming_rsvps = list(RSVP.objects.filter(
            event=event,
            occurrence_date=occurrence_date,
            status='coming'
        ).select_related('user').order_by('status_updated_at'))

        if len(coming_rsvps) > event.max_participants:
            r = coming_rsvps[event.max_participants]
            notify_waitlist_user(r, event, occurrence_date)

    response = JsonResponse({
        'success': True,
        'status': rsvp_obj.get_status_display(),
        'status_code': rsvp_obj.status,
        'comment': rsvp_obj.comment
    })

    logged_in_id = request.COOKIES.get('calendar_user_id', '')
    if logged_in_id and str(calendar_user.id) == str(logged_in_id):
        response.set_cookie(
            'calendar_user_id', calendar_user.id,
            max_age=365*24*60*60, path=get_cookie_path(),
            secure=_is_secure(), samesite='Lax'
        )

    return response


@require_POST
def guest_rsvp(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    name = request.POST.get('guest_name', '').strip()
    status = request.POST.get('status', 'maybe')
    occurrence_date_str = request.POST.get('occurrence_date', '')

    name = sanitize_guest_name(name)
    if not name:
        return JsonResponse({'error': 'Guest name is required'}, status=400)

    if len(name) > 100:
        return JsonResponse({'error': 'Guest name must be 100 characters or less'}, status=400)

    valid_statuses = [choice[0] for choice in RSVP.STATUS_CHOICES]
    if status not in valid_statuses:
        return JsonResponse({'error': 'Invalid status'}, status=400)

    if not occurrence_date_str:
        occurrence_date = event.date
    else:
        try:
            occurrence_date = datetime.strptime(occurrence_date_str, '%Y-%m-%d').date()
        except ValueError:
            occurrence_date = event.date

    guests = get_guests(event, occurrence_date)

    if request.POST.get('action') == 'remove':
        guests = [g for g in guests if g.get('name') != name]
        set_guests(event, occurrence_date, guests)
        return JsonResponse({'success': True, 'removed': True})

    existing = [g for g in guests if g.get('name') == name]
    if existing:
        existing[0]['status'] = status
    else:
        guests.append({'name': name, 'status': status})

    set_guests(event, occurrence_date, guests)

    return JsonResponse({'success': True, 'status': status, 'name': name})


@require_POST
def login_user(request):
    name = request.POST.get('name', '').strip()
    team_id = request.POST.get('team_id', '').strip()

    if not name:
        return JsonResponse({'error': 'Name is required'}, status=400)

    if not team_id:
        return JsonResponse({'error': 'Team is required'}, status=400)

    try:
        team = Tag.objects.get(id=int(team_id))
    except (Tag.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Invalid team'}, status=400)

    current_language = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, 'en')

    calendar_user, created = CalendarUser.objects.get_or_create(
        name=name,
        team=team,
        defaults={'language': current_language}
    )

    response = JsonResponse({
        'success': True,
        'user_id': calendar_user.id,
        'name': calendar_user.name,
        'team': calendar_user.team.name,
        'ntfy_topic': calendar_user.ntfy_topic,
        'language': calendar_user.language,
        'created': created,
    })

    cookie_path = get_cookie_path()
    cookie_kwargs = {
        'max_age': 365*24*60*60,
        'path': cookie_path,
        'secure': _is_secure(),
        'samesite': 'Lax',
    }
    response.set_cookie('calendar_user_id', calendar_user.id, **cookie_kwargs)

    if calendar_user.language:
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, calendar_user.language, **cookie_kwargs)

    return response


@require_POST
def update_user_settings(request):
    user_id = request.COOKIES.get('calendar_user_id', '')

    if not user_id:
        return JsonResponse({'error': 'Not logged in'}, status=400)

    try:
        calendar_user = CalendarUser.objects.get(id=int(user_id))
    except (CalendarUser.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Invalid user'}, status=400)

    if 'ntfy_topic' in request.POST:
        try:
            calendar_user.ntfy_topic = validate_ntfy_topic(request.POST.get('ntfy_topic', '').strip())
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)
    if 'language' in request.POST:
        calendar_user.language = request.POST.get('language', '').strip()

    calendar_user.save()

    return JsonResponse({
        'success': True,
        'ntfy_topic': calendar_user.ntfy_topic,
        'language': calendar_user.language,
    })


@require_POST
def save_preferences(request):
    preferred_tags = request.POST.get('preferred_tags', '')

    response = JsonResponse({'success': True})
    cookie_path = get_cookie_path()

    if preferred_tags is not None:
        response.set_cookie(
            'preferred_tags', preferred_tags,
            max_age=365*24*60*60, path=cookie_path,
            secure=_is_secure(), samesite='Lax'
        )

    return response


def admin_wrapper(request):
    return render(request, 'calendar_app/admin_wrapper.html')


def upcoming_events(request):
    today = timezone.now().date()
    end_date = today + timedelta(days=60)

    user_prefs = get_user_preferences(request)
    tag_filter_param = request.GET.get('tags', '')

    if tag_filter_param:
        active_tags = [t.strip() for t in tag_filter_param.split(',') if t.strip()]
    else:
        active_tags = user_prefs['preferred_tags']

    events = Event.objects.all().prefetch_related('tags', 'occurrence_details')

    non_recurring_filter = Q(date__range=(today, end_date), recurrence=None)
    recurring_filter = Q(recurrence__isnull=False)
    events = events.filter(non_recurring_filter | recurring_filter)

    if active_tags:
        events = events.filter(Q(tags__name__in=active_tags) | Q(tags__isnull=True)).distinct()

    calendar_user = user_prefs.get('calendar_user')
    events_list = list(events)
    rsvp_data = _prefetch_rsvps(events_list, calendar_user)

    all_occurrences = []
    for event in events_list:
        occurrences = get_event_occurrences(
            event, today, end_date, calendar_user,
            rsvp_data=rsvp_data.get(event.id)
        )
        all_occurrences.extend(occurrences)

    all_occurrences.sort(key=lambda x: (x['date'], x['start_time']))
    all_occurrences = all_occurrences[:20]

    tags = Tag.objects.all()
    user_prefs['preferred_tags'] = active_tags

    context = {
        'events': all_occurrences,
        'tags': tags,
        'user_prefs': user_prefs,
        'tag_filter': ','.join(active_tags) if active_tags else '',
    }
    return render(request, 'calendar_app/upcoming.html', context)


@require_POST
def update_occurrence(request, event_id):
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    event = get_object_or_404(Event, pk=event_id)

    occurrence_date_str = request.POST.get('occurrence_date', '')
    try:
        occurrence_date = datetime.strptime(occurrence_date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    cancelled = request.POST.get('cancelled') == 'true'
    reason = request.POST.get('reason', '').strip()
    start_time_str = request.POST.get('start_time', '').strip()
    end_time_str = request.POST.get('end_time', '').strip()

    start_time = None
    end_time = None

    if start_time_str:
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
        except ValueError:
            return JsonResponse({'error': 'Invalid start time'}, status=400)

    if end_time_str:
        try:
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
        except ValueError:
            return JsonResponse({'error': 'Invalid end time'}, status=400)

    old_cancelled = False
    old_reason = ''
    old_start_time = None
    old_end_time = None

    try:
        old_details = OccurrenceDetails.objects.get(event=event, occurrence_date=occurrence_date)
        old_cancelled = old_details.cancelled
        old_reason = old_details.reason
        old_start_time = old_details.override_start_time
        old_end_time = old_details.override_end_time
    except OccurrenceDetails.DoesNotExist:
        pass

    time_changed_flag = False
    if start_time_str or end_time_str:
        time_changed_flag = (start_time != old_start_time or end_time != old_end_time)

    defaults = {
        'cancelled': cancelled,
        'reason': reason,
    }
    if start_time_str:
        defaults['override_start_time'] = start_time
    if end_time_str:
        defaults['override_end_time'] = end_time

    details, created = OccurrenceDetails.objects.update_or_create(
        event=event,
        occurrence_date=occurrence_date,
        defaults=defaults
    )

    if cancelled and not old_cancelled:
        notify_rsvps_event_change(event, occurrence_date, 'cancelled', reason)
    elif not cancelled and old_cancelled:
        notify_rsvps_event_change(event, occurrence_date, 'uncancelled')
    elif reason and reason != old_reason:
        if cancelled:
            notify_rsvps_event_change(event, occurrence_date, 'cancelled', reason)
        else:
            notify_rsvps_event_change(event, occurrence_date, 'notice', reason)
    elif time_changed_flag:
        if not cancelled:
            notify_rsvps_event_change(event, occurrence_date, 'time_changed', start_time=start_time, end_time=end_time)

    return JsonResponse({
        'success': True,
        'cancelled': details.cancelled,
        'reason': details.reason,
        'start_time': details.override_start_time.isoformat() if details.override_start_time else None,
        'end_time': details.override_end_time.isoformat() if details.override_end_time else None,
    })
