from django import template

register = template.Library()

@register.filter
def month_name(month_number):
    """
    Template filter that returns the name of a month from its number.
    Usage: {{ 5|month_name }} will output "May"
    """
    import calendar
    try:
        return calendar.month_name[int(month_number)]
    except (IndexError, ValueError):
        return ""
