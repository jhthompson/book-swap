from django.db.models import Q
from django.http import HttpRequest

from core.models import BookSwap


def open_swaps_count(request: HttpRequest) -> dict:
    context = {}

    if request.user.is_authenticated:
        context["open_swaps_count"] = BookSwap.objects.filter(
            Q(proposed_by=request.user) | Q(proposed_to=request.user),
            Q(status=BookSwap.Status.PROPOSED) | Q(status=BookSwap.Status.ACCEPTED),
        ).count()

    return context
