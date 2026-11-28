"""Coordinator uploads a seller list (Excel .xlsx or .csv) -> preview -> add sellers + email each family their page.

Columns are found by their heading, in any order, with common wordings ("Student", "First name", "Parent email",
"Guardian", "Cell"...). A single "Name" / "Student name" column is split into first name + last initial.
We only ever keep the seller's LAST INITIAL, never their last name.
"""
import csv
import io
import re

from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from .forms import _phone

MAX_ROWS = 500
MAX_BYTES = 2 * 1024 * 1024

# (field, words that mean it) - first match wins, checked in this order
HEADINGS = [
    ("parent_email", ["parent email", "guardian email", "email", "e-mail"]),
    ("parent_phone", ["parent phone", "guardian phone", "phone", "cell", "mobile"]),
    ("parent_name", ["parent", "guardian"]),
    ("last", ["last name", "last", "surname", "last initial"]),
    ("first", ["first name", "first"]),
    ("goal", ["goal"]),
    ("name", ["seller", "student", "player", "athlete", "member", "scout", "name", "child"]),
]
FIELDS = ["first", "last", "parent_name", "parent_email", "parent_phone", "goal"]
TEMPLATE_HEADINGS = ["Seller first name", "Seller last name", "Parent name", "Parent email", "Parent phone",
                     "Goal (pizzas)"]
TEMPLATE_EXAMPLE = ["Jake", "Sullivan", "Erin Sullivan", "erin@example.com", "574-555-0101", 10]


class SellerFileError(Exception):
    pass


def _field_for(heading):
    h = re.sub(r"[^a-z\- ]", " ", (heading or "").lower())
    h = " ".join(h.split())
    if not h:
        return None
    for field, words in HEADINGS:
        if any(w == h or re.search(rf"\b{re.escape(w)}\b", h) for w in words):
            return field
    return None


def read_rows(upload):
    """Returns a list of lists (all strings) from an .xlsx or .csv upload."""
    if upload.size > MAX_BYTES:
        raise SellerFileError("That file is too big. Seller lists should be well under 2 MB.")
    name = (upload.name or "").lower()
    data = upload.read()
    if name.endswith((".xlsx", ".xlsm")) or data[:2] == b"PK":
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception:  # noqa: BLE001
            raise SellerFileError("We couldn't open that Excel file. Try saving it again as .xlsx or .csv.")
        ws = wb.worksheets[0]
        rows = []
        for r in ws.iter_rows(values_only=True):
            rows.append(["" if v is None else (str(int(v)) if isinstance(v, float) and v.is_integer() else str(v))
                         for v in r])
            if len(rows) > MAX_ROWS + 20:
                break
        return rows
    if name.endswith(".xls"):
        raise SellerFileError("That's an old Excel file (.xls). In Excel choose File > Save As > Excel Workbook (.xlsx), "
                           "or CSV, and upload that.")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SellerFileError("We couldn't read that file. Upload an Excel (.xlsx) or CSV file.")
    try:
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return [r for r in csv.reader(io.StringIO(text), dialect)][: MAX_ROWS + 20]


def _header(rows):
    """First row (of the first 10) where we recognise a name column. Returns (index, {col: field})."""
    for i, row in enumerate(rows[:10]):
        cols = {}
        for c, cell in enumerate(row):
            fld = _field_for(cell)
            if fld and fld not in cols.values():
                cols[c] = fld
        if "first" in cols.values() or "name" in cols.values():
            return i, cols
    raise SellerFileError("We couldn't find a seller name column. The first row should have headings like "
                       "\"Seller first name\" and \"Parent email\" - download our template to see.")


def parse(rows):
    """-> list of dicts: first, last_initial, parent_name, parent_email, parent_phone, goal, problems (list)."""
    start, cols = _header(rows)
    out = []
    for row in rows[start + 1:]:
        vals = {fld: (row[c].strip() if c < len(row) and row[c] else "") for c, fld in cols.items()}
        if not any(vals.values()):
            continue
        first, last = vals.get("first", ""), vals.get("last", "")
        if not first and vals.get("name"):
            n = vals["name"]
            if "," in n:  # "Sullivan, Jake"
                last, first = [p.strip() for p in n.split(",", 1)]
            else:
                parts = n.split()
                first, last = parts[0], (parts[-1] if len(parts) > 1 else "")
        first = first.split()[0].title()[:40] if first else ""
        initial = next((ch.upper() for ch in last if ch.isalpha()), "")
        problems = []
        if not first:
            problems.append("no seller name")
        email = vals.get("parent_email", "").replace("mailto:", "").strip()
        if email:
            try:
                validate_email(email)
            except ValidationError:
                problems.append(f"\"{email}\" isn't an email address - added without one")
                email = ""
        goal = 10
        if vals.get("goal"):
            try:
                goal = max(1, min(200, int(float(vals["goal"]))))
            except ValueError:
                pass
        phone = vals.get("parent_phone", "")
        out.append({"first": first, "last_initial": initial, "parent_name": vals.get("parent_name", "")[:100],
                    "parent_email": email.lower(), "parent_phone": _phone(phone) if phone else "", "goal": goal,
                    "problems": problems, "ok": bool(first)})
        if len(out) >= MAX_ROWS:
            break
    if not out:
        raise SellerFileError("The file has headings but no sellers under them.")
    return out


def mark_duplicates(rows, fundraiser):
    """Someone already on the list (same first name, last initial and parent email), or twice in the file."""
    seen = {(s.first_name.lower(), s.last_initial.upper(), s.parent_email.lower())
            for s in fundraiser.sellers.filter(active=True)}
    for r in rows:
        key = (r["first"].lower(), r["last_initial"], r["parent_email"])
        if r["ok"] and key in seen:
            r["ok"] = False
            r["problems"].append("already signed up")
        seen.add(key)
    return rows


def template_xlsx():
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Sellers"
    ws.append(TEMPLATE_HEADINGS)
    ws.append(TEMPLATE_EXAMPLE)
    for c in ws[1]:
        c.font = Font(bold=True)
    for col, w in zip("ABCDEF", (18, 18, 20, 28, 16, 14)):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
