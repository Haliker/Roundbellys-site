from django.db import models
from django.utils import timezone


class SiteSettings(models.Model):
    """One row. Things Adam may want to change without a code update."""
    program_name = models.CharField("fundraising program name", max_length=60, default="Raise the Dough",
                                    help_text="Shown on the website. Never used in links or QR codes, so renaming is safe.")
    phone = models.CharField(max_length=30, default="574-309-6230")
    email = models.EmailField(default="adam@roundbellyspizza.com")
    address = models.CharField(max_length=200, default="20950 West Ireland Road, South Bend, IN 46614")
    tasting_place = models.CharField(max_length=100, default="Slice and Dice Game Cafe")
    tasting_days = models.CharField(max_length=100, default="Sundays, Mondays and Tuesdays")
    service_area = models.CharField(max_length=200, default="within about 75 minutes of South Bend")
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "Website settings"

    def __str__(self):
        return "Website settings"

    @classmethod
    def get(cls):
        obj = cls.objects.first()
        return obj or cls.objects.create()


class Booking(models.Model):
    """Everything on the Bus's calendar. Public events show on the Events page; private catering only blocks the date."""
    PUBLIC, PRIVATE = "public", "private"
    KINDS = [(PUBLIC, "Public event (shows on the website)"), (PRIVATE, "Private catering (date shows as booked only)")]
    kind = models.CharField(max_length=10, choices=KINDS, default=PUBLIC)
    title = models.CharField(max_length=120, help_text="Public events: what people will see, e.g. 'Mishawaka Fall Festival'.")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    venue = models.CharField("place name", max_length=120, blank=True)
    address = models.CharField(max_length=200, help_text="Street, city - used for directions.")
    description = models.TextField(blank=True, help_text="Public events only: a line or two shown on the website.")
    link = models.URLField(blank=True, help_text="Optional: the event's own page.")
    cancelled = models.BooleanField(default=False)
    from_request = models.ForeignKey("CateringRequest", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="bookings")
    notes = models.TextField("office notes", blank=True, help_text="Never shown on the website.")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "start_time"]
        verbose_name = "booking / event"
        verbose_name_plural = "Bookings & events"

    def __str__(self):
        return f"{self.date:%b %-d, %Y} - {self.title}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time has to be after the start time."})

    @classmethod
    def upcoming_public(cls):
        return cls.objects.filter(kind=cls.PUBLIC, cancelled=False, date__gte=timezone.localdate())

    @classmethod
    def booked_on(cls, day):
        return cls.objects.filter(date=day, cancelled=False).exists()


class CateringRequest(models.Model):
    NEW, CONTACTED, TASTING, QUOTED, BOOKED, LOST = "new", "contacted", "tasting", "quoted", "booked", "lost"
    STATUSES = [(NEW, "New"), (CONTACTED, "Contacted"), (TASTING, "Tasting set"), (QUOTED, "Quote sent"),
                (BOOKED, "Booked"), (LOST, "Not going ahead")]
    YES_NO = [("yes", "Yes"), ("no", "No")]
    VENUE = [("yes", "Yes"), ("no", "No"), ("unsure", "Not sure")]

    status = models.CharField(max_length=12, choices=STATUSES, default=NEW)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    event_type = models.CharField(max_length=60)
    event_date = models.DateField()
    start_time = models.TimeField()
    venue = models.CharField("place name", max_length=120, blank=True)
    address = models.CharField(max_length=200)
    style = models.CharField(max_length=10)
    guests = models.PositiveIntegerField()
    addons = models.JSONField(default=list, blank=True)
    extra_hours = models.PositiveSmallIntegerField(default=0)
    had_pizza = models.CharField("had our pizza before?", max_length=5, choices=YES_NO)
    venue_ok = models.CharField("venue meets the Bus's needs?", max_length=8, choices=VENUE)
    wants_tasting = models.BooleanField(default=False)
    tasting_when = models.CharField("good tasting days/times", max_length=120, blank=True)
    message = models.TextField(blank=True)
    # The estimate as shown when they sent it (worked out on the server)
    est_total = models.DecimalField(max_digits=10, decimal_places=2)
    est_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_applied = models.BooleanField(default=False)
    date_was_booked = models.BooleanField(default=False, help_text="Something was already on the calendar that day.")
    office_notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    synced_at = models.DateTimeField(null=True, blank=True, help_text="When the ERP picked it up (later stage).")

    class Meta:
        ordering = ["-created"]
        verbose_name = "catering request"

    def __str__(self):
        return f"{self.name} - {self.event_type} {self.event_date:%b %-d, %Y} ({self.guests} guests)"

    @property
    def style_name(self):
        from .pricing import STYLES
        return STYLES.get(self.style, {}).get("name", self.style)

    @property
    def addon_names(self):
        from .pricing import ADDONS
        return [ADDONS[k]["name"] for k in self.addons if k in ADDONS]


