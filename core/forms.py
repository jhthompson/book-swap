from isbn_field.validators import ISBNValidator

from django import forms

from core.models import BookListing


class BookListingISBNForm(forms.Form):
    isbn = forms.CharField(
        required=False,
        label="ISBN",
        min_length=10,
        validators=[ISBNValidator],
    )


class BookListingDetailsForm(forms.Form):
    title = forms.CharField(max_length=255)
    author = forms.CharField(max_length=255)
    cover_photo = forms.ImageField(
        widget=forms.ClearableFileInput(
            attrs={"capture": "environment", "accept": "image/*"}
        ),
    )


class BookListingForm(forms.ModelForm):
    class Meta:
        model = BookListing
        fields = ["title", "author", "cover_photo", "isbn"]
        widgets = {
            "cover_photo": forms.ClearableFileInput(
                attrs={"capture": "environment", "accept": "image/*"}
            ),
        }


class BookListingSelectionFormSet(forms.BaseFormSet):
    def __init__(self, *args, **kwargs):
        owners = kwargs.pop("owners", [])
        super().__init__(*args, **kwargs)
        self.owners = owners

    def get_form_kwargs(self, form_index):
        form_kwargs = super().get_form_kwargs(form_index)
        if form_index < len(self.owners):
            form_kwargs["owner"] = self.owners[form_index]
        return form_kwargs


class BookListingSelectionForm(forms.Form):
    book_listings = forms.ModelMultipleChoiceField(
        queryset=BookListing.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Select books",
    )

    def __init__(self, *args, **kwargs):
        owner = kwargs.pop("owner", None)
        super().__init__(*args, **kwargs)
        if owner:
            self.fields["book_listings"].queryset = BookListing.objects.filter(
                owner=owner
            )
            self.fields["book_listings"].label = f"{owner.username}'s books"


class AcceptSwapForm(forms.Form):
    message = forms.CharField(
        label="How should they contact you to coordinate the swap?",
        widget=forms.Textarea(
            attrs={
                "class": "width:100",
            }
        ),
        help_text="Email, text message, WhatsApp, etc.",
    )
