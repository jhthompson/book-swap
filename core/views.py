import logging

import zxingcpp
from PIL import Image

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.gis.geos import Polygon
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import (
    BookListingSelectionForm,
    BookListingSelectionFormSet,
    EditProfileForm,
    IsbnForm,
    NewBookListingForm,
)
from core.models import BookListing, BookSwap, BookSwapEvent, Genre, OpenLibraryAuthor
from core.open_library import (
    get_book_details_from_openlibrary_search_results,
    search_openlibrary_by_isbn,
)

logger = logging.getLogger(__name__)


def index(request: HttpRequest):
    context = {}

    listings = BookListing.objects.filter(status=BookListing.Status.AVAILABLE).order_by(
        "-created_at"
    )

    if request.user.is_authenticated:
        listings = listings.exclude(owner=request.user)

    context["listings"] = listings

    return render(request, "core/index.html", context)


def profile(request: HttpRequest, id: int):
    context = {}
    context["profile_user"] = get_object_or_404(User, id=id)

    return render(request, "core/profile.html", context)


@login_required
def edit_profile(request: HttpRequest, id: int):
    context = {}

    editable_user = get_object_or_404(User, id=id)

    if request.user != editable_user:
        raise PermissionDenied()

    if request.method == "POST":
        form = EditProfileForm(request.POST)

        if form.is_valid():
            new_username = form.cleaned_data.get("username")
            new_city = form.cleaned_data.get("city")
            new_location = form.cleaned_data.get("location")

            if (
                User.objects.exclude(id=editable_user.id)
                .filter(username=new_username)
                .exists()
            ):
                form.add_error("username", "This username is already taken.")
            else:
                editable_user.username = new_username
                editable_user.save()

                editable_user.userprofile.city = new_city
                editable_user.userprofile.location = new_location
                editable_user.userprofile.save()

                messages.success(request, "Profile updated.")
                return redirect("profile", id=editable_user.id)
    else:
        form = EditProfileForm(
            initial={
                "username": editable_user.username,
                "city": editable_user.userprofile.city,
                "location": editable_user.userprofile.location,
            }
        )

    context["form"] = form

    return render(request, "core/edit_profile.html", context)


@login_required
def listings(request: HttpRequest):
    context = {}

    context["listings"] = BookListing.objects.filter(
        owner=request.user,
        status__in=[BookListing.Status.AVAILABLE, BookListing.Status.PENDING],
    ).order_by("-created_at")

    return render(request, "core/listings.html", context)


@login_required
def new_listing_isbn_prompt(request: HttpRequest):
    if request.method == "POST":
        form = IsbnForm(request.POST, request.FILES)

        if form.is_valid():
            form_isbn = form.cleaned_data.get("isbn")
            form_barcode = form.cleaned_data.get("barcode")

            isbn = form_isbn or extract_isbn_from_barcode_image(form_barcode)

            if isbn:
                return redirect("new_listing_from_isbn", isbn=isbn)
            else:
                messages.warning(
                    request,
                    "Could not find a valid ISBN. Please enter book details manually.",
                )
                return redirect("new_listing")

    else:
        form = IsbnForm()

    return render(request, "core/new_listing_isbn_prompt.html", {"form": form})


def extract_isbn_from_barcode_image(barcode) -> str | None:
    try:
        image = Image.open(barcode)
        results = zxingcpp.read_barcodes(image)
    except Exception:
        logger.exception("Error reading barcode image")
        return None

    for result in results:
        if result.format == zxingcpp.BarcodeFormat.EAN13:
            return result.text

    return None


