from datetime import date, time, timedelta
from decimal import Decimal as D

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import pricing
from .models import Booking, CateringRequest, ContactMessage, FundraiserInquiry, SiteSettings


class PricingTest(TestCase):
    def test_minimum_applies_to_the_total_with_addons(self):
        # 70 guests Food Truck = $1,050 -> billed $1,500; breadsticks = $1,400, still the $1,500 minimum
        e = pricing.estimate("truck", 70)
        self.assertTrue(e["minimum_applies"])
        self.assertEqual(e["total"], D("1500"))
        e = pricing.estimate("truck", 70, ["breadsticks"])
        self.assertEqual(e["food"], D("1400"))
        self.assertEqual(e["total"], D("1500"))
        # mini donuts instead: $1,540, over the minimum
        e = pricing.estimate("truck", 70, ["donuts"])
        self.assertFalse(e["minimum_applies"])
        self.assertEqual(e["total"], D("1540"))

    def test_the_120_guest_example(self):
        e = pricing.estimate("truck", 120, ["breadsticks", "donuts"], event_date=date(2027, 6, 12))
        self.assertEqual(e["total"], D("3240"))
        self.assertEqual(e["deposit"], D("810.00"))
        self.assertEqual(e["balance"], D("2430.00"))
        self.assertEqual(e["balance_due"], date(2027, 6, 5))

    def test_buffet_minimum_and_extra_hours(self):
        e = pricing.estimate("buffet", 60, extra_hours=1)
        self.assertEqual(e["food"], D("1200"))
        self.assertEqual(e["total"], D("2200"))  # $2,000 minimum + one $200 hour
        self.assertEqual(e["service_hours"], 4)

    def test_suggestions_say_which_addons_are_free(self):
        sugs = {s["key"]: s for s in pricing.estimate("truck", 70)["suggestions"]}
        self.assertTrue(sugs["breadsticks"]["free"])
        self.assertEqual(sugs["donuts"]["extra"], D("40"))
        self.assertEqual(pricing.estimate("truck", 200)["suggestions"], [])

    def test_unknown_addons_and_silly_numbers_are_ignored(self):
        e = pricing.estimate("truck", 999999, ["lobster"], extra_hours=99)
        self.assertEqual(e["addons"], [])
        self.assertEqual(e["guests"], pricing.MAX_GUESTS)
        self.assertEqual(e["extra_hours"], pricing.MAX_EXTRA_HOURS)


