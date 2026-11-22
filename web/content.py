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
