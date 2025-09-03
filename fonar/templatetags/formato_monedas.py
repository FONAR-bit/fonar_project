from django import template

register = template.Library()

@register.filter
def moneda(value):
    """
    Formatea un número en estilo moneda latino: $1.000.000
    """
    try:
        value = int(value)  # quitar decimales
        return "${:,.0f}".format(value).replace(",", ".")
    except (ValueError, TypeError):
        return value
