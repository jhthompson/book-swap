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