class FundraiserInquiry(models.Model):
    NEW, CONTACTED, APPROVED, DECLINED = "new", "contacted", "approved", "declined"
    STATUSES = [(NEW, "New"), (CONTACTED, "Contacted"), (APPROVED, "Approved"), (DECLINED, "Not a fit")]
    status = models.CharField(max_length=10, choices=STATUSES, default=NEW)
    group = models.CharField("group or team", max_length=120)
    organization = models.CharField("school / club / church", max_length=120, blank=True)
    name = models.CharField("coordinator", max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    sellers = models.PositiveIntegerField("about how many sellers")
    start_date = models.DateField("when you'd like the sale to start", null=True, blank=True)
    delivery_address = models.CharField("where we'd deliver", max_length=200, blank=True)
    color1 = models.CharField("team color 1", max_length=7, blank=True)
    color2 = models.CharField("team color 2", max_length=7, blank=True)
    message = models.TextField(blank=True)
    office_notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "fundraiser application"

    def __str__(self):
        return f"{self.group} ({self.name})"


class ContactMessage(models.Model):
    TOPICS = [("general", "General question"), ("catering", "Catering"), ("fundraising", "Fundraising"),
              ("wholesale", "Wholesale / stocking our pizza"), ("event", "Have the Bus at a public event")]
    topic = models.CharField(max_length=12, choices=TOPICS, default="general")
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    business = models.CharField("business name", max_length=120, blank=True)
    message = models.TextField()
    handled = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.get_topic_display()}: {self.name}"


class Testimonial(models.Model):
    """Quotes from happy customers. Nothing shows until 'show' is ticked (get their OK first)."""
    PAGES = [("fundraising", "Fundraising page"), ("catering", "Catering page"), ("home", "Home page")]
    quote = models.TextField(help_text="Keep it short - one or two sentences, their exact words.")
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, blank=True, help_text="e.g. Principal")
    organization = models.CharField(max_length=120, blank=True, help_text="e.g. Middlebury Elementary School")
    page = models.CharField(max_length=12, choices=PAGES, default="fundraising")
    show = models.BooleanField("show on the website", default=False,
                               help_text="Only tick this once they've said it's OK to use their words and name.")
    permission_note = models.CharField(max_length=200, blank=True, help_text="Who said OK and when (office only).")
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort", "id"]

    def __str__(self):
        return f"{self.name}: {self.quote[:50]}"

    @property
    def credit(self):
        return ", ".join(x for x in [self.name, self.role, self.organization] if x)


# ---------------------------------------------------------------- Fundraisers (Stage 3)
import secrets
from decimal import Decimal

CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I - easy to read off a flyer


def new_code(n=5):
    return "".join(secrets.choice(CODE_LETTERS) for _ in range(n))


def new_token():
    return secrets.token_urlsafe(18)


