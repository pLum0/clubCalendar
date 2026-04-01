from django import template
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

register = template.Library()


@register.filter
def human_readable_recurrence(recurrence_obj):
    if not recurrence_obj:
        return ""

    import recurrence as rec_module
    freq_map = {
        rec_module.YEARLY: _('Yearly'),
        rec_module.MONTHLY: _('Monthly'),
        rec_module.WEEKLY: _('Weekly'),
        rec_module.DAILY: _('Daily'),
    }

    human_parts = []
    rules = recurrence_obj.rrules if hasattr(recurrence_obj, 'rrules') else []

    for rule in rules:
        freq = freq_map.get(rule.freq, str(rule.freq))

        if rule.interval and rule.interval > 1:
            unit = _('year') if rule.freq == rec_module.YEARLY else \
                   _('month') if rule.freq == rec_module.MONTHLY else \
                   _('week') if rule.freq == rec_module.WEEKLY else \
                   _('day')
            human_parts.append(ngettext('Every %(interval)s %(unit)s', 'Every %(interval)s %(unit)s', rule.interval) % {
                'interval': rule.interval,
                'unit': unit
            })
        else:
            human_parts.append(freq)

        if rule.byday:
            day_map = {
                0: _('Monday'),
                1: _('Tuesday'),
                2: _('Wednesday'),
                3: _('Thursday'),
                4: _('Friday'),
                5: _('Saturday'),
                6: _('Sunday'),
            }
            days = []
            for d in rule.byday:
                if hasattr(d, 'weekday'):
                    days.append(day_map.get(d.weekday, str(d)))
                elif isinstance(d, str) and len(d) >= 2:
                    day_num = {'MO': 0, 'TU': 1, 'WE': 2, 'TH': 3, 'FR': 4, 'SA': 5, 'SU': 6}.get(d[:2].upper())
                    if day_num is not None:
                        days.append(day_map.get(day_num, str(d)))
                    else:
                        days.append(str(d))
                else:
                    days.append(str(d))
            days = [d for d in days if d is not None]
            if len(days) == 1:
                human_parts.append(_('on %(day)s') % {'day': days[0]})
            elif len(days) == 5 and all(d in days for d in [_('Monday'), _('Tuesday'), _('Wednesday'), _('Thursday'), _('Friday')]):
                human_parts.append(_("on weekdays"))
            elif len(days) == 2 and _('Saturday') in days and _('Sunday') in days:
                human_parts.append(_("on weekends"))
            else:
                human_parts.append(_('on %(days)s') % {'days': ', '.join(days)})

        if rule.bymonthday:
            days_str = ', '.join(str(d) for d in rule.bymonthday)
            human_parts.append(_('on day %(days)s of the month') % {'days': days_str})

        if rule.bymonth:
            from calendar import month_name
            months = [_(month_name[int(m)]) for m in rule.bymonth]
            human_parts.append(_('in %(months)s') % {'months': ', '.join(months)})

    exdates = recurrence_obj.exdates if hasattr(recurrence_obj, 'exdates') else []
    if exdates:
        human_parts.append(_("(with some dates excluded)"))

    return ' '.join(human_parts) if human_parts else str(recurrence_obj)
