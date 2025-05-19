from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

from django.forms import ValidationError
from isbn_field import ISBNField


class BookListing(models.Model):
    # user provided
    title = models.CharField(max_length=255)
    cover_photo = models.FileField(upload_to="book_listing_covers/")
    isbn = ISBNField(blank=True)

    # system populated/generated
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class BookSwap(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "PROPOSED", "Proposed"
        CANCELLED = "CANCELLED", "Cancelled"
        ACCEPTED = "ACCEPTED", "Accepted"
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
        return f"{self.proposed_by} proposed a swap to {self.proposed_to} on {self.created_at}"

    def accept(self, user: User, message: str = None):
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

            if message:
                BookSwapMessage.objects.create(
                    swap=self,
                    sender=user,
                    content=message,
                )

            return True

        return False

    def reject(self, user: User):
        if user != self.proposed_to:
            raise PermissionDenied("Only the receiver can reject this swap")

        if self.status == self.Status.PROPOSED:
            self.status = self.Status.DECLINED
            self.save()
            return True

        return False

    def cancel(self, user: User):
        if user != self.proposed_by:
            raise PermissionDenied("Only the proposer can cancel this swap")

        if self.status == self.Status.PROPOSED:
            self.status = self.Status.CANCELLED
            self.save()
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

    swap = models.ForeignKey(BookSwap, on_delete=models.CASCADE, related_name="events")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=7, choices=Type.choices)
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
