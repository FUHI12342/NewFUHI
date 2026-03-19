"""Shared admin helpers."""
from ..models import Staff


def _is_owner_or_super(request):
    """superuser または is_owner の場合 True"""
    if request.user.is_superuser:
        return True
    try:
        return request.user.staff.is_owner
    except Staff.DoesNotExist:
        return False
