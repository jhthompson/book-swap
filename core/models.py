import logging

from isbn_field import ISBNField

from django.contrib.auth.models import User
from django.contrib.gis.db import models as geo_models
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import models
from django.db.models import Q
from django.forms import ValidationError
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    city = models.CharField(max_length=100)
    location = geo_models.PointField()

    def __str__(self):
        return f"{self.user.username}'s Profile"


class Author(models.Model):
    name = models.CharField(max_length=255)
    openlibrary_author_id = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="OpenLibrary Author ID",
    )

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=255)
    isbn = ISBNField(unique=True, null=True, blank=True)
    openlibrary_edition_id = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="OpenLibrary Edition ID",
    )
    openlibrary_work_id = models.CharField(
        max_length=50, null=True, blank=True, verbose_name="OpenLibrary Work ID"
    )
    authors = models.ManyToManyField(Author)

    def __str__(self):
        return self.title

    def cover_url_small(self):
        return f"http://covers.openlibrary.org/b/isbn/{self.isbn}-S.jpg"

    def cover_url_medium(self):
        return f"http://covers.openlibrary.org/b/isbn/{self.isbn}-M.jpg"


class BookListing(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        AVAILABLE = "AVAILABLE", "Available"
        SWAPPED = "SWAPPED", "Swapped"
        REMOVED = "REMOVED", "Removed"

    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=9, choices=Status.choices, default=Status.PENDING
    )

    def __str__(self):
        return self.book.title

    def get_city(self):
        return self.owner.userprofile.city

    def remove(self):
        if self.status == self.Status.AVAILABLE:
            self.status = self.Status.REMOVED
            self.save()

            return True

        return False


