from django import forms


from core.models import BookListing


class BookListingForm(forms.ModelForm):
    class Meta:
        model = BookListing
        fields = ["title", "cover_photo", "isbn"]