class Fundraiser(models.Model):
    """One group's sale. Coordinators manage it through a private link - no passwords to remember."""
    SETUP, OPEN, CLOSED, DELIVERED = "setup", "open", "closed", "delivered"
    STATUSES = [(SETUP, "Getting ready"), (OPEN, "Selling"), (CLOSED, "Sale closed - making pizzas"),
                (DELIVERED, "Delivered and settled")]
    status = models.CharField(max_length=10, choices=STATUSES, default=SETUP)
    group = models.CharField("group or team", max_length=120)
    organization = models.CharField("school / club / church", max_length=120, blank=True)
    inquiry = models.ForeignKey("FundraiserInquiry", null=True, blank=True, on_delete=models.SET_NULL)
    coordinator = models.CharField("coordinator name", max_length=100)
    coordinator_email = models.EmailField()
    coordinator_phone = models.CharField(max_length=30, blank=True)
    sale_start = models.DateField()
    sale_end = models.DateField(help_text="Last day to order.")
    pickup_date = models.DateField(null=True, blank=True, help_text="When the pizzas get handed out (shows on flyers).")
    pickup_time = models.CharField(max_length=60, blank=True, help_text="e.g. 3:00 - 5:00 PM")
    pickup_place = models.CharField(max_length=160, blank=True, help_text="Where buyers get their pizzas (shows on flyers).")
    delivery_address = models.CharField("where we deliver", max_length=200, blank=True)
    party_goal = models.PositiveIntegerField("pizza party goal (pizzas)", null=True, blank=True,
                                             help_text="Leave blank if this sale doesn't have a party goal.")
    color1 = models.CharField("team color 1", max_length=7, default="#14284b")
    color2 = models.CharField("team color 2", max_length=7, default="#f2a900")
    join_code = models.CharField(max_length=8, unique=True, default=new_code)
    token = models.CharField("coordinator link key", max_length=40, unique=True, default=new_token)
    is_demo = models.BooleanField(default=False, help_text="Demo fundraisers show a DEMO banner and take no real money.")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sale_start"]

    def __str__(self):
        return f"{self.group} ({self.sale_start:%b %Y})"

    @property
    def ink_on_color1(self):
        """Black or white text, whichever reads better on team color 1."""
        h = (self.color1 or "#14284b").lstrip("#")
        try:
            r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        except ValueError:
            return "#ffffff"
        lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
        lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
        return "#1b1714" if lum > 0.4 else "#ffffff"

    @property
    def taking_orders(self):
        """Orders only once the coordinator has opened the sale, until the last day."""
        from django.utils import timezone
        return self.status == self.OPEN and timezone.localdate() <= self.sale_end

    @property
    def can_join(self):
        """Families can sign up sellers while the sale is being set up and while it's open."""
        from django.utils import timezone
        return self.status in (self.SETUP, self.OPEN) and timezone.localdate() <= self.sale_end

    def lines(self):
        return OrderLine.objects.filter(order__fundraiser=self)

    def totals(self):
        from django.db.models import Count, Sum
        orders = self.orders.all()
        agg = orders.aggregate(sales=Sum("total"), pizzas=Sum("pizzas"), n=Count("id"))
        sales = agg["sales"] or Decimal("0")
        card = orders.filter(payment=Order.CARD).aggregate(s=Sum("total"))["s"] or Decimal("0")
        uncollected = orders.filter(collected=False).aggregate(s=Sum("total"))["s"] or Decimal("0")
        share = (sales * Decimal("0.40")).quantize(Decimal("0.01"))
        invoice = (sales * Decimal("0.60")).quantize(Decimal("0.01"))
        credit = (card * Decimal("0.97")).quantize(Decimal("0.01"))
        return {"sales": sales, "pizzas": agg["pizzas"] or 0, "orders": agg["n"], "card": card,
                "cash_check": sales - card, "uncollected": uncollected, "share": share, "invoice": invoice,
                "credit": credit, "balance": invoice - credit, "card_fee": card - credit,
                "sellers": self.sellers.filter(active=True).count()}


