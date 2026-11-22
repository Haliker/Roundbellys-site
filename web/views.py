import logging
from datetime import date

from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from . import content, pricing
from .forms import CateringForm, ContactForm, FundraiserForm
from .models import Booking, Testimonial

log = logging.getLogger(__name__)


def _alert(subject, body):
    """Tell the office about a new request. Never stops the visitor if email isn't set up or fails."""
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [settings.OFFICE_EMAIL], fail_silently=False)
    except Exception:  # noqa: BLE001 - the request is saved either way
        log.exception("Office alert email failed: %s", subject)


def home(request):
    return render(request, "web/home.html", {
        "events": Booking.upcoming_public()[:4],
        "flavors": content.flavors_with_prices(),
        "rules": pricing.as_json(),
        "quotes": Testimonial.objects.filter(show=True, page="home"),
    })


def catering(request):
    initial = {"style": "truck", "guests": 100, "extra_hours": 0}
    for key in ("style", "guests"):
        if request.GET.get(key):
            initial[key] = request.GET[key]
    form = CateringForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if form.is_bot():
            return redirect("web:thanks", kind="catering")
        req = form.save(commit=False)
        est = pricing.estimate(req.style, req.guests, form.cleaned_data["addons"], req.extra_hours, req.event_date)
        req.addons = est["addons"]
        req.est_total, req.est_deposit, req.minimum_applied = est["total"], est["deposit"], est["minimum_applies"]
        req.date_was_booked = Booking.booked_on(req.event_date)
        req.save()
        _alert(f"New catering request: {req.event_type}, {req.event_date:%b %-d} ({req.guests} guests)",
               "\n".join([
                   f"{req.name} - {req.phone} - {req.email}",
                   f"{req.event_type} on {req.event_date:%A, %B %-d, %Y} at {req.start_time:%-I:%M %p}",
                   f"Where: {req.venue + ', ' if req.venue else ''}{req.address}",
                   f"{req.style_name}, {req.guests} guests" + (f", add-ons: {', '.join(req.addon_names)}" if req.addons else ""),
                   f"Extra hours: {req.extra_hours}" if req.extra_hours else "",
                   f"Estimate: ${req.est_total:,.2f} plus tax (deposit ${req.est_deposit:,.2f})"
                   + (" - minimum applies" if req.minimum_applied else ""),
                   f"Had our pizza: {req.get_had_pizza_display()}. Venue OK for the Bus: {req.get_venue_ok_display()}.",
                   f"Wants a tasting: {req.tasting_when or 'yes'}" if req.wants_tasting else "",
                   "HEADS UP: something is already on the calendar that day." if req.date_was_booked else "",
                   f"Message: {req.message}" if req.message else "",
                   "", "Open it: " + request.build_absolute_uri(reverse("admin:web_cateringrequest_change", args=[req.pk])),
               ]).replace("\n\n\n", "\n\n"))
        return redirect("web:thanks", kind="catering")
    return render(request, "web/catering.html", {"form": form, "rules": pricing.as_json(), "styles": pricing.STYLES,
                                                  "quotes": Testimonial.objects.filter(show=True, page="catering"),
                                                  "addons": pricing.ADDONS, "extra_hour": pricing.EXTRA_HOUR})


@require_GET
def date_check(request):
    """Is the Bus already booked that day? Used by the quote form while people type."""
    try:
        day = date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        return JsonResponse({"ok": False}, status=400)
    return JsonResponse({"ok": True, "booked": Booking.booked_on(day)})


def events(request):
    return render(request, "web/events.html", {"events": Booking.upcoming_public()})


def menu(request):
    return render(request, "web/menu.html", {"flavors": content.flavors_with_prices(), "tiers": content.TIERS})


def fundraising(request):
    form = FundraiserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if form.is_bot():
            return redirect("web:thanks", kind="fundraising")
        f = form.save()
        _alert(f"New fundraiser application: {f.group}",
               f"{f.name} - {f.phone} - {f.email}\n{f.group}"
               + (f" ({f.organization})" if f.organization else "")
               + f"\nAbout {f.sellers} sellers"
               + (f", hoping to start {f.start_date:%b %-d, %Y}" if f.start_date else "")
               + (f"\nDeliver to: {f.delivery_address}" if f.delivery_address else "")
               + (f"\nMessage: {f.message}" if f.message else "")
               + "\n\nOpen it: " + request.build_absolute_uri(reverse("admin:web_fundraiserinquiry_change", args=[f.pk])))
        return redirect("web:thanks", kind="fundraising")
    return render(request, "web/fundraising.html", {
        "form": form, "tiers": content.TIERS, "flavors": content.flavors_with_prices(),
        "share": int(content.TEAM_SHARE * 100), "avg": content.AVERAGE_PIZZA,
        "quotes": Testimonial.objects.filter(show=True, page="fundraising"),
    })


def wholesale(request):
    return render(request, "web/wholesale.html", {"flavors": content.flavors_with_prices()})


def contact(request):
    initial = {"topic": request.GET.get("topic", "general")}
    form = ContactForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if form.is_bot():
            return redirect("web:thanks", kind="contact")
        m = form.save()
        _alert(f"Website message ({m.get_topic_display()}): {m.name}",
               f"{m.name} - {m.email}" + (f" - {m.phone}" if m.phone else "")
               + (f"\nBusiness: {m.business}" if m.business else "") + f"\n\n{m.message}")
        return redirect("web:thanks", kind="contact")
    return render(request, "web/contact.html", {"form": form})


THANKS = {
    "catering": ("Your request is in.", "We'll call or email you within one business day to talk through your event. "
                 "Nothing is booked or charged yet."),
    "fundraising": ("Your application is in.", "We'll reach out within one business day to set up your sale dates."),
    "contact": ("Message sent.", "We'll get back to you within one business day."),
}


def thanks(request, kind):
    title, text = THANKS.get(kind, THANKS["contact"])
    return render(request, "web/thanks.html", {"title": title, "text": text, "kind": kind})


def about(request):
    return render(request, "web/about.html")


def robots(request):
    from django.http import HttpResponse
    return HttpResponse("User-agent: *\nDisallow: /office/\n", content_type="text/plain")
