from decimal import Decimal
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _num(value):
    try:
        return Decimal(value or 0)
    except Exception:
        return Decimal(0)


@register.filter
def money(value):
    v = _num(value)
    return f"{v:,.2f} MAD"


@register.filter
def pct(value):
    try:
        return f"{float(value):.1f}%"
    except Exception:
        return "0.0%"


@register.filter
def phase_badge(phase):
    mapping = {
        'Incorporation': 'purple',
        'Tirage': 'blue',
        'Appareillage': 'amber',
        'Tableau': 'green',
    }
    cls = mapping.get(str(phase), 'gray')
    return mark_safe(f'<span class="badge badge-{cls}">{phase}</span>')


@register.filter
def status_badge(status):
    mapping = {
        'active': 'green',
        'completed': 'blue',
        'paused': 'amber',
        'cancelled': 'red',
    }
    cls = mapping.get(str(status).lower(), 'gray')
    return mark_safe(f'<span class="badge badge-{cls}">{status}</span>')


@register.filter
def direction_badge(direction):
    cls = 'green' if direction == 'IN' else 'red'
    return mark_safe(f'<span class="badge badge-{cls}">{direction}</span>')


@register.filter
def get_item(d, key):
    if not d:
        return None
    return d.get(key)


@register.filter
def progress_offset(value):
    try:
        v = max(0, min(100, float(value)))
    except Exception:
        v = 0
    return 314 - (314 * v / 100)
