from django.urls import path

from core import views

urlpatterns = [
    path("", views.index, name="index"),
    path("listings", views.listings, name="listings"),
    path("listings/new", views.new_listing, name="new_listing"),
]
