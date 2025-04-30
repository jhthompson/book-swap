from django.contrib import admin

from core.models import BookListing


@admin.register(BookListing)
class BookListingAdmin(admin.ModelAdmin):
    pass
