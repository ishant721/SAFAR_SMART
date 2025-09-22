
from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css_class):
    if hasattr(field, 'as_widget'):
        return field.as_widget(attrs={'class': css_class})
    else:
        # If it's already rendered, return as is
        return field

@register.filter
def lookup(dictionary, key):
    """Custom filter to lookup dictionary values with dynamic keys"""
    if dictionary and key:
        return dictionary.get(key)
    return None