class Seller(models.Model):
    """A kid (or adult) selling. Public pages show first name + last initial only."""
    fundraiser = models.ForeignKey(Fundraiser, on_delete=models.CASCADE, related_name="sellers")
    first_name = models.CharField(max_length=40)
    last_initial = models.CharField(max_length=1, blank=True)
    parent_name = models.CharField("parent / guardian", max_length=100, blank=True)
    parent_email = models.EmailField(blank=True)
    parent_phone = models.CharField(max_length=30, blank=True)
    goal = models.PositiveSmallIntegerField("personal goal (pizzas)", default=10)
    code = models.CharField(max_length=8, unique=True, default=new_code, help_text="In their public order link.")
    token = models.CharField(max_length=40, unique=True, default=new_token, help_text="Their private seller page key.")
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["first_name", "last_initial"]

    def __str__(self):
        return self.display

    @property
    def display(self):
        return f"{self.first_name} {self.last_initial}." if self.last_initial else self.first_name

    def sold(self):
        from django.db.models import Sum
        a = self.orders.aggregate(p=Sum("pizzas"), s=Sum("total"))
        return {"pizzas": a["p"] or 0, "sales": a["s"] or Decimal("0")}


class Order(models.Model):
    CASH, CHECK, CARD, LATER = "cash", "check", "card", "later"
    PAYMENTS = [(CASH, "Cash to the seller"), (CHECK, "Check to the seller"), (CARD, "Card online"),
                (LATER, "Will pay the seller")]
    ONLINE, LOGGED = "online", "logged"
    fundraiser = models.ForeignKey(Fundraiser, on_delete=models.CASCADE, related_name="orders")
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name="orders")
    how = models.CharField(max_length=8, choices=[(ONLINE, "Buyer ordered online"), (LOGGED, "Seller entered it")], default=LOGGED)
    buyer_name = models.CharField(max_length=100)
    buyer_phone = models.CharField(max_length=30, blank=True)
    buyer_email = models.EmailField(blank=True)
    payment = models.CharField(max_length=6, choices=PAYMENTS, default=CASH)
    collected = models.BooleanField("money collected", default=False)
    pizzas = models.PositiveIntegerField(default=0)
    total = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    note = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.buyer_name} - {self.pizzas} pizzas (${self.total})"


class OrderLine(models.Model):
    SIZES = [("10", '10"'), ("12", '12"'), ("gf", 'Gluten-free 12"')]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    flavor = models.CharField(max_length=20)
    size = models.CharField(max_length=2, choices=SIZES)
    qty = models.PositiveSmallIntegerField()
    unit_price = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        ordering = ["id"]

    @property
    def line_total(self):
        return self.unit_price * self.qty

    @property
    def flavor_name(self):
        from .content import FLAVORS
        return next((f["name"] for f in FLAVORS if f["slug"] == self.flavor), self.flavor)


class EmailLog(models.Model):
    """Every email the website sends (or would send, on the demo). Office: Emails sent."""
    WAITING, SENT, FAILED, DEMO = "waiting", "sent", "failed", "demo"
    STATUSES = [(WAITING, "Sending"), (SENT, "Sent"), (FAILED, "Failed"), (DEMO, "Demo - not sent")]
    KINDS = [("seller_welcome", "Seller page link to parent"), ("order_receipt", "Order receipt to buyer"),
             ("seller_new_order", "New order note to parent"), ("coordinator_welcome", "Dashboard link to coordinator"),
             ("group_message", "Coordinator message to families")]
    kind = models.CharField(max_length=24, choices=KINDS)
    to = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    fundraiser = models.ForeignKey(Fundraiser, null=True, blank=True, on_delete=models.SET_NULL, related_name="emails")
    status = models.CharField(max_length=8, choices=STATUSES, default=WAITING)
    error = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.subject} -> {self.to}"