@login_required
def new_listing_from_isbn(request: HttpRequest, isbn: str):
    if request.method == "POST":
        form = NewBookListingForm(request.POST, request.FILES)

        if form.is_valid():
            title = form.cleaned_data.get("title")
            isbn = form.cleaned_data.get("isbn")
            authors = form.cleaned_data.get("authors")
            cover = request.FILES["cover"]
            genre_names = form.cleaned_data.get("genres", [])

            openlibrary_edition_id = form.cleaned_data.get("openlibrary_edition_id", "")
            openlibrary_work_id = form.cleaned_data.get("openlibrary_work_id", "")
            openlibrary_author_ids = form.cleaned_data.get(
                "openlibrary_author_ids", ""
            ).split(",")
            openlibrary_author_names = form.cleaned_data.get(
                "openlibrary_author_names", ""
            ).split(",")

            # genres
            genres = Genre.objects.filter(name__in=genre_names)

            # OpenLibrary Authors
            openlibrary_authors = []
            for ol_author_id, ol_author_name in zip(
                openlibrary_author_ids, openlibrary_author_names, strict=True
            ):
                openlibrary_author, created = OpenLibraryAuthor.objects.get_or_create(
                    openlibrary_author_id=ol_author_id
                )
                openlibrary_author.name = ol_author_name
                openlibrary_author.save()
                openlibrary_authors.append(openlibrary_author)

            # BookListing
            listing = BookListing.objects.create(
                title=title,
                isbn=isbn,
                authors=authors,
                cover=cover,
                owner=request.user,
                openlibrary_edition_id=openlibrary_edition_id,
                openlibrary_work_id=openlibrary_work_id,
            )
            listing.openlibrary_authors.set(openlibrary_authors)
            listing.genres.set(genres)
            listing.save()

            messages.success(request, "Book listing created.")
            return redirect("listing", id=listing.id)

    else:
        ol_search_data = search_openlibrary_by_isbn(isbn)

        if ol_search_data.get("numFound", 0) == 0:
            messages.warning(
                request,
                "Could not find book details on OpenLibrary. Please enter details manually.",  # noqa: E501
            )
        else:
            messages.success(request, "Populated book details from OpenLibrary.")

        ol_book_details = get_book_details_from_openlibrary_search_results(
            ol_search_data
        )

        form = NewBookListingForm(
            initial={
                # Main fields, pre-filled if OpenLibrary lookup was successful
                "isbn": isbn,
                "title": ol_book_details.get("title", ""),
                "authors": ", ".join(ol_book_details.get("author_names", [])),
                # Hidden fields for OpenLibrary data
                "openlibrary_edition_title": ol_book_details.get("title", ""),
                "openlibrary_edition_id": ol_book_details.get("edition_id", ""),
                "openlibrary_work_id": ol_book_details.get("work_id", ""),
                "openlibrary_author_names": ",".join(
                    ol_book_details.get("author_names", [])
                ),
                "openlibrary_author_ids": ",".join(
                    ol_book_details.get("author_ids", [])
                ),
            }
        )

    return render(
        request,
        "core/new_listing.html",
        {
            "form": form,
        },
    )


@login_required
def new_listing(request: HttpRequest):
    if request.method == "POST":
        form = NewBookListingForm(request.POST, request.FILES)

        if form.is_valid():
            title = form.cleaned_data.get("title")
            isbn = form.cleaned_data.get("isbn")
            authors = form.cleaned_data.get("authors")
            cover = request.FILES["cover"]

            listing = BookListing.objects.create(
                title=title,
                isbn=isbn,
                authors=authors,
                cover=cover,
                owner=request.user,
            )
            listing.save()

            messages.success(request, "Book listing created.")
            return redirect("listing", id=listing.id)

    else:
        form = NewBookListingForm()

    return render(
        request,
        "core/new_listing.html",
        {
            "form": form,
        },
    )


@login_required
def listing(request: HttpRequest, id: int):
    context = {}

    try:
        context["listing"] = BookListing.objects.get(
            id=id,
            owner=request.user,
            status__in=[BookListing.Status.AVAILABLE, BookListing.Status.PENDING],
        )
    except BookListing.DoesNotExist:
        return redirect("listings")

    return render(request, "core/listing.html", context)


@login_required
def delete_listing(request: HttpRequest, id: int):
    try:
        listing = BookListing.objects.get(
            id=id,
            owner=request.user,
            status__in=[BookListing.Status.AVAILABLE, BookListing.Status.PENDING],
        )
    except BookListing.DoesNotExist:
        return redirect("listings")

    if request.method == "POST":
        if listing.remove():
            messages.success(request, "Listing deleted.")
            return redirect("listings")
        else:
            messages.error(request, "Something went wrong.")
            return redirect("listings")

    return render(
        request,
        "core/delete_listing.html",
        {
            "listing": listing,
        },
    )


