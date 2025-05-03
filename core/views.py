from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from core.forms import BookListingForm
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
def listing(request, id):
    context = {}

    try:
        context["listing"] = BookListing.objects.get(id=id, owner=request.user)
    except BookListing.DoesNotExist:
        return redirect("listings")

    return render(request, "core/listing.html", context)


@login_required
def edit_listing(request, id):
    try:
        listing = BookListing.objects.get(id=id, owner=request.user)
    except BookListing.DoesNotExist:
        return redirect("listings")

    if request.method == "POST":
        form = BookListingForm(request.POST, request.FILES, instance=listing)

        if form.is_valid():
            form.save()
            return redirect("listing", id=listing.id)

    else:
        form = BookListingForm(instance=listing)

    return render(request, "core/edit_listing.html", {"form": form})


@login_required
def new_listing(request):
    if request.method == "POST":
        form = BookListingForm(request.POST, request.FILES)

        if form.is_valid():
            listing: BookListing = form.save(commit=False)
            listing.owner = request.user
            listing.save()
            return redirect("listings")

    else:
        form = BookListingForm()

    return render(request, "core/new_listing.html", {"form": form})
