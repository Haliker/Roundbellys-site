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


class FundraiserFlowTest(TestCase):
    def setUp(self):
        from .models import Fundraiser
        today = timezone.localdate()
        self.f = Fundraiser.objects.create(group="Test Tigers", coordinator="Coach", coordinator_email="c@example.com",
                                           sale_start=today, sale_end=today + timedelta(days=10), status="open",
                                           party_goal=100, color1="#000000", color2="#ff6a13")

    def join(self, **over):
        data = {"first_name": "jake", "last_initial": "s", "parent_name": "Amy Sullivan", "parent_email": "amy@example.com",
                "parent_phone": "5745550110", "goal": "20", "website": ""}
        data.update(over)
        return self.client.post(reverse("web:join", args=[self.f.join_code.lower()]), data)

    def test_family_signs_up_and_lands_on_their_seller_page(self):
        r = self.join()
        s = self.f.sellers.get()
        self.assertRedirects(r, reverse("web:seller_home", args=[s.token]))
        self.assertEqual((s.first_name, s.last_initial, s.parent_phone), ("Jake", "S", "574-555-0110"))
        page = self.client.get(reverse("web:seller_home", args=[s.token]))
        self.assertContains(page, reverse("web:order_page", args=[s.code]))
        self.assertContains(page, "<svg")  # QR code

    def test_buyer_orders_online_and_prices_come_from_the_server(self):
        self.join()
        s = self.f.sellers.get()
        url = reverse("web:order_page", args=[s.code])
        page = self.client.get(url)
        self.assertContains(page, "Jake S.")
        self.assertNotContains(page, "Sullivan")  # parent / last name never public
        r = self.client.post(url, {"q_deluxe_gf": "2", "q_cheese_10": "1", "q_pepperoni_12": "abc",
                                   "buyer_name": "Grandma", "buyer_phone": "", "buyer_email": "", "payment": "later",
                                   "website": ""})
        self.assertRedirects(r, reverse("web:order_thanks", args=[s.code]))
        from .models import Order
        o = Order.objects.get()
        self.assertEqual((o.pizzas, o.total, o.how, o.collected), (3, D("42"), "online", False))
        self.assertContains(self.client.get(reverse("web:order_thanks", args=[s.code])), "Grandma")
        # someone else's browser can't see that order
        from django.test import Client
        self.assertNotContains(Client().get(reverse("web:order_thanks", args=[s.code])), "Grandma")

    def test_card_only_offered_on_the_demo(self):
        self.join()
        s = self.f.sellers.get()
        r = self.client.post(reverse("web:order_page", args=[s.code]), {
            "q_cheese_10": "1", "buyer_name": "X", "payment": "card", "website": ""})
        self.assertEqual(r.status_code, 200)  # refused: not a choice on a real sale yet

    def test_empty_order_is_refused(self):
        self.join()
        s = self.f.sellers.get()
        r = self.client.post(reverse("web:order_page", args=[s.code]), {"buyer_name": "X", "payment": "later", "website": ""})
        self.assertContains(r, "Pick at least one pizza")

    def test_seller_logs_cash_order_then_marks_later_one_paid(self):
        from .models import Order
        self.join()
        s = self.f.sellers.get()
        self.client.post(reverse("web:seller_log", args=[s.token]), {
            "q_carnivore_12": "2", "buyer_name": "Uncle Dave", "payment": "later", "website": ""})
        o = Order.objects.get()
        self.assertFalse(o.collected)
        self.client.post(reverse("web:seller_home", args=[s.token]),
                         {"action": "collected", "order": o.pk, "value": "1", "paid_with": "check"})
        o.refresh_from_db()
        self.assertEqual((o.collected, o.payment), (True, "check"))

    def test_coordinator_totals_and_settlement(self):
        from .models import Order, OrderLine, Seller
        s = Seller.objects.create(fundraiser=self.f, first_name="Ava")
        for pay, total in [("card", 100), ("cash", 200), ("later", 50)]:
            o = Order.objects.create(fundraiser=self.f, seller=s, buyer_name="b", payment=pay, total=total, pizzas=5,
                                     collected=pay != "later")
            OrderLine.objects.create(order=o, flavor="cheese", size="10", qty=5, unit_price=10)
        t = self.f.totals()
        self.assertEqual(t["sales"], D("350"))
        self.assertEqual(t["share"], D("140.00"))
        self.assertEqual(t["invoice"], D("210.00"))
        self.assertEqual(t["credit"], D("97.00"))
        self.assertEqual(t["balance"], D("113.00"))
        self.assertEqual(t["uncollected"], D("50"))
        page = self.client.get(reverse("web:coordinator", args=[self.f.token]))
        self.assertContains(page, "$113.00")
        self.assertContains(page, "15</strong> of 100")
        packing = self.client.get(reverse("web:packing", args=[self.f.token]))
        self.assertContains(packing, "Ava")
        self.assertContains(packing, "15")

    def test_coordinator_adds_sellers_and_downloads_flyers(self):
        r = self.client.post(reverse("web:coordinator", args=[self.f.token]),
                             {"action": "add_sellers", "names": "Jake Sullivan\nmaria lopez\n\n"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sorted(s.display for s in self.f.sellers.all()), ["Jake S.", "Maria L."])
        pdf = self.client.get(reverse("web:all_flyers", args=[self.f.token]))
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_closed_sale_takes_no_orders_or_signups(self):
        from .models import Order
        self.join()
        s = self.f.sellers.get()
        self.f.status = "closed"
        self.f.save()
        self.assertContains(self.client.get(reverse("web:order_page", args=[s.code])), "This sale has ended")
        self.client.post(reverse("web:order_page", args=[s.code]), {"q_cheese_10": "1", "buyer_name": "X", "payment": "later"})
        self.assertFalse(Order.objects.exists())
        self.join(first_name="Late")
        self.assertEqual(self.f.sellers.count(), 1)

    def test_wrong_links_are_not_found(self):
        self.assertEqual(self.client.get(reverse("web:coordinator", args=["nope"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("web:seller_home", args=["nope"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("web:order_page", args=["ZZZZZ"])).status_code, 404)

    def test_demo_command(self):
        from django.core.management import call_command
        from io import StringIO
        from .models import Fundraiser
        call_command("make_demo_fundraiser", stdout=StringIO())
        call_command("make_demo_fundraiser", "--reset", stdout=StringIO())
        demo = Fundraiser.objects.get(is_demo=True)
        self.assertGreater(demo.totals()["pizzas"], 50)
        self.assertContains(self.client.get(reverse("web:coordinator", args=[demo.token])), "Demo fundraiser")


class SetupStageTest(TestCase):
    def test_families_can_join_before_the_sale_opens_but_orders_wait(self):
        from .models import Fundraiser, Order
        today = timezone.localdate()
        f = Fundraiser.objects.create(group="G", coordinator="C", coordinator_email="c@example.com", sale_start=today,
                                      sale_end=today + timedelta(days=5))  # status = setup
        self.client.post(reverse("web:join", args=[f.join_code]), {"first_name": "Ann", "parent_name": "P",
                         "parent_email": "p@example.com", "goal": "5", "website": ""})
        s = f.sellers.get()
        self.assertContains(self.client.get(reverse("web:order_page", args=[s.code])), "Orders open soon")
        self.client.post(reverse("web:order_page", args=[s.code]), {"q_cheese_10": "1", "buyer_name": "X", "payment": "later"})
        self.assertFalse(Order.objects.exists())
        self.client.post(reverse("web:coordinator", args=[f.token]), {"action": "open"})
        self.client.post(reverse("web:order_page", args=[s.code]), {"q_cheese_10": "1", "buyer_name": "X", "payment": "later", "website": ""})
        self.assertEqual(Order.objects.count(), 1)


class EmailAndImportTest(TestCase):
    def setUp(self):
        from .models import Fundraiser
        today = timezone.localdate()
        self.f = Fundraiser.objects.create(group="Test Tigers", coordinator="Coach Kim", coordinator_email="kim@example.com",
                                           sale_start=today, sale_end=today + timedelta(days=10), status="open",
                                           pickup_date=today + timedelta(days=20), pickup_place="Gym")
        self.dash = reverse("web:coordinator", args=[self.f.token])

    def test_signup_emails_the_parent_their_links(self):
        self.client.post(reverse("web:join", args=[self.f.join_code]), {
            "first_name": "jake", "last_initial": "s", "parent_name": "Amy", "parent_email": "amy@example.com",
            "parent_phone": "", "goal": "10", "website": ""})
        s = self.f.sellers.get()
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertEqual(m.to, ["amy@example.com"])
        self.assertEqual(m.reply_to, ["kim@example.com"])
        self.assertIn("Jake's seller page", m.subject)
        self.assertIn(reverse("web:seller_home", args=[s.token]), m.body)
        self.assertIn(reverse("web:order_page", args=[s.code]), m.body)
        self.assertNotIn("&#x27;", m.body + m.subject)  # plain text isn't HTML-escaped
        self.assertIn(reverse("web:seller_flyer", args=[s.token]), m.alternatives[0][0])
        self.assertEqual(self.f.emails.get().status, "sent")

    def test_online_order_sends_receipt_and_tells_the_parent(self):
        from .models import Seller
        s = Seller.objects.create(fundraiser=self.f, first_name="Jake", last_initial="S", parent_email="amy@example.com")
        self.client.post(reverse("web:order_page", args=[s.code]), {
            "q_cheese_10": "2", "buyer_name": "Grandma", "buyer_email": "gma@example.com", "payment": "later",
            "website": ""})
        to = {m.to[0]: m for m in mail.outbox}
        self.assertEqual(set(to), {"gma@example.com", "amy@example.com"})
        self.assertIn("$20.00", to["gma@example.com"].body)
        self.assertIn("pay Jake", to["gma@example.com"].body)
        self.assertIn("Grandma", to["amy@example.com"].subject)
        self.assertEqual(to["amy@example.com"].reply_to, ["gma@example.com"])

    def test_paper_order_receipt_only_when_email_given_and_no_note_to_parent(self):
        from .models import Seller
        s = Seller.objects.create(fundraiser=self.f, first_name="Jake", parent_email="amy@example.com")
        self.client.post(reverse("web:seller_log", args=[s.token]), {
            "q_cheese_10": "1", "buyer_name": "Neighbor", "buyer_email": "", "payment": "cash", "website": ""})
        self.assertEqual(len(mail.outbox), 0)
        self.client.post(reverse("web:seller_log", args=[s.token]), {
            "q_cheese_10": "1", "buyer_name": "Aunt", "buyer_email": "aunt@example.com", "payment": "cash", "website": ""})
        self.assertEqual([m.to for m in mail.outbox], [["aunt@example.com"]])
        self.assertIn("Paid to Jake", mail.outbox[0].body)

    def _upload(self, name, data):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post(self.dash, {"action": "upload", "file": SimpleUploadedFile(name, data)})

    def test_csv_upload_preview_then_add_and_email(self):
        from .models import Seller
        Seller.objects.create(fundraiser=self.f, first_name="Ava", last_initial="B", parent_email="b@example.com")
        csv_data = ("Student,Parent / Guardian,Email,Cell\n"
                    "Jake Sullivan,Erin Sullivan,erin@example.com,(574) 555-0101\n"
                    "\"Lopez, Maria\",Rosa,not-an-email,\n"
                    "Ava Brown,,b@example.com,\n"
                    ",,,\n"
                    "Theo,,theo@example.com,\n").encode()
        r = self._upload("roster.csv", csv_data)
        self.assertRedirects(r, reverse("web:seller_import", args=[self.f.token]))
        page = self.client.get(reverse("web:seller_import", args=[self.f.token]))
        self.assertContains(page, "3 sellers ready")
        self.assertContains(page, "already signed up")
        self.assertContains(page, "isn&#x27;t an email")
        self.assertContains(page, "Jake S.")
        self.assertNotContains(page, "Jake Sullivan")  # seller's last name never kept
        r = self.client.post(reverse("web:seller_import", args=[self.f.token]), {"email": "1"})
        self.assertRedirects(r, self.dash)
        names = sorted((s.first_name, s.last_initial, s.parent_email, s.parent_phone) for s in self.f.sellers.all())
        self.assertEqual(names, [("Ava", "B", "b@example.com", ""), ("Jake", "S", "erin@example.com", "574-555-0101"),
                                 ("Maria", "L", "", ""), ("Theo", "", "theo@example.com", "")])
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["erin@example.com", "theo@example.com"])
        # posting the preview again doesn't add them twice
        self.client.post(reverse("web:seller_import", args=[self.f.token]), {"email": "1"})
        self.assertEqual(self.f.sellers.count(), 4)

    def test_excel_upload_from_the_template(self):
        import io
        from openpyxl import load_workbook
        r = self.client.get(reverse("web:import_template", args=[self.f.token]))
        wb = load_workbook(io.BytesIO(r.content))
        ws = wb.active
        ws.append(["Mia", "Jones", "Pat Jones", "pat@example.com", "5745550199", 25])
        buf = io.BytesIO()
        wb.save(buf)
        self._upload("Sellers.xlsx", buf.getvalue())
        self.client.post(reverse("web:seller_import", args=[self.f.token]), {})  # no email box ticked
        got = {s.first_name: s for s in self.f.sellers.all()}
        self.assertEqual(set(got), {"Jake", "Mia"})
        self.assertEqual((got["Mia"].goal, got["Mia"].last_initial, got["Mia"].parent_phone), (25, "J", "574-555-0199"))
        self.assertEqual(len(mail.outbox), 0)

    def test_bad_files_are_explained(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        r = self.client.post(self.dash, {"action": "upload", "file": SimpleUploadedFile("x.csv", b"Color,Size\nred,big\n")},
                             follow=True)
        self.assertContains(r, "couldn&#x27;t find a seller name column")
        r = self.client.post(self.dash, {"action": "upload", "file": SimpleUploadedFile("old.xls", b"\xd0\xcf\x11\xe0junk")},
                             follow=True)
        self.assertContains(r, "Save As")

    def test_group_message_goes_to_each_family_with_their_own_links(self):
        from .models import Seller
        a = Seller.objects.create(fundraiser=self.f, first_name="Jake", parent_email="amy@example.com")
        b = Seller.objects.create(fundraiser=self.f, first_name="Mia", parent_email="pat@example.com")
        Seller.objects.create(fundraiser=self.f, first_name="NoEmail")
        page = self.client.get(self.dash)
        self.assertContains(page, "Pickup reminder")
        self.assertContains(page, "Send to 2 families")
        self.client.post(self.dash, {"action": "message", "subject": "Pickup Friday", "message": "Bring a cooler."})
        by = {m.to[0]: m for m in mail.outbox}
        self.assertEqual(set(by), {"amy@example.com", "pat@example.com"})
        self.assertIn(reverse("web:order_page", args=[a.code]), by["amy@example.com"].body)
        self.assertNotIn(reverse("web:order_page", args=[b.code]), by["amy@example.com"].body)
        self.assertEqual(by["pat@example.com"].reply_to, ["kim@example.com"])
        self.assertContains(self.client.get(self.dash), '"Pickup Friday" to 2')

    def test_resend_one_link_and_coordinator_welcome(self):
        from .models import Seller
        s = Seller.objects.create(fundraiser=self.f, first_name="Jake", parent_email="amy@example.com")
        self.client.post(self.dash, {"action": "email_seller", "seller": s.pk})
        self.assertEqual(mail.outbox[-1].to, ["amy@example.com"])
        from . import emails
        e = emails.coordinator_welcome(self.f, "https://roundbellyspizza.com")
        self.assertEqual(e.status, "sent")
        self.assertIn(f"https://roundbellyspizza.com/group/{self.f.token}/", mail.outbox[-1].body)

    def test_demo_never_sends_but_logs(self):
        from .models import Seller
        self.f.is_demo = True
        self.f.save()
        Seller.objects.create(fundraiser=self.f, first_name="Jake", parent_email="amy@example.com")
        r = self.client.post(self.dash, {"action": "message", "subject": "Hi", "message": "Hello"}, follow=True)
        self.assertContains(r, "Nothing was sent")
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.f.emails.get().status, "demo")

    @override_settings(EMAIL_BACKEND="web.tests.BrokenBackend")
    def test_failed_email_never_breaks_the_signup(self):
        r = self.client.post(reverse("web:join", args=[self.f.join_code]), {
            "first_name": "jake", "parent_name": "Amy", "parent_email": "amy@example.com", "goal": "10", "website": ""})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.f.emails.get().status, "failed")


from django.core.mail.backends.base import BaseEmailBackend  # noqa: E402


class BrokenBackend(BaseEmailBackend):
    def send_messages(self, messages):
        raise OSError("mail server down")
