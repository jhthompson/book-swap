from django.urls import path

from core import views

urlpatterns = [
    # listings
    path("listings", views.listings, name="listings"),
    path("listings/new", views.new_listing, name="new_listing"),
    path("listings/<int:id>", views.listing, name="listing"),
    path("listings/<int:id>/edit", views.edit_listing, name="edit_listing"),
    # swaps
    path("swaps", views.swaps, name="swaps"),
    path("swaps/new", views.new_swap, name="new_swap"),
    path("swaps/<int:id>", views.swap, name="swap"),
    # index
    path("", views.index, name="index"),
]
