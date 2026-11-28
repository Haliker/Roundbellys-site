"""Fundraiser pages: coordinator dashboard, seller sign-up, seller page, public order page, packing sheet.

Nobody here has a password. Each page is reached by a long private link (coordinator / seller) or a short public
code (the seller's order page and the group's join page). Public pages only ever show a seller's first name and
last initial; parent contact details are for the coordinator only.
"""
from decimal import Decimal

import qrcode
import qrcode.image.svg
from django import forms
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe

from . import content, emails
from . import seller_import as imp
from .forms import _phone
from .models import Fundraiser, Order, OrderLine, Seller


def qr_svg(url):
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    svg = img.to_string(encoding="unicode")
    return mark_safe(svg.replace("<svg ", '<svg class="qr" role="img" aria-label="QR code" ', 1))


def _abs(request, name, *args):
    return request.build_absolute_uri(reverse(name, args=args))


def _with_progress(sellers):
    rows = []
    for s in sellers:
        sold = s.sold()
        pct = min(100, round(100 * sold["pizzas"] / s.goal)) if s.goal else 0
        rows.append({"s": s, "pizzas": sold["pizzas"], "sales": sold["sales"], "pct": pct})
    return rows


def _goal_pct(f, pizzas):
    return min(100, round(100 * pizzas / f.party_goal)) if f.party_goal else None


# ------------------------------------------------------------------ forms
class JoinForm(forms.Form):
    first_name = forms.CharField(label="Seller's first name", max_length=40)
    last_initial = forms.CharField(label="First letter of last name", max_length=1, required=False)
    parent_name = forms.CharField(label="Parent or guardian name", max_length=100)
    parent_email = forms.EmailField(label="Parent email", help_text="We'll email you your seller's page. Only used for this fundraiser.")
    parent_phone = forms.CharField(label="Parent phone", max_length=30, required=False)
    goal = forms.IntegerField(label="Personal goal (pizzas)", min_value=1, max_value=200, initial=10)
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def clean_last_initial(self):
        v = (self.cleaned_data.get("last_initial") or "").strip()[:1].upper()
        if v and not v.isalpha():
            raise forms.ValidationError("Just one letter.")
        return v

    def clean_first_name(self):
        return self.cleaned_data["first_name"].strip().title()

    def clean_parent_phone(self):
        v = self.cleaned_data.get("parent_phone")
        return _phone(v) if v else ""


class BuyerForm(forms.Form):
    buyer_name = forms.CharField(label="Buyer's name", max_length=100)
    buyer_phone = forms.CharField(label="Phone", max_length=30, required=False)
    buyer_email = forms.EmailField(label="Email (for a receipt)", required=False)
    payment = forms.ChoiceField(widget=forms.RadioSelect)
    note = forms.CharField(label="Note", max_length=200, required=False)
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def __init__(self, *a, choices=(), **kw):
        super().__init__(*a, **kw)
        self.fields["payment"].choices = choices
        if len(choices) == 1:
            self.fields["payment"].initial = choices[0][0]

    def clean_buyer_phone(self):
        v = self.cleaned_data.get("buyer_phone")
        return _phone(v) if v else ""


def _save_order(f, seller, form, lines, how):
    with transaction.atomic():
        pay = form.cleaned_data["payment"]
        order = Order.objects.create(
            fundraiser=f, seller=seller, how=how, buyer_name=form.cleaned_data["buyer_name"].strip(),
            buyer_phone=form.cleaned_data.get("buyer_phone", ""), buyer_email=form.cleaned_data.get("buyer_email", ""),
            payment=pay, collected=pay in (Order.CASH, Order.CHECK, Order.CARD), note=form.cleaned_data.get("note", ""))
        for slug, size, qty, price in lines:
            OrderLine.objects.create(order=order, flavor=slug, size=size, qty=qty, unit_price=price)
        order.pizzas = sum(q for _, _, q, _ in lines)
        order.total = sum((Decimal(p) * q for _, _, q, p in lines), Decimal("0"))
        order.save(update_fields=["pizzas", "total"])
    return order


