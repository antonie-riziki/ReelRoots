from django import forms
from django.core.exceptions import ValidationError

from .models import UserProfile


HERITAGE_TOPICS = [
    ("history", "History"),
    ("culture", "Culture"),
    ("heritage", "Heritage"),
    ("oral-history", "Oral history"),
    ("indigenous-knowledge", "Indigenous knowledge"),
    ("architecture", "Architecture"),
    ("music", "Music"),
    ("food", "Food"),
    ("art", "Art"),
    ("historical-figures", "Historical figures"),
    ("historical-events", "Historical events"),
]

REGIONS = [
    ("East Africa", "East Africa"),
    ("West Africa", "West Africa"),
    ("Central Africa", "Central Africa"),
    ("North Africa", "North Africa"),
    ("Southern Africa", "Southern Africa"),
    ("Global African diaspora", "Global African diaspora"),
]

COUNTRIES = [
    ("Kenya", "Kenya"),
    ("Uganda", "Uganda"),
    ("Tanzania", "Tanzania"),
    ("Rwanda", "Rwanda"),
    ("Ethiopia", "Ethiopia"),
    ("Nigeria", "Nigeria"),
    ("Ghana", "Ghana"),
    ("South Africa", "South Africa"),
    ("Other", "Other countries"),
]

LANGUAGES = [
    ("en", "English"),
    ("sw", "Kiswahili"),
    ("fr", "French"),
    ("ar", "Arabic"),
    ("am", "Amharic"),
    ("yo", "Yoruba"),
    ("zu", "isiZulu"),
]

CONTENT_TYPES = [
    ("short_video", "Short videos"),
    ("oral_history", "Oral histories"),
    ("archive_document", "Archive documents"),
    ("explainer", "Explainers"),
]


class SignUpForm(forms.Form):
    name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=32)
    institution = forms.CharField(max_length=255, required=False)
    password = forms.CharField(min_length=8, widget=forms.PasswordInput)
    confirm_password = forms.CharField(min_length=8, widget=forms.PasswordInput)
    terms = forms.BooleanField()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") and cleaned.get("password") != cleaned.get("confirm_password"):
            raise ValidationError("Passwords do not match.")
        return cleaned


class SignInForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class VerifyPhoneForm(forms.Form):
    code = forms.CharField(min_length=6, max_length=6, strip=True)

    def clean_code(self):
        code = self.cleaned_data["code"]
        if not code.isdigit():
            raise ValidationError("Enter the six-digit code sent to your phone.")
        return code


class OnboardingForm(forms.Form):
    topics = forms.MultipleChoiceField(
        choices=HERITAGE_TOPICS,
        required=True,
        widget=forms.CheckboxSelectMultiple,
    )
    regions = forms.MultipleChoiceField(
        choices=REGIONS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    countries = forms.MultipleChoiceField(
        choices=COUNTRIES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    languages = forms.MultipleChoiceField(
        choices=LANGUAGES,
        required=True,
        widget=forms.CheckboxSelectMultiple,
    )
    content_types = forms.MultipleChoiceField(
        choices=CONTENT_TYPES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def clean_topics(self):
        topics = self.cleaned_data["topics"]
        if len(topics) > 6:
            raise ValidationError("Choose up to six interests for now.")
        return topics


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["name", "institution"]
