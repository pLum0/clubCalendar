from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    try:
        return dictionary[key]
    except (KeyError, TypeError):
        return None
