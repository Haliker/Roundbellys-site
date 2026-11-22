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