# ------------------------------------------------------------------ public order page
def order_page(request, code):
    seller = get_object_or_404(Seller.objects.select_related("fundraiser"), code=code.upper(), active=True)
    f = seller.fundraiser
    choices = [(Order.LATER, f"Pay {seller.first_name} by cash or check when the pizzas arrive")]
    if f.is_demo:
        choices.append((Order.CARD, "Pay by card now (demo: no real charge)"))
    form = BuyerForm(request.POST or None, choices=choices)
    grid_error = None
    if request.method == "POST" and f.taking_orders:
        lines = content.read_grid(request.POST)
        if not lines:
            grid_error = "Pick at least one pizza."
        if form.is_valid() and lines:
            if form.cleaned_data.get("website"):
                return redirect("web:order_thanks", code=seller.code)
            order = _save_order(f, seller, form, lines, Order.ONLINE)
            emails.order_emails(order, emails.base_url(request))
            request.session["last_order"] = order.pk  # only this browser can see the order it just placed
            return redirect("web:order_thanks", code=seller.code)
    return render(request, "web/fr/order.html", {
        "f": f, "seller": seller, "form": form, "grid": content.order_grid(), "grid_error": grid_error,
        "posted": request.POST, "sold": seller.sold(),
    })


def order_thanks(request, code):
    seller = get_object_or_404(Seller.objects.select_related("fundraiser"), code=code.upper())
    order = Order.objects.filter(pk=request.session.get("last_order") or 0, seller=seller).prefetch_related("lines").first()
    return render(request, "web/fr/order_thanks.html", {"f": seller.fundraiser, "seller": seller, "order": order})


# ------------------------------------------------------------------ joining
def join(request, code):
    f = get_object_or_404(Fundraiser, join_code=code.upper())
    form = JoinForm(request.POST or None)
    if request.method == "POST" and f.can_join and form.is_valid():
        if form.cleaned_data.get("website"):
            return redirect("web:join", code=f.join_code)
        d = form.cleaned_data
        s = Seller.objects.create(fundraiser=f, first_name=d["first_name"], last_initial=d["last_initial"],
                                  parent_name=d["parent_name"], parent_email=d["parent_email"],
                                  parent_phone=d["parent_phone"], goal=d["goal"])
        e = emails.seller_welcome(s, emails.base_url(request))
        sent = f"We emailed this page's link to {s.parent_email}." if e and e.status == e.SENT else \
            "Bookmark this page." if not f.is_demo else "Demo: on a real sale we'd email you this page's link."
        messages.success(request, f"{s.first_name} is signed up! {sent} It's {s.first_name}'s own seller page.")
        return redirect("web:seller_home", token=s.token)
    return render(request, "web/fr/join.html", {"f": f, "form": form})


# ------------------------------------------------------------------ seller page (private link)
def seller_home(request, token):
    seller = get_object_or_404(Seller.objects.select_related("fundraiser"), token=token)
    f = seller.fundraiser
    if request.method == "POST" and request.POST.get("action") == "collected":
        o = get_object_or_404(Order, pk=request.POST.get("order"), seller=seller)
        o.collected = request.POST.get("value") == "1"
        if o.collected and o.payment == Order.LATER:
            o.payment = request.POST.get("paid_with") if request.POST.get("paid_with") in (Order.CASH, Order.CHECK) else Order.CASH
        o.save(update_fields=["collected", "payment"])
        return redirect(reverse("web:seller_home", args=[token]) + "#orders")
    link = _abs(request, "web:order_page", seller.code)
    sold = seller.sold()
    orders = seller.orders.prefetch_related("lines")
    owed = sum((o.total for o in orders if not o.collected), Decimal("0"))
    return render(request, "web/fr/seller.html", {
        "f": f, "seller": seller, "link": link, "qr": qr_svg(link), "sold": sold, "orders": orders, "owed": owed,
        "pct": min(100, round(100 * sold["pizzas"] / seller.goal)) if seller.goal else 0,
        "share_text": f"Hi! I'm selling Roundbelly's pizzas for {f.group}. You can order here: {link}",
    })


def seller_log(request, token):
    seller = get_object_or_404(Seller.objects.select_related("fundraiser"), token=token)
    f = seller.fundraiser
    choices = [(Order.CASH, "Paid cash"), (Order.CHECK, "Paid by check"), (Order.LATER, "Will pay later")]
    form = BuyerForm(request.POST or None, choices=choices, initial={"payment": Order.CASH})
    grid_error = None
    if request.method == "POST" and f.taking_orders:
        lines = content.read_grid(request.POST)
        if not lines:
            grid_error = "Pick at least one pizza."
        if form.is_valid() and lines:
            o = _save_order(f, seller, form, lines, Order.LOGGED)
            emails.order_emails(o, emails.base_url(request))
            messages.success(request, f"Saved: {o.buyer_name}, {o.pizzas} pizza{'s' if o.pizzas != 1 else ''}, ${o.total:,.2f}.")
            return redirect("web:seller_home", token=token)
    return render(request, "web/fr/seller_log.html", {"f": f, "seller": seller, "form": form,
                                                       "grid": content.order_grid(), "grid_error": grid_error,
                                                       "posted": request.POST})


# ------------------------------------------------------------------ coordinator dashboard (private link)
def _fundraiser_for(token):
    return get_object_or_404(Fundraiser, token=token)


