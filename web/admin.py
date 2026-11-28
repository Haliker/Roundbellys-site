from datetime import timedelta

from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (Booking, CateringRequest, ContactMessage, Fundraiser, FundraiserInquiry, Order, OrderLine, Seller,
                     SiteSettings, Testimonial)


class UpcomingFilter(admin.SimpleListFilter):
    title = "when"
    parameter_name = "when"

    def lookups(self, request, model_admin):
        return [("upcoming", "Upcoming"), ("past", "Past")]

    def queryset(self, request, qs):
        today = timezone.localdate()
        if self.value() == "upcoming":
            return qs.filter(date__gte=today)
        if self.value() == "past":
            return qs.filter(date__lt=today).order_by("-date")
        return qs


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["date", "start_time", "end_time", "title", "kind", "address", "cancelled"]
    list_filter = [UpcomingFilter, "kind", "cancelled"]
    search_fields = ["title", "venue", "address", "notes"]
    date_hierarchy = "date"
    fieldsets = [
        (None, {"fields": ["kind", "title", "date", ("start_time", "end_time"), "venue", "address"]}),
        ("Shown on the website (public events only)", {"fields": ["description", "link"]}),
        ("Office only", {"fields": ["cancelled", "from_request", "notes"]}),
    ]
    raw_id_fields = ["from_request"]

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        data.setdefault("kind", request.GET.get("kind", Booking.PUBLIC))
        return data


@admin.action(description="Book these dates on the calendar (private catering)")
def book_dates(modeladmin, request, queryset):
    made = 0
    for r in queryset:
        if r.bookings.exists():
            continue
        start = r.start_time
        hours = 2 if r.style == "truck" else 3
        end_h = min(23, start.hour + hours + (r.extra_hours or 0))
        Booking.objects.create(kind=Booking.PRIVATE, title=f"{r.name} - {r.event_type}", date=r.event_date,
                               start_time=start, end_time=start.replace(hour=end_h), venue=r.venue,
                               address=r.address, from_request=r)
        r.status = CateringRequest.BOOKED
        r.save(update_fields=["status"])
        made += 1
    messages.success(request, f"{made} date(s) booked. They now show as taken on the quote form.")


@admin.register(CateringRequest)
class CateringRequestAdmin(admin.ModelAdmin):
    list_display = ["created", "name", "event_type", "event_date", "guests", "style_label", "est_total", "status",
                    "wants_tasting", "date_was_booked"]
    list_editable = ["status"]
    list_filter = ["status", "style", "wants_tasting", "event_type"]
    search_fields = ["name", "email", "phone", "address", "venue", "message"]
    date_hierarchy = "event_date"
    actions = [book_dates]
    readonly_fields = ["created", "est_total", "est_deposit", "minimum_applied", "date_was_booked", "addon_list", "synced_at"]
    fieldsets = [
        ("Status", {"fields": ["status", "office_notes"]}),
        ("Contact", {"fields": ["name", "phone", "email"]}),
        ("Event", {"fields": ["event_type", "event_date", "start_time", "venue", "address", "date_was_booked"]}),
        ("What they picked", {"fields": ["style", "guests", "addon_list", "extra_hours", "est_total", "est_deposit",
                                         "minimum_applied"]}),
        ("Their answers", {"fields": ["had_pizza", "venue_ok", "wants_tasting", "tasting_when", "message"]}),
        ("Record", {"fields": ["created", "synced_at"]}),
    ]

    @admin.display(description="style")
    def style_label(self, obj):
        return obj.style_name

    @admin.display(description="add-ons")
    def addon_list(self, obj):
        return ", ".join(obj.addon_names) or "None"


@admin.action(description="Set up a fundraiser from this application")
def make_fundraiser(modeladmin, request, queryset):
    made = []
    for q in queryset:
        if Fundraiser.objects.filter(inquiry=q).exists():
            continue
        start = q.start_date or timezone.localdate() + timedelta(days=7)
        f = Fundraiser.objects.create(
            inquiry=q, group=q.group, organization=q.organization, coordinator=q.name, coordinator_email=q.email,
            coordinator_phone=q.phone, sale_start=start, sale_end=start + timedelta(days=13),
            delivery_address=q.delivery_address, color1=q.color1 or "#14284b", color2=q.color2 or "#f2a900")
        q.status = FundraiserInquiry.APPROVED
        q.save(update_fields=["status"])
        made.append(f)
    if made:
        messages.success(request, f"Set up {len(made)} fundraiser(s). Open each one to check the dates, then send the "
                                  "coordinator their dashboard link.")


