from django.urls import path

from core import views

urlpatterns = [
    # listings
    path("listings", views.listings, name="listings"),
    path(
        "listings/new",
        views.BookListingWizardView.as_view(),
        name="new_listing",
    ),
    path("listings/<int:id>", views.listing, name="listing"),
    path("listings/<int:id>/edit", views.edit_listing, name="edit_listing"),
    path("listings/<int:id>/delete", views.delete_listing, name="delete_listing"),
    # swaps
    path("swaps", views.swaps, name="swaps"),
    path("swaps/new", views.new_swap, name="new_swap"),
    path("swaps/<int:id>", views.swap, name="swap"),
    path("swaps/<int:id>/messages", views.swap_messages, name="swap_messages"),
    path("swaps/<int:id>/cancel", views.cancel_swap, name="cancel_swap"),
    path("swaps/<int:id>/accept", views.accept_swap, name="accept_swap"),
    path("swaps/<int:id>/complete", views.complete_swap, name="complete_swap"),
    path("swaps/<int:id>/decline", views.decline_swap, name="decline_swap"),
    # search
    path("search", views.search, name="search"),
    path("map", views.map_view, name="map"),
    # API
    path("api/book-listings/", views.book_listings_api, name="book_listings_api"),
    # index
    path("", views.index, name="index"),
]