def coordinator(request, token):
    f = _fundraiser_for(token)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_sellers":
            made = 0
            for raw in (request.POST.get("names") or "").splitlines()[:300]:
                parts = raw.replace(",", " ").split()
                if not parts:
                    continue
                first = parts[0].strip().title()[:40]
                last = parts[1][:1].upper() if len(parts) > 1 and parts[1][:1].isalpha() else ""
                Seller.objects.create(fundraiser=f, first_name=first, last_initial=last)
                made += 1
            messages.success(request, f"Added {made} seller{'s' if made != 1 else ''}.")
        elif action == "open" and f.status == Fundraiser.SETUP:
            f.status = Fundraiser.OPEN
            f.save(update_fields=["status"])
            messages.success(request, "Your sale is open. Sellers can start taking orders.")
        elif action == "close" and f.status in (Fundraiser.SETUP, Fundraiser.OPEN):
            f.status = Fundraiser.CLOSED
            f.save(update_fields=["status"])
            messages.success(request, "Sale closed. We'll start making your pizzas.")
        elif action == "upload":
            up = request.FILES.get("file")
            if not up:
                messages.error(request, "Pick a file first.")
            else:
                try:
                    rows = imp.mark_duplicates(imp.parse(imp.read_rows(up)), f)
                except imp.SellerFileError as e:
                    messages.error(request, str(e))
                else:
                    request.session[f"import_{f.pk}"] = rows
                    return redirect("web:seller_import", token=token)
        elif action == "email_seller":
            s = get_object_or_404(Seller, pk=request.POST.get("seller"), fundraiser=f)
            e = emails.seller_welcome(s, emails.base_url(request))
            _say_sent(request, e, f"{s.display}'s link", s.parent_email)
        elif action == "message":
            subject = (request.POST.get("subject") or "").strip()[:150]
            body = (request.POST.get("message") or "").strip()[:5000]
            if not subject or not body:
                messages.error(request, "Write a subject and a message first.")
            else:
                n = emails.group_message(f, emails.base_url(request), subject, body)
                if not n:
                    messages.error(request, "None of your sellers have a parent email yet.")
                elif f.is_demo:
                    messages.success(request, f"Demo: on a real fundraiser this would email {n} families. Nothing was sent.")
                else:
                    messages.success(request, f"Sending your message to {n} families. Replies come to {f.coordinator_email}.")
        elif action == "seller_off":
            s = get_object_or_404(Seller, pk=request.POST.get("seller"), fundraiser=f)
            if s.orders.exists():
                messages.error(request, f"{s.display} already has orders, so they stay on the list.")
            else:
                s.delete()
                messages.success(request, f"Removed {s.display}.")
        return redirect("web:coordinator", token=token)
    join_link = _abs(request, "web:join", f.join_code)
    t = f.totals()
    with_email = f.sellers.filter(active=True).exclude(parent_email="").count()
    sellers = sorted(_with_progress(f.sellers.filter(active=True)), key=lambda r: (-r["pizzas"], r["s"].first_name))
    return render(request, "web/fr/coordinator.html", {
        "f": f, "t": t, "sellers": sellers, "join_link": join_link, "join_qr": qr_svg(join_link),
        "goal_pct": _goal_pct(f, t["pizzas"]), "recent": f.orders.select_related("seller")[:12],
        "seller_links": [(s, _abs(request, "web:seller_home", s.token)) for s in f.sellers.filter(active=True)],
        "with_email": with_email, "presets": emails.presets(f, emails.base_url(request)),
        "last_messages": _last_messages(f),
    })


def _say_sent(request, e, what, to):
    if e is None:
        messages.error(request, "There's no parent email for that seller.")
    elif e.status == e.DEMO:
        messages.success(request, f"Demo: on a real fundraiser {what} would be emailed to {to}. Nothing was sent.")
    elif e.status == e.FAILED:
        messages.error(request, f"The email to {to} didn't go through. Check the address, or copy the link instead.")
    else:
        messages.success(request, f"Emailed {what} to {to}.")


def _last_messages(f):
    """Group messages sent so far: subject, when, how many families."""
    out = {}
    for e in f.emails.filter(kind="group_message").order_by("-created")[:2000]:
        key = (e.subject, e.created.replace(second=0, microsecond=0))
        out.setdefault(key, 0)
        out[key] += 1
    return [{"subject": k[0], "when": k[1], "n": n} for k, n in list(out.items())[:5]]


