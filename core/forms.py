from django import forms


from core.models import BookListing


class BookListingForm(forms.ModelForm):
    class Meta:
        model = BookListing
        fields = ["title", "cover_photo", "isbn"]
        widgets = {
            "cover_photo": forms.ClearableFileInput(
                attrs={"capture": "environment", "accept": "image/*"}
            ),
        }


class BookListingSelectionFormSet(forms.BaseFormSet):
    def __init__(self, *args, **kwargs):
        owners = kwargs.pop("owners", [])
        super(BookListingSelectionFormSet, self).__init__(*args, **kwargs)
        self.owners = owners

    def get_form_kwargs(self, form_index):
        form_kwargs = super(BookListingSelectionFormSet, self).get_form_kwargs(
            form_index
        )
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
        widget=forms.Textarea,
        help_text="Email, text message, WhatsApp, etc.",
    )