@override_settings(OFFICE_EMAIL="office@example.com")
class CateringFormTest(TestCase):
    def post(self, **over):
        data = {"style": "truck", "guests": "70", "addons": ["breadsticks"], "extra_hours": "0",
                "event_type": "Graduation party", "event_date": (timezone.localdate() + timedelta(days=30)).isoformat(),
                "start_time": "17:00", "venue": "", "address": "123 Main St, Mishawaka, IN", "had_pizza": "no",
                "venue_ok": "unsure", "name": "Pat Doe", "email": "pat@example.com", "phone": "(574) 555-1234",
                "message": "", "website": ""}
        data.update(over)
        return self.client.post(reverse("web:catering"), data)

    def test_request_is_saved_priced_on_the_server_and_office_told(self):
        r = self.post()
        self.assertRedirects(r, reverse("web:thanks", args=["catering"]))
        req = CateringRequest.objects.get()
        self.assertEqual(req.est_total, D("1500"))
        self.assertTrue(req.minimum_applied)
        self.assertEqual(req.est_deposit, D("375.00"))
        self.assertEqual(req.phone, "574-555-1234")
        self.assertEqual(req.addons, ["breadsticks"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Graduation party", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["office@example.com"])

    def test_booked_date_is_flagged(self):
        day = timezone.localdate() + timedelta(days=30)
        Booking.objects.create(kind=Booking.PRIVATE, title="Smith wedding", date=day, start_time=time(16),
                               end_time=time(19), address="x")
        self.post(event_date=day.isoformat())
        self.assertTrue(CateringRequest.objects.get().date_was_booked)
        j = self.client.get(reverse("web:date_check"), {"date": day.isoformat()}).json()
        self.assertTrue(j["booked"])
        self.assertFalse(self.client.get(reverse("web:date_check"), {"date": (day + timedelta(days=1)).isoformat()}).json()["booked"])

    def test_bad_input_shows_errors(self):
        r = self.post(phone="123", guests="0", event_date=timezone.localdate().isoformat())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "10-digit phone")
        self.assertContains(r, "how many guests")
        self.assertContains(r, "from tomorrow on")
        self.assertFalse(CateringRequest.objects.exists())

    def test_bots_are_quietly_dropped(self):
        r = self.post(website="http://spam.example")
        self.assertRedirects(r, reverse("web:thanks", args=["catering"]))
        self.assertFalse(CateringRequest.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_quick_ticket_values_carry_over(self):
        r = self.client.get(reverse("web:catering"), {"style": "buffet", "guests": "150"})
        self.assertContains(r, 'value="150"')


class OtherFormsTest(TestCase):
    def test_fundraiser_application(self):
        r = self.client.post(reverse("web:fundraising"), {
            "group": "Lakeville Wrestling", "organization": "", "name": "Coach K", "email": "k@example.com",
            "phone": "574 555 9876", "sellers": "40", "start_date": "", "delivery_address": "", "color1": "#14284B",
            "color2": "#F2A900", "message": "", "website": ""})
        self.assertRedirects(r, reverse("web:thanks", args=["fundraising"]))
        f = FundraiserInquiry.objects.get()
        self.assertEqual(f.color1, "#14284b")
        self.assertEqual(f.phone, "574-555-9876")

    def test_contact_message(self):
        r = self.client.post(reverse("web:contact"), {"topic": "wholesale", "name": "Gas Stop", "email": "g@example.com",
                                                      "phone": "", "business": "Gas Stop", "message": "Can we carry you?",
                                                      "website": ""})
        self.assertRedirects(r, reverse("web:thanks", args=["contact"]))
        self.assertEqual(ContactMessage.objects.get().topic, "wholesale")


class PagesTest(TestCase):
    def test_every_page_opens(self):
        for name in ["home", "catering", "events", "menu", "fundraising", "wholesale", "about", "contact"]:
            r = self.client.get(reverse(f"web:{name}"))
            self.assertEqual(r.status_code, 200, name)
        self.assertEqual(self.client.get(reverse("web:thanks", args=["catering"])).status_code, 200)

    def test_only_upcoming_public_events_show(self):
        today = timezone.localdate()
        Booking.objects.create(kind=Booking.PUBLIC, title="Mishawaka Fall Fest", date=today + timedelta(days=5),
                               start_time=time(11), end_time=time(15), address="Mishawaka, IN")
        Booking.objects.create(kind=Booking.PRIVATE, title="Secret wedding", date=today + timedelta(days=6),
                               start_time=time(11), end_time=time(15), address="x")
        Booking.objects.create(kind=Booking.PUBLIC, title="Old festival", date=today - timedelta(days=5),
                               start_time=time(11), end_time=time(15), address="x")
        Booking.objects.create(kind=Booking.PUBLIC, title="Rained out", date=today + timedelta(days=7),
                               start_time=time(11), end_time=time(15), address="x", cancelled=True)
        for url in [reverse("web:events"), reverse("web:home")]:
            r = self.client.get(url)
            self.assertContains(r, "Mishawaka Fall Fest")
            for hidden in ["Secret wedding", "Old festival", "Rained out"]:
                self.assertNotContains(r, hidden)

    def test_program_name_comes_from_settings(self):
        s = SiteSettings.get()
        s.program_name = "Dough for Your Team"
        s.save()
        self.assertContains(self.client.get(reverse("web:fundraising")), "Dough for Your Team")

    def test_old_wix_addresses_redirect(self):
        self.assertRedirects(self.client.get("/shop"), "/fundraising/", status_code=301)
        self.assertRedirects(self.client.get("/wholesale-shop"), "/wholesale/", status_code=301)

    def test_office_needs_a_login(self):
        r = self.client.get("/office/")
        self.assertEqual(r.status_code, 302)


class TestimonialTest(TestCase):
    def test_quotes_only_show_once_ticked(self):
        from .models import Testimonial
        t = Testimonial.objects.get(organization="Middlebury Elementary School")
        self.assertFalse(t.show)
        self.assertNotContains(self.client.get(reverse("web:fundraising")), "without any hesitation")
        t.show = True
        t.save()
        r = self.client.get(reverse("web:fundraising"))
        self.assertContains(r, "without any hesitation")
        self.assertContains(r, "Marion Hostetler, Principal, Middlebury Elementary School")
        self.assertNotContains(self.client.get(reverse("web:catering")), "without any hesitation")
