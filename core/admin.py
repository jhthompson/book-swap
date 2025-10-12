from django.contrib import admin
from django.contrib.gis import admin as geo_admin

from core.models import (
    BookListing,
    BookSwap,
    BookSwapEvent,
    BookSwapMessage,
    OpenLibraryAuthor,
    UserProfile,
)


@admin.register(OpenLibraryAuthor)
class OpenLibraryAuthorAdmin(admin.ModelAdmin):
    pass


@admin.register(BookListing)
class BookListingAdmin(admin.ModelAdmin):
    pass


@admin.register(UserProfile)
class UserProfileAdmin(geo_admin.GISModelAdmin):
    pass


class BookSwapEventInline(admin.TabularInline):
    model = BookSwapEvent
    extra = 0


class BookSwapMessageInline(admin.TabularInline):
    model = BookSwapMessage
    extra = 0


@admin.register(BookSwap)
class BookSwapAdmin(admin.ModelAdmin):
    inlines = [BookSwapEventInline, BookSwapMessageInline]
