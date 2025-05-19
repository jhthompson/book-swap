from django import forms
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

from core.forms import (
    AcceptSwapForm,
    BookListingForm,
    BookListingSelectionForm,
    BookListingSelectionFormSet,
)
from core.models import BookListing, BookSwap, BookSwapEvent


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
    proposed_by = request.user
    proposed_to_id = request.GET.get("proposed_to")
    proposed_to = User.objects.get(id=proposed_to_id)
    requested_book_listing_ids = request.GET.getlist("requested_book_listing_ids")
    requested_book_listings = BookListing.objects.filter(
        id__in=requested_book_listing_ids, owner=proposed_to
    )

    if request.method == "POST":
        FormSetFactory = forms.formset_factory(
            form=BookListingSelectionForm, formset=BookListingSelectionFormSet
        )

        formset = FormSetFactory(
            request.POST,
            owners=[proposed_to, proposed_by],
        )

        if formset.is_valid():
            requested_book_listings = formset.cleaned_data[0]["book_listings"]
            offered_book_listings = formset.cleaned_data[1]["book_listings"]

            book_swap = BookSwap.objects.create(
                proposed_by=proposed_by,
                proposed_to=proposed_to,
            )
            book_swap.offered_books.set(offered_book_listings)
            book_swap.requested_books.set(requested_book_listings)
            book_swap.save()

            BookSwapEvent.objects.create(
                swap=book_swap,
                user=proposed_by,
                type=BookSwapEvent.Type.PROPOSE,
            )

            return redirect("swap", book_swap.id)
    else:
        BookListingSelectionFormSetFactory = forms.formset_factory(
            form=BookListingSelectionForm,
            formset=BookListingSelectionFormSet,
            extra=0,
            min_num=2,
            max_num=2,
        )
        formset = BookListingSelectionFormSetFactory(
            owners=[proposed_to, proposed_by],
            initial=[
                {"book_listings": requested_book_listings},
                {"book_listings": []},
            ],
        )

    context = {}
    context["formset"] = formset
    context["proposed_to"] = proposed_to

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


@login_required
def cancel_swap(request: HttpRequest, id: int):
    try:
        swap = BookSwap.objects.get(id=id)
        if swap.proposed_by != request.user:
            raise BookSwap.DoesNotExist()

        if swap.cancel(request.user):
            return redirect("swap", swap.id)
    except BookSwap.DoesNotExist:
        return redirect("index")

    return render(request, "core/cancel_swap.html", context={"swap": swap})


@login_required
def accept_swap(request: HttpRequest, id: int):
    try:
        swap = BookSwap.objects.get(id=id)
        if swap.proposed_to != request.user:
            raise BookSwap.DoesNotExist
    except BookSwap.DoesNotExist:
        return redirect("index")

    if request.method == "POST":
        form = AcceptSwapForm(request.POST)

        if form.is_valid():
            message = form.cleaned_data["message"]

            if swap.accept(user=request.user, message=message):
                return redirect("swaps")
            else:
                raise PermissionDenied()

    return render(
        request,
        "core/accept_swap.html",
        context={"swap": swap, "form": AcceptSwapForm()},
    )


@login_required
def decline_swap(request: HttpRequest, id: int):
    try:
        swap = BookSwap.objects.get(id=id)
        if swap.proposed_to != request.user:
            raise BookSwap.DoesNotExist
    except BookSwap.DoesNotExist:
        return redirect("index")

    return render(request, "core/decline_swap.html", context={"swap": swap})
