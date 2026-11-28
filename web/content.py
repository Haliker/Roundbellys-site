"""Menu facts used on several pages (from the fundraiser flyer, Nov 2026)."""

FLAVORS = [
    {"slug": "cheese", "name": "Cheese", "tier": "classic",
     "ingredients": "Pizza sauce, Italian blend cheese, Italian seasoning"},
    {"slug": "pepperoni", "name": "Pepperoni", "tier": "classic",
     "ingredients": "Pizza sauce, Italian blend cheese, pepperoni"},
    {"slug": "sausage", "name": "Sausage", "tier": "classic",
     "ingredients": "Pizza sauce, Italian blend cheese, sausage"},
    {"slug": "cbr", "name": "Chicken Bacon Ranch", "tier": "specialty",
     "ingredients": "Ranch sauce, Italian blend cheese, chicken, bacon"},
    {"slug": "bacon-pickle", "name": "Bacon Pickle", "tier": "specialty",
     "ingredients": "Olive oil and garlic sauce, bacon, dill pickles, dill seasoning"},
    {"slug": "carnivore", "name": "Carnivore", "tier": "specialty",
     "ingredients": "Pizza sauce, Italian blend cheese, pepperoni, sausage, bacon"},
    {"slug": "deluxe", "name": "Deluxe", "tier": "works",
     "ingredients": "Pizza sauce, Italian blend cheese, pepperoni, sausage, red onion, mushroom, black olives, green pepper"},
]

# Fundraiser prices: 10" / 12" / gluten-free 12"
TIERS = {
    "classic": {"name": "Classics", "prices": (10, 12, 13)},
    "specialty": {"name": "Specialties", "prices": (12, 14, 15)},
    "works": {"name": "The Works", "prices": (13, 15, 16)},
}

TEAM_SHARE = 0.40
AVERAGE_PIZZA = 13  # used only for the "what could we raise" calculator, and said so on the page


def flavors_with_prices():
    out = []
    for f in FLAVORS:
        t = TIERS[f["tier"]]
        out.append({**f, "tier_name": t["name"], "prices": t["prices"]})
    return out


SIZES = [("10", '10"'), ("12", '12"'), ("gf", 'GF 12"')]


def price(slug, size):
    """Fundraiser price for one pizza, or None if there's no such flavor/size."""
    f = next((f for f in FLAVORS if f["slug"] == slug), None)
    idx = {"10": 0, "12": 1, "gf": 2}.get(size)
    if f is None or idx is None:
        return None
    return TIERS[f["tier"]]["prices"][idx]


def order_grid():
    """Rows for the order screens: each flavor with its three prices."""
    rows = []
    for f in FLAVORS:
        p = TIERS[f["tier"]]["prices"]
        rows.append({**f, "cells": [{"size": s, "label": lab, "price": p[i], "name": f"q_{f['slug']}_{s}"}
                                    for i, (s, lab) in enumerate(SIZES)]})
    return rows


def read_grid(data, max_each=50):
    """Turn posted q_<flavor>_<size> boxes into [(slug, size, qty, unit_price)]. Prices come from here, never the form."""
    out = []
    for f in FLAVORS:
        for s, _ in SIZES:
            raw = (data.get(f"q_{f['slug']}_{s}") or "").strip()
            if not raw:
                continue
            try:
                q = int(raw)
            except ValueError:
                continue
            if q > 0:
                out.append((f["slug"], s, min(q, max_each), price(f["slug"], s)))
    return out
