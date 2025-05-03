from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from core.forms import CreateListingForm
from core.models import BookListing


def index(request):
    context = {}

    return render(request, "core/index.html", context)


@login_required
def listings(request):
    context = {}

    context["listings"] = BookListing.objects.filter(owner=request.user)

    return render(request, "core/listings.html", context)


@login_required
def new_listing(request):
    if request.method == "POST":
        form = CreateListingForm(request.POST, request.FILES)

        if form.is_valid():
            listing = BookListing(
                title=form.cleaned_data["title"],
                cover_photo=form.cleaned_data["cover_photo"],
                isbn=form.cleaned_data["isbn"],
                owner=request.user,
            )
            listing.full_clean()
            listing.save()
            return redirect("listings")

    else:
        form = CreateListingForm()

    return render(request, "core/new_listing.html", {"form": form})
