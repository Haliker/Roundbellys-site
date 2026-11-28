# roundbellyspizza.com - project notes for Claude

Public website for **Roundbelly's Pizza** (owner Adam, adam@roundbellyspizza.com), replacing the old Wix site.
Roundbelly's = wood-fired **Pizza Bus** catering (red Blue Bird school bus with a wood-burning oven, "Wood Fire Pizza"
on the side) + public cooks ("events") + frozen take-and-bake pizzas for **fundraisers** and **wholesale**, made in
its own USDA-inspected kitchen in South Bend, IN. Revenue today: ~50% private catering, ~30% events, ~20%
wholesale + fundraising; Adam's goal is to grow so catering and wholesale/fundraising are ~50/50.

## Working with Adam
- Plain language, no jargon; he isn't a programmer. Deploy / setup steps go in the chat reply, never in a file.
- **This repo: Claude may commit and push directly** (Adam, Nov 22 2026). Render deploys on push.
- **Never change the ch-erp repo from this project** (Adam has other work going on there). Read it only.
- Phone first: most visitors are on phones.

## Stack (same as the ERP on purpose)
Django 5.2, Postgres on Render (sqlite locally), whitenoise, gunicorn. Server-rendered templates + one small vanilla
JS file (`web/static/web/js/estimate.js`). No frontend framework. Uploaded files would have to live in the DB
(Render's disk is wiped on deploy) - none yet; site photos are static files in the repo.

Run locally: `NO_WHITENOISE=1 python3 manage.py runserver` / tests: `NO_WHITENOISE=1 TESTING=1 python3 manage.py test web`.
`build.sh` (Render) = install, collectstatic, migrate, `setup_site` (settings row + first office login from
ADMIN_USERNAME / ADMIN_PASSWORD env vars). `render.yaml` = web service `roundbellys-site` + Postgres `roundbellys-site-db`.

## Layout
- `web/pricing.py` - THE catering price rules (Food Truck $15/guest, 2 h, $1,500 min; Buffet $20/guest, 5 pizzas,
  3 h, $2,000 min; add-ons breadsticks $5, salad bar $7, mini donuts $7, cheesecake bar $10 per guest; minimum is on
  the TOTAL incl. add-ons; $200/extra hour; 25% deposit, balance 7 days before; plus tax; 3% fee on credit cards only).
  `as_json()` feeds the page estimator; every request is re-priced on the server.
- `web/content.py` - flavors + ingredients + fundraiser prices (Classics 10/12/13, Specialties 12/14/15,
  The Works 13/15/16 for 10" / 12" / GF 12"); team keeps 40%.
- `web/models.py` - SiteSettings (program name "Raise the Dough" - a setting, NEVER in URLs/QR codes; phone, email,
  tasting place/days, service area), Booking (public event = shown on site / private catering = only blocks the
  date), CateringRequest, FundraiserInquiry, ContactMessage.
- Office = Django admin at `/office/` ("Roundbelly's office"). Catering requests have a "Book these dates" action.
- Forms: honeypot field `website` (bots dropped silently), phone normalised to 574-555-1234, office alert email via
  SMTP env vars (EMAIL_HOST etc.); without them it logs to the console (request is saved either way).
- Old Wix paths /shop and /wholesale-shop redirect.

## Fundraising reward (Adam, Nov 22 2026)
NOT every group: only when a club/group's sale is big enough to make it make sense, Roundbelly's sets a party goal;
hitting it = the Pizza Bus comes and throws a pizza party (wood-fired on site). Site copy says "bigger sales can earn".
Done every year at e.g. - Middlebury Elementary is on year 3 (party Nov 2026); principal Marion Hostetler wrote a
thank-you letter (Nov 18 2024; "best day ever", each student + staff got their own 10" pizza). It's the headline of the
Fundraising page. Exact terms (goal amount, who qualifies) still to confirm with Adam. Testimonials model: quotes only
show once "show" is ticked (permission first); Middlebury quote loaded hidden by migration 0003.

## Design
Colors from the Bus: bus red #a3281c, school-bus yellow #f6b400, ember #ff7a1a, ink #1b1714, soot #241a15. Fonts:
Archivo Black (display) + Bitter (body), self-hosted woff2 (OFL). The one bold element = the "order ticket" price
estimator (torn-paper top, tilted, hard yellow shadow). Buttons have hard offset shadows like sign lettering.
Tagline "Never trust a skinny chef." (from the frozen-pizza fundraising label, `img/fundraising-badge.webp`).
Navy & Gold is a FLYER option for team colors, not the site's look.
Photos: `img/photos/` from Roundbelly's Facebook (Bus, oven, food). team-bus = a local high school team at the Bus
(the school posted it to Roundbelly's page itself; used on Fundraising, school not named). School-class photo (sent by
a school after its fundraiser, with a thank-you card) is only 320 px - need a bigger copy. Toddler-with-mini-donuts
photo NOT used until Adam confirms the parents' OK.

## Plan (stages)
1. DONE (Nov 22 2026): public site - home, catering + instant estimate + request form, events, our pizza,
   fundraising info + application, wholesale, about, contact; office admin.
2. Catering behind the scenes: quote -> Square deposit (Roundbelly's own Square, 3% credit-card fee) -> calendar,
   reminders, Google Calendar sync of public events.
3. Fundraising - FIRST VERSION BUILT (Nov 28 2026), `web/fundraise.py` + templates `web/fr/`:
   - No passwords: coordinator dashboard = private link /group/<token>/; seller page = private link /me/<token>/;
     public order page /s/<CODE>/ (5-letter code, no 0/O/1/I); family sign-up /join/<JOINCODE>/.
   - Models Fundraiser (status setup/open/closed/delivered, dates, pickup, party_goal, team colors, is_demo),
     Seller (first name + last initial public; parent contact coordinator-only), Order (online/logged; payment
     cash/check/card/later; collected), OrderLine (prices from content.py, never from the form).
   - Card payment online only on the demo until Square (stage 2) is connected; real sales: buyers order online and
     pay the seller ("later") or the seller logs cash/check orders.
   - Settlement on the dashboard: Roundbelly's 60% of gross, card orders credited x 0.97, balance at delivery.
   - Packing sheet /group/<token>/packing/ (kitchen totals + one box list per seller). Flyers: `web/flyer.py` (ported
     prototype, team colors via team_palette, small print images in web/flyer_img, fonts in web/flyer_fonts),
     /me/<token>/flyer.pdf and /group/<token>/flyers.pdf (all sellers).
   - Office: Fundraisers admin (links to send, totals), "Set up a fundraiser from this application" action.
   - Demo: `manage.py make_demo_fundraiser [--reset]` (runs on every deploy, only makes it if missing): Riverbend
     Raptors Volleyball (fake, purple/gold), 14 sellers, join code DEMO, DEMO banner on every page.
   Still to do: Square card payments, emails (seller links to parents, order receipts), sale auto-close, ERP sync.
4. Wholesale logins with each customer's own pricing.
5. ERP sync - the ERP (ch-erp, company RB) always starts the connection; the website never holds ERP credentials.
   Signed requests, scoped keys, ERP treats website data as untrusted drafts. Minors' contact info stays here.
Domain: registrar Squarespace, DNS currently on Wix (ns12/ns13.wixdns.net). Keep the 5 Google MX records exactly;
add SPF/DKIM/DMARC at cutover (Adam's choice). See the claude.ai project docs for the full plans.
