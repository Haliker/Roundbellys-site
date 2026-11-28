"""Fundraiser emails: seller links to parents, buyer receipts, new-order notes, coordinator links, group messages.

Every email is written to EmailLog (office: Back office -> Emails sent) with its text, so the office can see what
went out, what failed and - on the demo fundraiser - what WOULD have gone out (demo emails are never sent).
A failed email never stops the page that triggered it.
"""
import html as htmllib
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.urls import reverse

from .models import EmailLog, SiteSettings

log = logging.getLogger(__name__)


def base_url(request=None):
    """Links in emails: SITE_URL when set (e.g. https://roundbellyspizza.com), else the address being used now."""
    if getattr(settings, "SITE_URL", ""):
        return settings.SITE_URL.rstrip("/")
    if request is not None:
        return f"{request.scheme}://{request.get_host()}"
    return "https://roundbellyspizza.com"


def url(base, name, *args):
    return base + reverse(name, args=args)


def _render(kind, ctx):
    ctx = {"site": SiteSettings.get(), **ctx}
    # plain-text parts: undo the HTML escaping templates do (Roundbelly&#x27;s -> Roundbelly's)
    subject = htmllib.unescape(" ".join(render_to_string(f"web/email/{kind}_subject.txt", ctx).split()))
    text = htmllib.unescape(render_to_string(f"web/email/{kind}.txt", ctx)).strip() + "\n"
    html = render_to_string(f"web/email/{kind}.html", ctx)
    return subject, text, html


def _deliver(entries, connection=None):
    """entries = [(EmailLog, html, reply_to)]. Sends and records the result on each log row."""
    try:
        conn = connection or get_connection()
        conn.open()
    except Exception as e:  # noqa: BLE001
        log.exception("Email connection failed")
        for e_log, _h, _r in entries:
            e_log.status, e_log.error = EmailLog.FAILED, f"Couldn't connect to the mail server: {e}"[:300]
            e_log.save(update_fields=["status", "error"])
        return
    try:
        for e_log, html, reply_to in entries:
            msg = EmailMultiAlternatives(e_log.subject, e_log.body, settings.DEFAULT_FROM_EMAIL, [e_log.to],
                                         reply_to=[reply_to] if reply_to else None, connection=conn)
            msg.attach_alternative(html, "text/html")
            try:
                msg.send()
                e_log.status = EmailLog.SENT
            except Exception as e:  # noqa: BLE001
                log.exception("Email to %s failed", e_log.to)
                e_log.status, e_log.error = EmailLog.FAILED, str(e)[:300]
            e_log.save(update_fields=["status", "error"])
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def _prepare(kind, to, ctx, fundraiser=None, reply_to=""):
    subject, text, html = _render(kind, ctx)
    demo = bool(fundraiser and fundraiser.is_demo)
    e_log = EmailLog.objects.create(kind=kind, to=to, subject=subject, body=text, fundraiser=fundraiser,
                                    status=EmailLog.DEMO if demo else EmailLog.WAITING)
    return e_log, html, reply_to, demo


def send(kind, to, ctx, fundraiser=None, reply_to=""):
    """One email, sent now. Returns the EmailLog row (status sent / failed / demo)."""
    if not to:
        return None
    e_log, html, reply_to, demo = _prepare(kind, to, ctx, fundraiser, reply_to)
    if not demo:
        _deliver([(e_log, html, reply_to)])
    return e_log


def send_many(kind, items, fundraiser=None, reply_to=""):
    """items = [(to, ctx)]. Prepared now (so the log shows them right away), sent in the background so a big group
    doesn't make the page wait. Returns how many will go out."""
    entries = []
    for to, ctx in items:
        e_log, html, rt, demo = _prepare(kind, to, ctx, fundraiser, reply_to)
        if not demo:
            entries.append((e_log, html, rt))
    if entries:
        if getattr(settings, "EMAIL_IN_BACKGROUND", True):
            threading.Thread(target=_deliver, args=(entries,), daemon=True).start()
        else:
            _deliver(entries)
    return len(items)


# ---------------------------------------------------------------- the messages
def _seller_ctx(base, seller):
    f = seller.fundraiser
    return {"f": f, "seller": seller,
            "seller_link": url(base, "web:seller_home", seller.token),
            "order_link": url(base, "web:order_page", seller.code),
            "flyer_link": url(base, "web:seller_flyer", seller.token)}


def seller_welcome(seller, base):
    """To the parent: their seller's private page, order link and flyer."""
    if not seller.parent_email:
        return None
    return send("seller_welcome", seller.parent_email, _seller_ctx(base, seller), seller.fundraiser,
                reply_to=seller.fundraiser.coordinator_email)


def order_emails(order, base):
    """Receipt to the buyer (when they gave an email) + a heads-up to the seller's parent for online orders."""
    seller, f = order.seller, order.fundraiser
    ctx = {**_seller_ctx(base, seller), "order": order, "lines": list(order.lines.all())}
    if order.buyer_email:
        send("order_receipt", order.buyer_email, ctx, f, reply_to=seller.parent_email or f.coordinator_email)
    if order.how == order.ONLINE and seller.parent_email:
        send("seller_new_order", seller.parent_email, ctx, f, reply_to=order.buyer_email or "")


def coordinator_welcome(f, base):
    return send("coordinator_welcome", f.coordinator_email, {
        "f": f, "dashboard_link": url(base, "web:coordinator", f.token), "join_link": url(base, "web:join", f.join_code),
    }, f, reply_to=settings.OFFICE_EMAIL)


def group_message(f, base, subject, message):
    """Coordinator -> every family with an email. One email per seller (no one sees anyone else's address), each with
    that seller's own links. Families with two sellers get one email per seller."""
    items = []
    for s in f.sellers.filter(active=True).exclude(parent_email=""):
        items.append((s.parent_email, {**_seller_ctx(base, s), "subject": subject, "message": message}))
    return send_many("group_message", items, f, reply_to=f.coordinator_email)


def presets(f, base):
    """Ready-made group messages the coordinator can pick and edit."""
    from django.utils.dateformat import format as df
    end = df(f.sale_end, "l, F j")
    pickup = ""
    if f.pickup_date:
        pickup = df(f.pickup_date, "l, F j") + (f" from {f.pickup_time}" if f.pickup_time else "")
        if f.pickup_place:
            pickup += f" at {f.pickup_place}"
    return [
        {"key": "open", "label": "The sale is open",
         "subject": f"{f.group} pizza sale is open",
         "message": f"Our Roundbelly's pizza sale is open! The last day to order is {end}.\n\n"
                    "Share your seller's order link (below) with family and friends - text it, email it, or post it. "
                    "Print the flyer for anyone who'd rather order on paper.\n\nThank you for helping!"},
        {"key": "last", "label": "Last few days",
         "subject": f"Last few days of the {f.group} pizza sale",
         "message": f"Just a reminder: the last day to order pizzas is {end}.\n\nNow is a great time to send the order "
                    "link one more time to anyone who hasn't ordered yet. Please make sure any paper orders are "
                    "entered on your seller page by then.\n\nThank you!"},
        {"key": "pickup", "label": "Pickup reminder",
         "subject": f"Pizza pickup for {f.group}",
         "message": (f"Your pizzas are coming! Pickup is {pickup}.\n\n" if pickup else "Your pizzas are coming!\n\n")
                    + "Your seller's pizzas will be boxed together with their name on them. They are frozen, so please "
                    "bring a cooler or come straight home, and hand them out to your buyers soon.\n\nYour seller page "
                    "shows who still needs to pay you.\n\nThank you for a great sale!"},
    ]
