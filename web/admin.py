from django.contrib import admin, messages
from django.utils import timezone

from .models import Booking, CateringRequest, ContactMessage, FundraiserInquiry, SiteSettings


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


@admin.register(FundraiserInquiry)
class FundraiserInquiryAdmin(admin.ModelAdmin):
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
