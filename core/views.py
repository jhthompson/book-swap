import os

from formtools.wizard.views import SessionWizardView

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator
from django.http import HttpRequest
from django.shortcuts import redirect, render

from core.forms import (
    AcceptSwapForm,
    BookListingDetailsForm,
    BookListingForm,
    BookListingISBNForm,
    BookListingSelectionForm,
    BookListingSelectionFormSet,
)
from core.models import BookListing, BookSwap, BookSwapEvent


def index(request):
    context = {}

    if request.user.is_authenticated:
        context["listings"] = BookListing.objects.exclude(owner=request.user).order_by(
            "-created_at"
        )
    else:
        context["listings"] = BookListing.objects.all().order_by("-created_at")

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
def delete_listing(request, id):
    try:
        listing = BookListing.objects.get(id=id, owner=request.user)
    except BookListing.DoesNotExist:
        return redirect("listings")

    if request.method == "POST":
        listing.delete()
        messages.success(request, "Listing deleted successfully.")
        return redirect("listings")

    form = forms.Form()  # Empty form for CSRF token

    return render(
        request,
        "core/delete_listing.html",
        {"listing": listing, "form": form},
    )


class BookListingWizardView(LoginRequiredMixin, SessionWizardView):
    template_name = "core/book_listing_wizard.html"

    form_list = [
        ("isbn", BookListingISBNForm),
        ("details", BookListingDetailsForm),
    ]

    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "book_listing_wizard_cover_photos")
    )

    def process_step(self, form):
        """Called after each step's form is validated"""
        if self.steps.current == "isbn":
            isbn = form.cleaned_data["isbn"]
            book_data = self.lookup_book_by_isbn(isbn)

            if book_data:
                # Store the API data to pre-populate next step
                self.storage.extra_data["api_book_data"] = book_data
                self.storage.extra_data["api_lookup_success"] = True
                messages.success(
                    self.request,
                    "Found book details from ISBN - please double check they are correct.",  # noqa: E501
                )
            else:
                self.storage.extra_data["api_lookup_success"] = False

        return super().process_step(form)

    def get_form_initial(self, step):
        """Pre-populate forms with data"""
        initial = super().get_form_initial(step)

        if step == "details" and self.storage.extra_data.get("api_lookup_success"):
            api_data = self.storage.extra_data.get("api_book_data", {})
            initial.update(
                {
                    "title": api_data.get("title", ""),
                    "author": api_data.get("author", ""),
                    "publisher": api_data.get("publisher", ""),
                    # ... map other fields
                }
            )

        return initial

    def lookup_book_by_isbn(self, isbn):
        if not isbn:
            return None

        try:
            import json
            import urllib.request

            url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())

            if data.get("totalItems", 0) > 0:
                book = data["items"][0]["volumeInfo"]
                return {
                    "title": book.get("title", ""),
                    "author": ", ".join(book.get("authors", [])),
                    # ... extract other fields if needed
                }
        except Exception:
            # Log the error
            pass
        return None

    def done(self, form_list, **kwargs):
        """Process final form submission"""
        # Combine data from both steps
        isbn_data = form_list[0].cleaned_data
        details_data = form_list[1].cleaned_data

        # Create your book listing object here
        listing = BookListing.objects.create(
            isbn=isbn_data["isbn"],
            title=details_data["title"],
            author=details_data["author"],
            cover_photo=details_data["cover_photo"],
            owner=self.request.user,
        )

        return redirect("listing", listing.id)


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

    queryset = BookListing.objects.all()

    if query:
        queryset = queryset.filter(title__icontains=query) | queryset.filter(
            author__icontains=query
        )

    if request.user.is_authenticated:
        queryset = queryset.exclude(owner=request.user)

    queryset = queryset.order_by("-created_at")

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context["page_obj"] = page_obj

    return render(request, "core/search.html", context)
