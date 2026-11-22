import re
from datetime import timedelta

from django import forms
from django.utils import timezone

from . import pricing
from .models import CateringRequest, ContactMessage, FundraiserInquiry

EVENT_TYPES = ["Graduation party", "Wedding", "Rehearsal dinner", "Shower", "Birthday", "Anniversary",
               "Company event", "School or church event", "Team party", "Other"]

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class Honeypot(forms.Form):
    """A hidden box people never see. Bots fill it in; we quietly drop those."""
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def is_bot(self):
        return bool(self.cleaned_data.get("website"))


def _phone(value):
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise forms.ValidationError("Enter a 10-digit phone number so we can call you back.")
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"


class CateringForm(Honeypot, forms.ModelForm):
    addons = forms.MultipleChoiceField(choices=[(k, v["name"]) for k, v in pricing.ADDONS.items()],
                                       required=False, widget=forms.CheckboxSelectMultiple)
    style = forms.ChoiceField(choices=[(k, v["name"]) for k, v in pricing.STYLES.items()], widget=forms.RadioSelect)
    event_type = forms.ChoiceField(choices=[(t, t) for t in EVENT_TYPES])
    had_pizza = forms.ChoiceField(choices=CateringRequest.YES_NO, widget=forms.RadioSelect, label="Have you had our pizza before?")
    venue_ok = forms.ChoiceField(choices=CateringRequest.VENUE, widget=forms.RadioSelect,
                                 label="Does the spot have hard, level ground with 40 feet for the Bus to park?")

    class Meta:
        model = CateringRequest
        fields = ["style", "guests", "addons", "extra_hours", "event_type", "event_date", "start_time", "venue",
                  "address", "had_pizza", "venue_ok", "wants_tasting", "tasting_when", "name", "email", "phone", "message"]
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "guests": forms.NumberInput(attrs={"min": 1, "max": pricing.MAX_GUESTS, "inputmode": "numeric"}),
            "extra_hours": forms.NumberInput(attrs={"min": 0, "max": pricing.MAX_EXTRA_HOURS}),
            "message": forms.Textarea(attrs={"rows": 4}),
            "address": forms.TextInput(attrs={"autocomplete": "street-address"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
        }
        labels = {
            "guests": "How many guests?", "extra_hours": "Extra hours of service", "event_date": "Event date",
            "start_time": "When should we start serving?", "venue": "Place name",
            "address": "Event address", "wants_tasting": "I'd like a free tasting",
            "tasting_when": "Days or times that work for a tasting", "name": "Your name",
            "message": "Anything else we should know?",
        }

    def clean_phone(self):
        return _phone(self.cleaned_data.get("phone"))

    def clean_guests(self):
        g = self.cleaned_data.get("guests") or 0
        if g < 1:
            raise forms.ValidationError("Enter how many guests you expect.")
        if g > pricing.MAX_GUESTS:
            raise forms.ValidationError(f"For more than {pricing.MAX_GUESTS} guests, send us a message instead.")
        return g

    def clean_extra_hours(self):
        h = self.cleaned_data.get("extra_hours") or 0
        if h > pricing.MAX_EXTRA_HOURS:
            raise forms.ValidationError(f"Up to {pricing.MAX_EXTRA_HOURS} extra hours here; call us for longer.")
        return h

    def clean_event_date(self):
        d = self.cleaned_data["event_date"]
        today = timezone.localdate()
        if d < today + timedelta(days=1):
            raise forms.ValidationError("Pick a date from tomorrow on. For something sooner, give us a call.")
        if d > today + timedelta(days=730):
            raise forms.ValidationError("We book up to two years ahead.")
        return d


class FundraiserForm(Honeypot, forms.ModelForm):
    class Meta:
        model = FundraiserInquiry
        fields = ["group", "organization", "name", "email", "phone", "sellers", "start_date", "delivery_address",
                  "color1", "color2", "message"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "sellers": forms.NumberInput(attrs={"min": 1, "max": 2000, "inputmode": "numeric"}),
            "color1": forms.TextInput(attrs={"type": "color", "value": "#a3281c"}),
            "color2": forms.TextInput(attrs={"type": "color", "value": "#f6b400"}),
            "message": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {"message": "Anything else we should know?", "group": "Group or team name",
                  "organization": "School, club or church", "name": "Your name (coordinator)"}

    def clean_phone(self):
        return _phone(self.cleaned_data.get("phone"))

    def _color(self, key):
        v = (self.cleaned_data.get(key) or "").strip()
        if v and not HEX.match(v):
            raise forms.ValidationError("Pick a color from the color box.")
        return v.lower()

    def clean_color1(self):
        return self._color("color1")

    def clean_color2(self):
        return self._color("color2")


class ContactForm(Honeypot, forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["topic", "name", "email", "phone", "business", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}
        labels = {"topic": "What's this about?", "name": "Your name", "business": "Business name", "message": "Your message"}

    def clean_phone(self):
        v = self.cleaned_data.get("phone")
        return _phone(v) if v else ""
