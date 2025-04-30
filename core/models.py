from django.db import models
from django.contrib.auth.models import User

from isbn_field import ISBNField


class BookListing(models.Model):
    # required
    title = models.CharField(max_length=255)
    cover_photo = models.FileField(upload_to="book_listing_covers/")
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    # optional
    isbn = ISBNField(blank=True)

    def __str__(self):
        return self.title