@admin.register(FundraiserInquiry)
class FundraiserInquiryAdmin(admin.ModelAdmin):
    actions = [make_fundraiser]
    list_display = ["created", "group", "organization", "name", "phone", "sellers", "start_date", "status"]
    list_editable = ["status"]
    list_filter = ["status"]
    search_fields = ["group", "organization", "name", "email", "phone"]


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["created", "topic", "name", "email", "phone", "business", "handled"]
    list_editable = ["handled"]
    list_filter = ["topic", "handled"]
    search_fields = ["name", "email", "business", "message"]


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "page", "show", "quote"]
    list_editable = ["show"]
    list_filter = ["page", "show"]


class SellerInline(admin.TabularInline):
    model = Seller
    extra = 0
    fields = ["first_name", "last_initial", "parent_name", "parent_email", "parent_phone", "goal", "active", "code"]
    readonly_fields = ["code"]


@admin.register(Fundraiser)
class FundraiserAdmin(admin.ModelAdmin):
    list_display = ["group", "organization", "status", "sale_start", "sale_end", "is_demo", "dashboard"]
    list_filter = ["status", "is_demo"]
    search_fields = ["group", "organization", "coordinator", "coordinator_email"]
    inlines = [SellerInline]
    readonly_fields = ["links", "money", "join_code", "created"]
    fieldsets = [
        ("Links to send", {"fields": ["links"]}),
        ("Group", {"fields": ["status", "group", "organization", "is_demo", ("color1", "color2")]}),
        ("Coordinator", {"fields": ["coordinator", "coordinator_email", "coordinator_phone"]}),
        ("Dates and delivery", {"fields": [("sale_start", "sale_end"), ("pickup_date", "pickup_time"), "pickup_place",
                                           "delivery_address", "party_goal"]}),
        ("Totals so far", {"fields": ["money"]}),
        ("Record", {"fields": ["join_code", "created"]}),
    ]

    @admin.display(description="dashboard")
    def dashboard(self, obj):
        return format_html('<a href="{}" target="_blank">Open</a>', reverse("web:coordinator", args=[obj.token]))

    @admin.display(description="links")
    def links(self, obj):
        if not obj.pk:
            return "Save first."
        return format_html(
            '<p><b>Coordinator dashboard</b> (send only to the coordinator - it is their private page):<br>'
            '<a href="{0}" target="_blank">{0}</a></p><p><b>Seller sign-up link</b> (coordinator shares it with families):'
            '<br><a href="{1}" target="_blank">{1}</a></p><p><a href="{2}" target="_blank">Packing sheet</a> &nbsp; '
            '<a href="{3}" target="_blank">All flyers (PDF)</a></p>',
            reverse("web:coordinator", args=[obj.token]), reverse("web:join", args=[obj.join_code]),
            reverse("web:packing", args=[obj.token]), reverse("web:all_flyers", args=[obj.token]))

    @admin.display(description="totals")
    def money(self, obj):
        if not obj.pk:
            return "-"
        t = obj.totals()
        return format_html("{} pizzas, ${} sales. Team keeps ${}. Roundbelly's 60%: ${}; card orders credited ${}; "
                           "balance at delivery ${}.", t["pizzas"], f"{t['sales']:,.2f}", f"{t['share']:,.2f}",
                           f"{t['invoice']:,.2f}", f"{t['credit']:,.2f}", f"{t['balance']:,.2f}")


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["created", "fundraiser", "seller", "buyer_name", "pizzas", "total", "payment", "collected", "how"]
    list_filter = ["fundraiser", "payment", "collected", "how"]
    search_fields = ["buyer_name", "buyer_phone", "buyer_email", "seller__first_name"]
    inlines = [OrderLineInline]