@login_required
def swaps(request: HttpRequest):
    context = {}

    is_user_involved = Q(proposed_by=request.user) | Q(proposed_to=request.user)
    is_open = Q(status=BookSwap.Status.PROPOSED) | Q(status=BookSwap.Status.ACCEPTED)

    involved_pending_swaps = BookSwap.objects.filter(is_user_involved & is_open)
    involved_closed_swaps = BookSwap.objects.filter(is_user_involved & ~is_open)

    context["pending_swaps"] = involved_pending_swaps.order_by(
        "-created_at"
    ).prefetch_related(
        "requested_listings",
        "offered_listings",
        Prefetch(
            "events",
            queryset=BookSwapEvent.objects.order_by("-created_at").select_related(
                "user"
            ),
            to_attr="ordered_events",
        ),
    )

    context["closed_swaps"] = involved_closed_swaps.order_by(
        "-created_at"
    ).prefetch_related(
        "requested_listings",
        "offered_listings",
        Prefetch(
            "events",
            queryset=BookSwapEvent.objects.order_by("-created_at").select_related(
                "user"
            ),
            to_attr="ordered_events",
        ),
    )

    return render(request, "core/swaps.html", context)


@login_required
def new_swap(request: HttpRequest):
    proposed_by = request.user
    proposed_to_id = request.GET.get("proposed_to")
    proposed_to = User.objects.get(id=proposed_to_id)
    requested_book_listing_ids = request.GET.getlist("requested_book_listing_ids")
    requested_book_listings = BookListing.objects.filter(
        id__in=requested_book_listing_ids,
        owner=proposed_to,
        status=BookListing.Status.AVAILABLE,
    )

    if proposed_by == proposed_to:
        messages.error(request, "You cannot propose a swap to yourself.")
        return redirect("index")

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
            book_swap.offered_listings.set(offered_book_listings)
            book_swap.requested_listings.set(requested_book_listings)
            book_swap.save()

            BookSwapEvent.objects.create(
                swap=book_swap,
                user=proposed_by,
                type=BookSwapEvent.Type.PROPOSE,
            )

            book_swap.notify(request, BookSwapEvent.Type.PROPOSE)

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

    if request.user == swap.proposed_by:
        context["your_listings"] = swap.offered_listings.all()
        context["their_listings"] = swap.requested_listings.all()
        context["them"] = swap.proposed_to
    elif request.user == swap.proposed_to:
        context["your_listings"] = swap.requested_listings.all()
        context["their_listings"] = swap.offered_listings.all()
        context["them"] = swap.proposed_by

    context["you"] = request.user
    context["swap_id"] = swap.id

    return render(request, "core/swap.html", context)


@login_required
def swap_messages(request: HttpRequest, id: int):
    try:
        swap = BookSwap.objects.get(id=id, status=BookSwap.Status.ACCEPTED)
        if swap.proposed_by != request.user and swap.proposed_to != request.user:
            raise BookSwap.DoesNotExist
    except BookSwap.DoesNotExist:
        messages.error(request, "Something went wrong.")
        return redirect("index")

    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        if content:
            from core.models import BookSwapMessage

            BookSwapMessage.objects.create(
                swap=swap,
                sender=request.user,
                content=content,
            )
        else:
            messages.error(request, "Message cannot be empty.")

    return redirect("swap", id=swap.id)


@login_required
def cancel_swap(request: HttpRequest, id: int):
    try:
        swap = BookSwap.objects.get(id=id, proposed_by=request.user)
    except BookSwap.DoesNotExist:
        return redirect("index")

    if request.method == "POST":
        if swap.cancel(request.user):
            messages.success(request, "Swap cancelled.")
            return redirect("swaps")
        else:
            messages.error(request, "Something went wrong.")
            return redirect("swap", swap.id)

    return render(request, "core/cancel_swap.html", context={"swap": swap})