class BookSwap(models.Model):
    #       User (A) proposes a swap to User (B)
    #       System (S) performs automatic actions
    #
    #       ┌─────────PROPOSED────────────┬────────────┐
    #       │            │                │            │
    #       A            B                S            B
    #       │            │                │            │
    #       ▼            ▼                ▼            ▼
    #   CANCELLED     ACCEPTED───S───►RESCINDED    DECLINED
    #                    │
    #                    A
    #                    │
    #                    ▼
    #                COMPLETED

    class Status(models.TextChoices):
        PROPOSED = "PROPOSED", "Proposed"
        CANCELLED = "CANCELLED", "Cancelled"
        RESCINDED = "RESCINDED", "Rescinded"
        ACCEPTED = "ACCEPTED", "Accepted"
        COMPLETED = "COMPLETED", "Completed"
        DECLINED = "DECLINED", "Declined"

    proposed_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="proposed_by"
    )
    proposed_to = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="proposed_to"
    )

    offered_listings = models.ManyToManyField(
        BookListing, related_name="offered_listings"
    )
    requested_listings = models.ManyToManyField(
        BookListing, related_name="requested_listings"
    )

    status = models.CharField(
        max_length=9, choices=Status.choices, default=Status.PROPOSED
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.proposed_by} proposed a swap to {self.proposed_to} on {self.created_at}"  # noqa: E501

    def get_absolute_url(self):
        return reverse("swap", kwargs={"id": self.pk})

    def notify(self, request: HttpRequest, event_type: "BookSwapEvent.Type"):
        match event_type:
            case BookSwapEvent.Type.PROPOSE:
                subject = f"{self.proposed_by.username} wants to swap books with you"
                message = render_to_string(
                    "core/emails/proposed_swap_notification.txt",
                    {
                        "proposed_by": self.proposed_by,
                        "swap_url": request.build_absolute_uri(self.get_absolute_url()),
                        "offered_listings": self.offered_listings.all(),
                        "requested_listings": self.requested_listings.all(),
                    },
                )
                recipient = self.proposed_to

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=None,
                    recipient_list=[recipient.email],
                )

            case BookSwapEvent.Type.CANCEL:
                pass
            case BookSwapEvent.Type.ACCEPT:
                subject = f"{self.proposed_to.username} accepted your book swap"
                message = render_to_string(
                    "core/emails/accepted_swap_notification.txt",
                    {
                        "proposed_to": self.proposed_to,
                        "swap_url": request.build_absolute_uri(self.get_absolute_url()),
                        "offered_listings": self.offered_listings.all(),
                        "requested_listings": self.requested_listings.all(),
                    },
                )
                recipient = self.proposed_by

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=None,
                    recipient_list=[recipient.email],
                )
            case BookSwapEvent.Type.DECLINE:
                pass

    def accept(self, user: User):
        if user != self.proposed_to:
            raise PermissionDenied("Only the receiver can accept this swap")

        if self.status == self.Status.PROPOSED:
            self.status = self.Status.ACCEPTED
            self.save()

            BookSwapEvent.objects.create(
                swap=self,
                user=user,
                type=BookSwapEvent.Type.ACCEPT,
            )

            return True

        return False

    def complete(self, user: User):
        logger.debug("User %s attempting to complete swap %d", user, self.id)

        if user != self.proposed_by:
            raise PermissionDenied("Only the proposer can complete this swap")

        if self.status == self.Status.ACCEPTED:
            self.status = self.Status.COMPLETED
            self.save()

            BookSwapEvent.objects.create(
                swap=self,
                user=user,
                type=BookSwapEvent.Type.COMPLETE,
            )

            # mark all involved books as swapped
            for offered_listing in self.offered_listings.all():
                offered_listing.status = BookListing.Status.SWAPPED
                offered_listing.save()

            for requested_listing in self.requested_listings.all():
                requested_listing.status = BookListing.Status.SWAPPED
                requested_listing.save()

            # cancel any other swaps involving these listings
            book_in_swap = Q(offered_listings__in=self.offered_listings.all()) | Q(
                requested_listings__in=self.requested_listings.all()
            )
            swap_open = Q(status=BookSwap.Status.PROPOSED) | Q(
                status=BookSwap.Status.ACCEPTED
            )
            other_swaps = BookSwap.objects.filter(book_in_swap, swap_open).exclude(
                id=self.id
            )

            for swap in other_swaps:
                if swap.rescind():
                    logger.info(
                        "Rescinded swap %d due to completion of swap %d",
                        swap.id,
                        self.id,
                    )
                else:
                    logger.warning(
                        "Failed to rescind swap %d during completion of swap %d",
                        swap.id,
                        self.id,
                    )

            return True

        return False

    def rescind(self):
        if self.status in [self.Status.PROPOSED, self.Status.ACCEPTED]:
            self.status = self.Status.RESCINDED
            self.save()

            BookSwapEvent.objects.create(
                swap=self,
                user=None,
                type=BookSwapEvent.Type.RESCIND,
            )

            return True

        return False

    def decline(self, user: User):
        if user != self.proposed_to:
            raise PermissionDenied("Only the receiver can decline this swap")

        if self.status == self.Status.PROPOSED:
            self.status = self.Status.DECLINED
            self.save()

            BookSwapEvent.objects.create(
                swap=self,
                user=user,
                type=BookSwapEvent.Type.DECLINE,
            )

            return True

        return False

    def cancel(self, user: User):
        if user != self.proposed_by:
            raise PermissionDenied("Only the proposer can cancel this swap")

        if self.status == self.Status.PROPOSED:
            self.status = self.Status.CANCELLED
            self.save()

            BookSwapEvent.objects.create(
                swap=self,
                user=user,
                type=BookSwapEvent.Type.CANCEL,
            )
            return True

        return False

    def get_timeline(self):
        events = [{"type": "event", "item": event} for event in self.events.all()]
        messages = [{"type": "message", "item": msg} for msg in self.messages.all()]

        timeline = events + messages
        timeline.sort(key=lambda x: x["item"].created_at)

        return timeline


class BookSwapEvent(models.Model):
    class Type(models.TextChoices):
        PROPOSE = "PROPOSE", "Proposed"
        CANCEL = "CANCEL", "Cancelled"
        RESCIND = "RESCIND", "Rescinded"
        ACCEPT = "ACCEPT", "Accepted"
        DECLINE = "DECLINE", "Declined"
        COMPLETE = "COMPLETE", "Completed"

    swap = models.ForeignKey(BookSwap, on_delete=models.CASCADE, related_name="events")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    type = models.CharField(max_length=8, choices=Type.choices)
    created_at = models.DateTimeField(auto_now_add=True)


class BookSwapMessage(models.Model):
    swap = models.ForeignKey(
        BookSwap, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Validate that the sender is involved in the swap
        if self.sender != self.swap.proposer and self.sender != self.swap.receiver:
            raise ValidationError("Messages can only be sent by swap participants")
