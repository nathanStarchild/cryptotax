from django import template
from taxApp.models import Token

register = template.Library()

@register.filter
def get_token(address):
    try:
        token = Token.objects.get(address=address)
        return token.coin.name
    except Token.DoesNotExist:
        return address