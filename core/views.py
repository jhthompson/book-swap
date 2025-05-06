from django import forms
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from core.forms import (
    BookListingForm,
    BookListingSelectionForm,
    BookListingSelectionFormSet,
)
from core.models import BookListing, BookSwap


def index(request):
    context = {}

    if request.user.is_authenticated:
        context["listings"] = BookListing.objects.exclude(owner=request.user)

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


@login_required
def swaps(request):
    context = {}

    context["swaps_by_you"] = BookSwap.objects.filter(proposed_by=request.user)
    context["swaps_to_you"] = BookSwap.objects.filter(proposed_to=request.user)

    return render(request, "core/swaps.html", context)


@login_required
def new_swap(request: HttpRequest):
    if request.method == "POST":
        formset = forms.formset_factory(BookListingSelectionForm)(request.POST)

        if formset.is_valid():
            print(formset.cleaned_data)
            requested_book_listings = formset.cleaned_data[0]["book_listings"]
            offered_book_listings = formset.cleaned_data[1]["book_listings"]

            proposed_to = requested_book_listings[0].owner
            proposed_by = offered_book_listings[0].owner

            book_swap = BookSwap.objects.create(
                proposed_by=proposed_by,
                proposed_to=proposed_to,
            )
            book_swap.offered_books.set(offered_book_listings)
            book_swap.requested_books.set(requested_book_listings)
            book_swap.save()

            return redirect("swap", book_swap.id)

    context = {}

    proposed_by = request.user
    proposed_to_id = request.GET.get("proposed_to")
    proposed_to = User.objects.get(id=proposed_to_id)
    requested_book_listing_ids = request.GET.getlist("requested_book_listing_ids")
    requested_book_listings = BookListing.objects.filter(
        id__in=requested_book_listing_ids, owner=proposed_to
    )

    context["proposed_by"] = proposed_by
    context["proposed_to"] = proposed_to

    BookListingSelectionFormSetFactory = forms.formset_factory(
        form=BookListingSelectionForm,
        formset=BookListingSelectionFormSet,
        extra=0,
        min_num=2,
        max_num=2,
    )
    context["formset"] = BookListingSelectionFormSetFactory(
        owners=[proposed_to, proposed_by],
        initial=[
            {"book_listings": requested_book_listings},
            {"book_listings": []},
        ],
    )

    return render(request, "core/new_swap.html", context)


@login_required
def swap(request: HttpRequest, id: int):
    context = {}

    try:
        swap = BookSwap.objects.get(id=id)
        context["swap"] = swap

        if swap.proposed_by != request.user and swap.proposed_to != request.user:
            raise BookSwap.DoesNotExist

    except BookSwap.DoesNotExist:
        return redirect("index")

    return render(request, "core/swap.html", context)
