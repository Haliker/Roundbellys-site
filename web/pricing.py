"""Catering pricing - the ONE place the numbers live.

The page's live estimator gets these same numbers (as JSON), and every request is re-priced here on the
server, so what's saved never depends on the visitor's browser.

Rules (Adam, Nov 22 2026):
- Food Truck Style $15/person, unlimited pizza, 2-hour window, $1,500 minimum.
- Buffet Style $20/person, 5 pizza choices, 3-hour window, $2,000 minimum.
- Add-ons per person (both styles): breadsticks $5, salad bar $7, mini donuts $7, cheesecake bar $10.
- Minimum applies to the event total INCLUDING add-ons.
- $200 per extra hour past the service window (prep and cleanup don't count).
- Plus sales tax. 25% deposit holds the date; the rest is due 7 days before the event.
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

D = Decimal

STYLES = {
    "truck": {"name": "Food Truck Style", "rate": D("15"), "minimum": D("1500"), "hours": 2,
              "blurb": "Unlimited pizza made fresh on the Bus, right at your event."},
    "buffet": {"name": "Buffet Style", "rate": D("20"), "minimum": D("2000"), "hours": 3,
               "blurb": "Your choice of 5 pizzas, set out buffet style."},
}

ADDONS = {
    "breadsticks": {"name": "Breadsticks with sauces", "rate": D("5")},
    "salad": {"name": "Salad bar", "rate": D("7")},
    "donuts": {"name": "Mini donuts", "rate": D("7")},
    "cheesecake": {"name": "Cheesecake bar", "rate": D("10")},
}

EXTRA_HOUR = D("200")
DEPOSIT_PCT = D("0.25")
BALANCE_DAYS = 7
MAX_GUESTS = 2000
MAX_EXTRA_HOURS = 8
CARD_FEE_PCT = 3  # credit cards only; debit / bank transfer free


def money(x):
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def estimate(style, guests, addons=(), extra_hours=0, event_date=None):
    """Price an event. Returns a dict of plain numbers (Decimal) + suggestions when under the minimum."""
    s = STYLES[style]
    guests = max(0, min(int(guests or 0), MAX_GUESTS))
    extra_hours = max(0, min(int(extra_hours or 0), MAX_EXTRA_HOURS))
    picked = [k for k in ADDONS if k in set(addons or ())]
    per_person = s["rate"] + sum((ADDONS[k]["rate"] for k in picked), D("0"))
    food = per_person * guests
    minimum_applies = food < s["minimum"]
    food_billed = s["minimum"] if minimum_applies else food
    hours_cost = EXTRA_HOUR * extra_hours
    total = food_billed + hours_cost
    deposit = money(total * DEPOSIT_PCT)
    out = {
        "style": style, "style_name": s["name"], "guests": guests, "addons": picked,
        "per_person": per_person, "food": food, "minimum": s["minimum"], "minimum_applies": minimum_applies,
        "food_billed": food_billed, "extra_hours": extra_hours, "hours_cost": hours_cost,
        "total": total, "deposit": deposit, "balance": total - deposit,
        "service_hours": s["hours"] + extra_hours, "suggestions": [],
    }
    if event_date:
        out["balance_due"] = event_date - timedelta(days=BALANCE_DAYS)
    if minimum_applies and guests:
        for k, a in ADDONS.items():
            if k in picked:
                continue
            new_food = food + a["rate"] * guests
            extra = max(D("0"), new_food - s["minimum"])
            out["suggestions"].append({"key": k, "name": a["name"], "extra": extra, "free": extra == 0})
    return out


def as_json():
    """The same rules for the page's estimator."""
    return {
        "styles": {k: {"name": v["name"], "rate": float(v["rate"]), "minimum": float(v["minimum"]), "hours": v["hours"]}
                   for k, v in STYLES.items()},
        "addons": {k: {"name": v["name"], "rate": float(v["rate"])} for k, v in ADDONS.items()},
        "extraHour": float(EXTRA_HOUR), "depositPct": float(DEPOSIT_PCT), "balanceDays": BALANCE_DAYS,
        "maxGuests": MAX_GUESTS,
    }
