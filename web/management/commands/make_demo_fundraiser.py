"""Load (or reload) the demo fundraiser used for the How-To Guide and walkthrough video.

    python manage.py make_demo_fundraiser          # makes it if missing
    python manage.py make_demo_fundraiser --reset  # throws the old demo away and makes a fresh one

Everything is made up: the group, sellers, parents (example.com emails, 555 phone numbers) and buyers.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from web import content
from web.models import Fundraiser, Order, OrderLine, Seller

SELLERS = [("Jake", "S", 25), ("Maria", "L", 20), ("Owen", "P", 15), ("Ava", "K", 15), ("Liam", "D", 12),
           ("Sophie", "R", 15), ("Eli", "M", 10), ("Grace", "T", 12), ("Noah", "B", 10), ("Chloe", "W", 10),
           ("Mason", "H", 10), ("Lily", "C", 8), ("Ben", "F", 10), ("Zoe", "N", 10)]
BUYERS = ["Grandma Ruth", "Uncle Dave", "Mrs. Patel", "Coach Miller", "The Hendersons", "Tom (next door)",
          "Aunt Lisa", "Pastor Jim", "Dr. Chen", "The Garcias", "Kelly at the bank", "Mr. Brooks", "Nana Joyce",
          "The Kowalskis", "Shannon R.", "Mike's Auto", "Grandpa Walt", "The Nguyens", "Becky (Mom's work)",
          "Mr. & Mrs. Ortiz", "Jen T.", "The Wilsons", "Carl from church", "Aunt Marie"]
PARENTS = ["Sullivan", "Lopez", "Price", "Kim", "Davis", "Reyes", "Miller", "Thomas", "Baker", "Walsh", "Harris",
           "Cole", "Foster", "Nash"]
DEMO_JOIN = "DEMO"


class Command(BaseCommand):
    help = "Make the demo fundraiser (fake group, sellers and orders)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Replace any existing demo fundraiser.")

    @transaction.atomic
    def handle(self, *args, **opts):
        old = Fundraiser.objects.filter(is_demo=True)
        if old.exists() and not opts["reset"]:
            f = old.first()
            self.stdout.write(f"Demo already there: /group/{f.token}/  (use --reset for a fresh one)")
            return
        for f in old:
            Order.objects.filter(fundraiser=f).delete()
            f.delete()
        rnd = random.Random(2026)
        today = timezone.localdate()
        f = Fundraiser.objects.create(
            status=Fundraiser.OPEN, group="Riverbend Raptors Volleyball", organization="Riverbend Middle School",
            coordinator="Coach Dana Whitfield", coordinator_email="coach.demo@example.com", coordinator_phone="574-555-0100",
            sale_start=today - timedelta(days=6), sale_end=today + timedelta(days=8),
            pickup_date=today + timedelta(days=19), pickup_time="3:30 - 6:00 PM", pickup_place="Riverbend Middle School gym lobby",
            delivery_address="123 Demo Lane, South Bend, IN", party_goal=300, color1="#4b2e83", color2="#fdb927",
            join_code=DEMO_JOIN, is_demo=True)
        flavors = [fl["slug"] for fl in content.FLAVORS]
        weights = [16, 22, 12, 12, 9, 10, 9]  # pepperoni + cheese sell most
        n_orders = 0
        for i, (first, last, goal) in enumerate(SELLERS):
            s = Seller.objects.create(fundraiser=f, first_name=first, last_initial=last, goal=goal,
                                      parent_name=f"{rnd.choice(['Amy', 'Chris', 'Pat', 'Jordan', 'Sam', 'Kate'])} {PARENTS[i]}",
                                      parent_email=f"{PARENTS[i].lower()}.family@example.com",
                                      parent_phone=f"574-555-01{i + 10:02d}")
            for _ in range(rnd.choice([0, 2, 3, 4, 5, 6, 7, 8]) if i else 9):
                lines = {}
                for _ in range(rnd.choice([1, 1, 2, 2, 3, 4])):
                    slug = rnd.choices(flavors, weights)[0]
                    size = rnd.choices(["10", "12", "gf"], [5, 6, 1])[0]
                    lines[(slug, size)] = lines.get((slug, size), 0) + 1
                how = rnd.choice([Order.ONLINE, Order.LOGGED, Order.LOGGED])
                pay = Order.CARD if how == Order.ONLINE and rnd.random() < .6 else rnd.choice([Order.CASH, Order.CHECK, Order.LATER])
                collected = pay == Order.CARD or (pay != Order.LATER and rnd.random() < .8)
                o = Order.objects.create(fundraiser=f, seller=s, how=how, buyer_name=rnd.choice(BUYERS),
                                         buyer_phone=f"574-555-{rnd.randint(200, 999):04d}", payment=pay, collected=collected)
                for (slug, size), q in lines.items():
                    OrderLine.objects.create(order=o, flavor=slug, size=size, qty=q, unit_price=content.price(slug, size))
                o.pizzas = sum(lines.values())
                o.total = sum((Decimal(content.price(sl, sz)) * q for (sl, sz), q in lines.items()), Decimal("0"))
                o.created = timezone.now() - timedelta(days=rnd.randint(0, 5), hours=rnd.randint(0, 10))
                o.save()
                n_orders += 1
        t = f.totals()
        self.stdout.write(self.style.SUCCESS(
            f"Demo fundraiser ready: {f.group}, {len(SELLERS)} sellers, {n_orders} orders, {t['pizzas']} pizzas, "
            f"${t['sales']:,.2f} sales."))
        self.stdout.write(f"  Coordinator dashboard: {reverse('web:coordinator', args=[f.token])}")
        self.stdout.write(f"  Seller sign-up:        {reverse('web:join', args=[f.join_code])}")
        first = f.sellers.order_by("created").first()
        self.stdout.write(f"  {first.display}'s seller page: {reverse('web:seller_home', args=[first.token])}")
        self.stdout.write(f"  {first.display}'s order page:  {reverse('web:order_page', args=[first.code])}")
