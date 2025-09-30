from isbn_field import ISBNField

from django.contrib.auth.models import User
from django.contrib.gis.db import models as geo_models
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import models
from django.forms import ValidationError
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    city = models.CharField(max_length=100)
    location = geo_models.PointField()

    def __str__(self):
        return f"{self.user.username}'s Profile"


class BookListing(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        SWAPPED = "SWAPPED", "Swapped"
        REMOVED = "REMOVED", "Removed"

    # user provided
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    cover_photo = models.FileField(upload_to="book_listing_covers/")
    isbn = ISBNField(blank=True)

    # system managed
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=9, choices=Status.choices, default=Status.AVAILABLE
    )

    def __str__(self):
        return self.title

    def get_city(self):
        return self.owner.userprofile.city

    def remove(self):
        if self.status == self.Status.AVAILABLE:
            self.status = self.Status.REMOVED
            self.save()

            return True

        return False


class BookSwap(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "PROPOSED", "Proposed"
        CANCELLED = "CANCELLED", "Cancelled"
        ACCEPTED = "ACCEPTED", "Accepted"
        COMPLETED = "COMPLETED", "Completed"
        DECLINED = "DECLINED", "Declined"

    proposed_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="proposed_by"
    )
    proposed_to = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="proposed_to"
    )

    offered_books = models.ManyToManyField(BookListing, related_name="offered_books")
    requested_books = models.ManyToManyField(
        BookListing, related_name="requested_books"
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
                        "offered_books": self.offered_books.all(),
                        "requested_books": self.requested_books.all(),
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
                        "offered_books": self.offered_books.all(),
                        "requested_books": self.requested_books.all(),
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
        if user != self.proposed_by:
            raise PermissionDenied("Only the proposer can complete this swap")

        if self.status == self.Status.ACCEPTED:
            self.status = self.Status.COMPLETED
            self.save()

            # TODO: have to do much more here...
            # - soft delete books listed in this swap?
            # - cancel any other swaps involving these listings?

            BookSwapEvent.objects.create(
                swap=self,
                user=user,
                type=BookSwapEvent.Type.COMPLETE,
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
        ACCEPT = "ACCEPT", "Accepted"
        DECLINE = "DECLINE", "Declined"
        COMPLETE = "COMPLETE", "Completed"

    swap = models.ForeignKey(BookSwap, on_delete=models.CASCADE, related_name="events")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
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
