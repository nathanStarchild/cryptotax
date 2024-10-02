from django import template

register = template.Library()

@register.filter
def truncateHash(hash):
    return f"{hash[:7]}...{hash[-4:]}"