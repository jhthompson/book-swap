from django.contrib import admin

from core.models import BookListing, BookSwap


@admin.register(BookListing)
class BookListingAdmin(admin.ModelAdmin):
    pass


@admin.register(BookSwap)
class BookSwapAdmin(admin.ModelAdmin):
    pass