@login_required
def accept_swap(request: HttpRequest, id: int):
    try:
        swap = BookSwap.objects.get(id=id, proposed_to=request.user)
    except BookSwap.DoesNotExist:
        return redirect("index")

    if request.method == "POST":
        if swap.accept(user=request.user):
            swap.notify(request, BookSwapEvent.Type.ACCEPT)

            return redirect("swap", swap.id)
        else:
            raise PermissionDenied()

    return render(
        request,
        "core/accept_swap.html",
        context={"swap": swap},
    )


@login_required
def complete_swap(request: HttpRequest, id: int):
    try:
        swap = BookSwap.objects.get(id=id, proposed_by=request.user)
    except BookSwap.DoesNotExist:
        return redirect("index")

    if request.method == "POST":
        if swap.complete(user=request.user):
            return redirect("swap", swap.id)
        else:
            raise PermissionDenied()

    return render(
        request,
        "core/complete_swap.html",
        context={"swap": swap},
    )


@login_required
def decline_swap(request: HttpRequest, id: int):
    try:
        swap = BookSwap.objects.get(id=id, proposed_to=request.user)
    except BookSwap.DoesNotExist:
        return redirect("index")

    if request.method == "POST":
        form = forms.Form(request.POST)

        if form.is_valid() and swap.decline(user=request.user):
            messages.success(request, "Swap declined.")
            return redirect("swaps")
        else:
            messages.error(request, "Something went wrong.")
            return redirect("swap", swap.id)

    return render(request, "core/decline_swap.html", context={"swap": swap})


def search(request: HttpRequest):
    query = request.GET.get("query", "")
    context = {"query": query}

    queryset = BookListing.objects.filter(status=BookListing.Status.AVAILABLE)

    if query:
        queryset = queryset.filter(title__icontains=query) | queryset.filter(
            authors__icontains=query
        )

    if request.user.is_authenticated:
        queryset = queryset.exclude(owner=request.user)

    queryset = queryset.order_by("-created_at")

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context["page_obj"] = page_obj

    return render(request, "core/search.html", context)


def map_view(request: HttpRequest):
    return render(request, "core/map.html")


def book_listings_api(request: HttpRequest):
    try:
        north = float(request.GET["north"])
        south = float(request.GET["south"])
        east = float(request.GET["east"])
        west = float(request.GET["west"])
    except (KeyError, ValueError):
        return JsonResponse({"error": "Invalid bounds"}, status=400)

    bbox = Polygon.from_bbox((west, south, east, north))
    listings = BookListing.objects.filter(
        status=BookListing.Status.AVAILABLE, owner__userprofile__location__within=bbox
    )

    if request.user.is_authenticated:
        listings = listings.exclude(owner=request.user)

    results = [
        {
            "id": listing.id,
            "title": listing.title,
            "authors": listing.authors,
            "cover": listing.cover.url,
            "location": {
                "lat": listing.owner.userprofile.location.y,
                "lng": listing.owner.userprofile.location.x,
            },
            "owner": {
                "id": listing.owner.id,
                "username": listing.owner.username,
            },
        }
        for listing in listings.select_related("owner__userprofile")
    ]

    return JsonResponse({"results": results})


@staff_member_required
def approve_pending_listings(request):
    pending_listings = BookListing.objects.filter(
        status=BookListing.Status.PENDING
    ).order_by("created_at")

    if request.method == "POST":
        listing_id = request.GET.get("listing_id") or request.POST.get("listing_id")
        action = request.POST.get("action")

        try:
            listing = BookListing.objects.get(
                id=listing_id,
                status=BookListing.Status.PENDING,
            )
        except BookListing.DoesNotExist:
            return HttpResponseBadRequest(
                "Invalid listing ID or listing already approved."
            )

        if action == "approve":
            if listing.approve():
                messages.success(
                    request,
                    f"Listing '{listing.title}' has been approved (marked as AVAILABLE).",  # noqa: E501
                )
        elif action == "reject":
            if listing.remove():
                messages.success(
                    request,
                    f"Listing '{listing.title}' has been rejected (marked as REMOVED).",
                )
        else:
            return HttpResponseBadRequest("Invalid action.")

        return redirect("approve_pending_listings")

    return render(
        request,
        "core/approve_pending_listings.html",
        {"pending_listings": pending_listings},
    )
