from django.contrib import admin

from core.models import BookListing, BookSwap, BookSwapEvent, BookSwapMessage


@admin.register(BookListing)
class BookListingAdmin(admin.ModelAdmin):
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
