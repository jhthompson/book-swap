from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from core.models import BookListing


def index(request):
    context = {}

    return render(request, "core/index.html", context)


@login_required
def listings(request):
    context = {}

    context["listings"] = BookListing.objects.filter(owner=request.user)

    return render(request, "core/listings.html", context)