def seller_import(request, token):
    """Preview an uploaded seller list, then add them (and email each family their seller's page)."""
    f = _fundraiser_for(token)
    key = f"import_{f.pk}"
    rows = request.session.get(key)
    if not rows:
        return redirect("web:coordinator", token=token)
    if request.method == "POST":
        if request.POST.get("action") == "cancel":
            request.session.pop(key, None)
            return redirect("web:coordinator", token=token)
        if not f.can_join:
            messages.error(request, "This sale has ended, so no more sellers can be added.")
            return redirect("web:coordinator", token=token)
        send = request.POST.get("email") == "1"
        made = []
        with transaction.atomic():
            for r in imp.mark_duplicates([dict(r, problems=list(r["problems"])) for r in rows if r["ok"]], f):
                if not r["ok"]:
                    continue
                made.append(Seller.objects.create(
                    fundraiser=f, first_name=r["first"], last_initial=r["last_initial"], parent_name=r["parent_name"],
                    parent_email=r["parent_email"], parent_phone=r["parent_phone"], goal=r["goal"]))
        request.session.pop(key, None)
        base = emails.base_url(request)
        mailed = [s for s in made if s.parent_email]
        if send and mailed:
            emails.send_many("seller_welcome", [(s.parent_email, emails._seller_ctx(base, s)) for s in mailed], f,
                             reply_to=f.coordinator_email)
        msg = f"Added {len(made)} seller{'s' if len(made) != 1 else ''}."
        if send and mailed:
            msg += (f" Demo: {len(mailed)} welcome emails would go out on a real fundraiser." if f.is_demo
                    else f" Emailing {len(mailed)} families their seller's page now.")
        if len(made) > len(mailed):
            msg += f" {len(made) - len(mailed)} have no parent email - copy their link from the list below."
        messages.success(request, msg)
        return redirect("web:coordinator", token=token)
    good = [r for r in rows if r["ok"]]
    return render(request, "web/fr/import.html", {
        "f": f, "rows": rows, "good": len(good), "skipped": len(rows) - len(good),
        "with_email": sum(1 for r in good if r["parent_email"]),
    })


def import_template(request, token):
    _fundraiser_for(token)
    r = HttpResponse(imp.template_xlsx(),
                     content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r["Content-Disposition"] = 'attachment; filename="Seller list template.xlsx"'
    return r


def packing(request, token):
    """Printable: totals by flavor/size for the kitchen, then one box list per seller with each buyer's pizzas."""
    f = _fundraiser_for(token)
    names = {fl["slug"]: fl["name"] for fl in content.FLAVORS}
    order_of = {fl["slug"]: i for i, fl in enumerate(content.FLAVORS)}
    sizes = dict(content.SIZES)
    totals = {}
    for ln in f.lines():
        totals[(ln.flavor, ln.size)] = totals.get((ln.flavor, ln.size), 0) + ln.qty
    kitchen = [{"flavor": names.get(k[0], k[0]), "size": sizes[k[1]], "qty": v}
               for k, v in sorted(totals.items(), key=lambda kv: (order_of.get(kv[0][0], 99), kv[0][1]))]
    boxes = []
    for s in f.sellers.filter(active=True).prefetch_related("orders__lines"):
        orders = list(s.orders.all())
        if not orders:
            continue
        boxes.append({"seller": s, "orders": orders, "pizzas": sum(o.pizzas for o in orders),
                      "owed": sum((o.total for o in orders if not o.collected), Decimal("0"))})
    return render(request, "web/fr/packing.html", {"f": f, "kitchen": kitchen, "boxes": boxes,
                                                   "total": sum(k["qty"] for k in kitchen)})


# ------------------------------------------------------------------ flyers
def _pdf(data, filename):
    r = HttpResponse(data, content_type="application/pdf")
    r["Content-Disposition"] = f'inline; filename="{filename}"'
    r["Cache-Control"] = "private, no-store"
    return r


def _slug(text):
    return "".join(ch if ch.isalnum() else "-" for ch in text).strip("-")[:40] or "flyer"


def seller_flyer(request, token):
    from .flyer import flyers_pdf
    seller = get_object_or_404(Seller.objects.select_related("fundraiser"), token=token)
    data = flyers_pdf([seller], lambda s: _abs(request, "web:order_page", s.code))
    return _pdf(data, f"Flyer-{_slug(seller.display)}.pdf")


def all_flyers(request, token):
    from .flyer import flyers_pdf
    f = _fundraiser_for(token)
    sellers = f.sellers.filter(active=True).select_related("fundraiser")
    if not sellers.exists():
        messages.error(request, "Add some sellers first - each one gets their own flyer.")
        return redirect("web:coordinator", token=token)
    data = flyers_pdf(sellers, lambda s: _abs(request, "web:order_page", s.code))
    return _pdf(data, f"Flyers-{_slug(f.group)}.pdf")
