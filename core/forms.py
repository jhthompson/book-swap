from django import forms

from isbn_field.validators import ISBNValidator


class CreateListingForm(forms.Form):
    title = forms.CharField(max_length=255)
    cover_photo = forms.FileField()
    isbn = forms.CharField(required=False, min_length=10, validators=[ISBNValidator])
