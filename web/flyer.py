"""Seller flyers (PDF): the "Raise the Dough" layout, filled in for one seller, in the team's colors.

Front: menu with photos and prices, the seller's name, their QR code (their own order page), pickup details.
Back: paper order form for cash / check buyers, labeled with the seller and group.
Ported from the flyer prototype (Nov 22 2026). Colors: `team_palette` keeps text readable whatever colors a team picks.
"""
import io
from pathlib import Path
from types import SimpleNamespace

import qrcode
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
FONTS = HERE / "flyer_fonts"
IMGDIR = HERE / "flyer_img"  # small copies made for print
_fonts = False


def _register_fonts():
    global _fonts
    if not _fonts:
        pdfmetrics.registerFont(TTFont("Black", str(FONTS / "ArchivoBlack-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("Body", str(FONTS / "Carlito-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("BodyB", str(FONTS / "Carlito-Bold.ttf")))
        _fonts = True


def IMG(name):  # noqa: N802 - reads like the old file paths; ReportLab reuses each picture within one PDF
    return str(IMGDIR / name)


TIERS = [
    ("CLASSICS", (10, 12, 13), [
        ("Cheese", "cheese.png", "Pizza sauce, Italian blend cheese, Italian seasoning"),
        ("Pepperoni", "pepperoni.png", "Pizza sauce, Italian blend cheese, pepperoni"),
        ("Sausage", "sausage.png", "Pizza sauce, Italian blend cheese, sausage")]),
    ("SPECIALTIES", (12, 14, 15), [
        ("Chicken Bacon Ranch", "cbr.png", "Ranch sauce, Italian blend cheese, chicken, bacon"),
        ("Bacon Pickle", "bacon-pickle.png", "Olive oil & garlic sauce, bacon, dill pickles, dill seasoning"),
        ("Carnivore", "carnivore.png", "Pizza sauce, Italian blend cheese, pepperoni, sausage, bacon")]),
    ("THE WORKS", (13, 15, 16), [
        ("Deluxe", "deluxe.png", "Pizza sauce, Italian blend cheese, pepperoni, sausage, red onion, mushroom, black olives, green pepper")]),
]


# ---- team colors -> a readable palette
def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
def hexc(c): return "#%02X%02X%02X" % tuple(round(max(0, min(1, v)) * 255) for v in c)
def mix(a, b, t): return tuple(x + (y - x) * t for x, y in zip(a, b))   # t=0 -> a, t=1 -> b
def lum(c):
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = map(f, c); return 0.2126 * r + 0.7152 * g + 0.0722 * b
def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True); return (la + 0.05) / (lb + 0.05)

WHITE, BLACK = (1, 1, 1), (0, 0, 0)


def team_palette(color1, color2):
    a, b = rgb(color1), rgb(color2)
    dark, accent = (a, b) if lum(a) <= lum(b) else (b, a)
    # the panel colour must carry white text: darken until contrast >= 7
    t = 0
    while contrast(mix(dark, BLACK, t), WHITE) < 7 and t < 1: t += 0.05
    dark = mix(dark, BLACK, t)
    head = dark
    for t in (0.25, 0.2, 0.15, 0.1, 0.05):          # slightly lighter headline/tier colour if still readable
        if contrast(mix(dark, WHITE, t), WHITE) >= 4.5: head = mix(dark, WHITE, t); break
    # accent must stand out on the dark panel; if it's white/near-white or too close to the panel, fall back
    accent_ok = contrast(accent, dark) >= 3
    near_white = lum(accent) > 0.8
    gold = accent if accent_ok else mix(dark, WHITE, 0.75)
    # tier-1 band / header rule needs white text on it
    band = accent if contrast(accent, WHITE) >= 3 else mix(dark, WHITE, 0.35)
    amt = mix(dark, WHITE, 0.82) if near_white else mix(accent, WHITE, 0.35)
    return dict(CREAM=WHITE, BROWN=dark, RED=head, ORANGE=band, GOLD=gold, AMT=amt,
                TAN=mix(dark, WHITE, 0.86), MUTED=mix(dark, (0.35, 0.35, 0.35), 0.6))




# ---- drawing (from the prototype)
def qr(url):
    q = qrcode.QRCode(box_size=10, border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(url); q.make(fit=True)
    b = io.BytesIO(); q.make_image(fill_color="black", back_color="white").save(b, "PNG"); b.seek(0)
    return ImageReader(b)


def wrap(c, t, f, s, w):
    out, cur = [], ""
    for word in t.split():
        x = (cur + " " + word).strip()
        if c.stringWidth(x, f, s) <= w: cur = x
        else: out.append(cur); cur = word
    return out + [cur]


def center_lines(c, lines, f, s, cx, y, lead):
    c.setFont(f, s)
    for ln in lines: c.drawCentredString(cx, y, ln); y -= lead
    return y


def pizza_card(c, P, name, img, ingr, prices, cx, top, d=92, w=128):
    # tan disc behind photo for a little depth
    c.setFillColor(P.TAN); c.circle(cx, top - d / 2, d / 2 + 4, fill=1, stroke=0)
    c.drawImage(IMG(img), cx - d / 2, top - d, d, d, mask="auto")
    c.setFillColor(P.BROWN)
    y = center_lines(c, wrap(c, name.upper(), "Black", 10.5, w), "Black", 10.5, cx, top - d - 15, 12)
    c.setFillColor(P.MUTED)
    y = center_lines(c, wrap(c, ingr, "Body", 7.8, w), "Body", 7.8, cx, y - 1, 9)
    c.setFillColor(P.RED); c.setFont("BodyB", 8.8)
    c.drawCentredString(cx, y - 3, f'10" ${prices[0]}   •   12" ${prices[1]}   •   GF ${prices[2]}')
    c.setFillColor(black)


def front(c, W, H, s):
    P = s["P"]
    c.setFillColor(P.CREAM); c.rect(0, 0, W, H, fill=1, stroke=0)

    # header
    c.drawImage(IMG("logo.png"), 28, H - 66, 300, 37.5, mask="auto")
    c.setFillColor(P.RED); c.setFont("Black", 42); c.drawString(28, H - 118, s["headline"])
    c.setFillColor(P.BROWN); c.setFont("BodyB", 13)
    c.drawString(30, H - 138, "Frozen take & bake pizza, made in our USDA-inspected kitchen in South Bend, Indiana.")
    c.setStrokeColor(P.ORANGE); c.setLineWidth(3); c.line(30, H - 150, 548, H - 150)

    # pizza grid: row 1 = 4 cards, row 2 = 3 cards + GF badge
    flat = [(n, i, g, p) for _, p, items in TIERS for (n, i, g) in items]
    xs = [97, 226, 355, 484]
    top1, top2 = H - 162, H - 362
    for k, (n, i, g, p) in enumerate(flat):
        row, col = divmod(k, 4)
        pizza_card(c, P, n, i, g, p, xs[col], top1 if row == 0 else top2)
    c.drawImage(IMG("gluten-free.png"), xs[3] - 46, top2 - 92, 92, 92, mask="auto")
    c.setFillColor(P.BROWN); c.setFont("BodyB", 9)
    c.drawCentredString(xs[3], top2 - 107, "Every flavor available")
    c.drawCentredString(xs[3], top2 - 118, "gluten-free (12\")")

    # right panel
    px, pw = 572, W - 572 - 22
    c.setFillColor(P.BROWN); c.roundRect(px, 22, pw, H - 44, 14, fill=1, stroke=0)
    cx = px + pw / 2
    c.setFillColor(P.GOLD); c.setFont("Black", 11); c.drawCentredString(cx, H - 54, "YOU'RE SUPPORTING")
    c.setFillColor(white)
    sz = 24
    while c.stringWidth(s["seller"], "Black", sz) > pw - 24: sz -= 1
    c.setFont("Black", sz); c.drawCentredString(cx, H - 82, s["seller"])
    y = center_lines(c, wrap(c, s["group"], "BodyB", 14, pw - 24), "BodyB", 14, cx, H - 102, 16)

    # 40% callout
    c.setFillColor(P.GOLD); c.roundRect(px + 14, y - 40, pw - 28, 36, 8, fill=1, stroke=0)
    c.setFillColor(P.BROWN); fs = 15
    while c.stringWidth("40% OF EVERY PIZZA", "Black", fs) > pw - 40: fs -= 0.5
    c.setFont("Black", fs); c.drawCentredString(cx, y - 20, "40% OF EVERY PIZZA")
    c.setFont("BodyB", 9.5); c.drawCentredString(cx, y - 33, f"goes straight back to {s['group_short']}")

    # QR
    qs = 112; qy = y - 60 - qs
    c.setFillColor(white); c.roundRect(cx - qs / 2 - 7, qy - 7, qs + 14, qs + 14, 8, fill=1, stroke=0)
    c.drawImage(qr(s["url"]), cx - qs / 2, qy, qs, qs)
    c.setFillColor(white); c.setFont("Black", 12.5); c.drawCentredString(cx, qy - 24, "SCAN. ORDER. DONE.")
    c.setFont("Body", 9.5)
    yy = center_lines(c, wrap(c, s["qr_line"], "Body", 9.5, pw - 30), "Body", 9.5, cx, qy - 38, 11)

    # pickup box
    bh = 74; by = yy - bh - 4
    c.setStrokeColor(P.GOLD); c.setLineWidth(1.5); c.roundRect(px + 14, by, pw - 28, bh, 8, fill=0, stroke=1)
    c.setFillColor(P.GOLD); c.setFont("Black", 10); c.drawCentredString(cx, by + bh - 15, "PICKUP")
    c.setFillColor(white); c.setFont("BodyB", 10.5)
    c.drawCentredString(cx, by + bh - 31, s["pickup_date"])
    c.drawCentredString(cx, by + bh - 45, s["pickup_time"])
    c.setFont("Body", 9.5)
    for i, ln in enumerate(wrap(c, s["pickup_location"], "Body", 9.5, pw - 40)[:2]):
        c.drawCentredString(cx, by + bh - 59 - i * 10, ln)

    steps = ["Pick your pizzas", s["pay_step"], "Pick up frozen, bake when you want"]
    sy = by - 26
    c.setFillColor(P.GOLD); c.setFont("Black", 10); c.drawCentredString(cx, sy, "EASY AS 1, 2, 3"); sy -= 20
    for n, st in enumerate(steps, 1):
        c.setFillColor(P.GOLD); c.circle(px + 28, sy + 3.5, 8, fill=1, stroke=0)
        c.setFillColor(P.BROWN); c.setFont("Black", 9); c.drawCentredString(px + 28, sy, str(n))
        c.setFillColor(white); c.setFont("Body", 9.3)
        for k, ln in enumerate(wrap(c, st, "Body", 9.3, pw - 60)): c.drawString(px + 44, sy - k * 10.5, ln)
        sy -= 26
    c.setFillColor(P.TAN); c.setFont("Body", 9)
    c.drawCentredString(cx, 44, f"Paying cash or check? Order on the back")
    c.drawCentredString(cx, 33, f"and pay {s['seller_first']} directly.")


def back(c, W, H, s):
    P = s["P"]
    L, R = 26, W - 26
    c.drawImage(IMG("logo.png"), L, H - 50, 220, 27.5, mask="auto")
    c.setFillColor(P.RED); c.setFont("Black", 20); c.drawString(L + 232, H - 46, "ORDER FORM")
    c.setFillColor(P.BROWN); c.setFont("BodyB", 10.5)
    c.drawRightString(R, H - 30, f"Seller: {s['seller']}   |   {s['group']}")
    c.drawRightString(R, H - 45, f"Pickup: {s['pickup_date']}, {s['pickup_time']}")

    name_w, ph_w, tot_w, amt_w, pay_w = 118, 72, 40, 52, 46
    cw = (R - L - name_w - ph_w - tot_w - amt_w - pay_w) / 21
    top, th, fh, sh, rowh, rows = H - 60, 26, 26, 14, 16.4, 25
    x = [L, L + name_w, L + name_w + ph_w]
    for _ in range(21): x.append(x[-1] + cw)
    x += [x[-1] + tot_w, x[-1] + tot_w + amt_w, x[-1] + tot_w + amt_w + pay_w]
    hb = top - th - fh - sh
    bottom = hb - rows * rowh

    # tier header bands
    fi = 0
    tier_cols = [P.ORANGE, P.RED, P.BROWN]
    for t, (tname, p, items) in enumerate(TIERS):
        x0, x1 = x[2 + fi * 3], x[2 + (fi + len(items)) * 3]
        c.setFillColor(tier_cols[t]); c.rect(x0, top - th, x1 - x0, th, fill=1, stroke=0)
        c.setFillColor(white); fs = 9.5
        while c.stringWidth(tname, "Black", fs) > x1 - x0 - 6: fs -= 0.5
        c.setFont("Black", fs); c.drawCentredString((x0 + x1) / 2, top - 12, tname)
        pt = f'${p[0]} / ${p[1]} / ${p[2]}'; fs = 8.5
        while c.stringWidth(pt, "BodyB", fs) > x1 - x0 - 6: fs -= 0.5
        c.setFont("BodyB", fs); c.drawCentredString((x0 + x1) / 2, top - 22, pt)
        for (n, _, _) in items:
            fx0 = x[2 + fi * 3]
            if fi % 2 == 0:
                c.setFillColor(P.CREAM); c.rect(fx0, bottom, cw * 3, top - th - bottom, fill=1, stroke=0)
            c.setFillColor(P.BROWN)
            lines = wrap(c, n, "BodyB", 8.5, cw * 3 - 4)
            yy = top - th - 10 - (1 if len(lines) == 2 else 5)
            center_lines(c, lines, "BodyB", 8.5, fx0 + cw * 1.5, yy, 9)
            for j, szl in enumerate(('10"', '12"', 'GF')):
                c.setFont("BodyB", 7.5); c.drawCentredString(x[2 + fi * 3 + j] + cw / 2, hb + 4, szl)
            fi += 1
    c.setFillColor(P.AMT); c.rect(x[24], bottom, amt_w, top - bottom, fill=1, stroke=0)
    c.setFillColor(P.BROWN)
    for xx, w, t in ((x[0], name_w, ["Buyer Name"]), (x[1], ph_w, ["Phone"]), (x[23], tot_w, ["Total", "Pizzas"]),
                     (x[24], amt_w, ["Amount", "Due"]), (x[25], pay_w, ["Cash /", "Check"])):
        yy = top - th - fh / 2 - (0 if len(t) == 1 else -5) - 3
        center_lines(c, t, "BodyB", 9, xx + w / 2, yy - 6, 10)

    # grid lines
    c.setStrokeColor(P.BROWN)
    for i in range(rows + 1):
        c.setLineWidth(0.4); c.line(L, hb - i * rowh, R, hb - i * rowh)
    c.setLineWidth(0.8); c.line(L, hb, R, hb); c.line(L, top - th, R, top - th)
    for i, xx in enumerate(x):
        heavy = i in (0, 1, 2, 23, 24, 25, 26) or (i - 2) % 3 == 0
        c.setLineWidth(0.9 if heavy else 0.35)
        c.line(xx, bottom, xx, top - th if heavy else hb)
    c.setLineWidth(1.2); c.rect(L, bottom, R - L, top - bottom)

    # footer
    c.drawImage(qr(s["url"]), L, 14, 50, 50)
    c.setFillColor(P.RED); c.setFont("Black", 10.5); c.drawString(L + 60, 50, "ORDERING ONLINE? SKIP THE FORM.")
    c.setFillColor(P.BROWN); c.setFont("Body", 9.3)
    c.drawString(L + 60, 37, f"Scan the code to order online. It's credited to {s['seller_first']} automatically.")
    c.drawString(L + 60, 25, f"Sellers: add these orders on your seller page before {s['sale_end']}.  Order link: {s['url'].replace('https://', '')}")
    c.setFont("BodyB", 10)
    c.drawRightString(R - 112, 46, "Total pizzas:"); c.setLineWidth(0.7); c.line(R - 106, 45, R, 45)
    c.drawRightString(R - 112, 26, "Cash/check collected: $"); c.line(R - 106, 25, R, 25)


def palette(color1, color2):
    try:
        p = team_palette(color1 or "#14284b", color2 or "#f2a900")
    except (ValueError, IndexError):
        p = team_palette("#14284b", "#f2a900")
    return SimpleNamespace(**{k: HexColor(hexc(v)) for k, v in p.items()})


def draw_flyer(c, seller, url):
    """Add one seller's two-page flyer to an open canvas."""
    from .models import SiteSettings
    f = seller.fundraiser
    W, H = landscape(letter)
    name = SiteSettings.get().program_name.strip() or "Raise the Dough"
    card = f.is_demo  # card payment online only where it's switched on (demo now; real once Square is connected)
    s = dict(P=palette(f.color1, f.color2), seller=seller.display, seller_first=seller.first_name, group=f.group,
             group_short="the team" if len(f.group) > 22 else f.group, url=url,
             headline=(name.upper() + "!")[:24],
             pickup_date=f.pickup_date.strftime("%A, %B %-d") if f.pickup_date else "Ask your seller",
             pickup_time=f.pickup_time or "", pickup_location=f.pickup_place or "",
             sale_end=f.sale_end.strftime("%B %-d"),
             qr_line=(f"Pay by card online. Your order counts toward {seller.first_name}'s total automatically." if card
                      else f"Order online in a minute, then pay {seller.first_name} when your pizzas arrive."),
             pay_step="Pay online, or cash/check to your seller" if card else "Pay your seller by cash or check")
    front(c, W, H, s)
    c.showPage()
    back(c, W, H, s)
    c.showPage()


def flyers_pdf(sellers, url_for):
    """One PDF with a flyer for every seller given. url_for(seller) -> their order page address."""
    _register_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(letter))
    sellers = list(sellers)
    c.setTitle(f"Roundbelly's flyers - {sellers[0].fundraiser.group}" if sellers else "Roundbelly's flyers")
    for s in sellers:
        draw_flyer(c, s, url_for(s))
    c.save()
    return buf.getvalue()
