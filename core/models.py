from django.db import models
from django.contrib.auth.models import User

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
    proposed_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="proposed_by"
    )
    proposed_to = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="proposed_to"
    )
    proposed_on = models.DateTimeField(auto_now_add=True)

    offered_books = models.ManyToManyField(BookListing, related_name="offered_books")
    requested_books = models.ManyToManyField(
        BookListing, related_name="requested_books"
    )

    def __str__(self):
        return f"Swap proposed by {self.proposed_by} to {self.proposed_to} on {self.proposed_on}"
