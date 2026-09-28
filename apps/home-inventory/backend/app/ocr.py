"""Best-effort invoice text extraction (Tesseract / pdftotext) + field heuristics tuned for
Indian retail invoices (Amazon, Flipkart, Croma, Reliance Digital, local GST bills).
Everything returned is a *suggestion* the user confirms in the form."""
import logging
import re
import shutil
import subprocess
import tempfile
import threading
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dateutil import parser as dparser
from PIL import Image, ImageOps

from .config import get_settings
from .schemas import ExtractedFields
from .warranty import today_local

log = logging.getLogger("ocr")
settings = get_settings()
_ocr_lock = threading.Semaphore(1)   # one OCR at a time — the Pi has 4 cores, keep UI responsive

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


def ocr_available() -> bool:
    return settings.enable_ocr and pytesseract is not None and shutil.which("tesseract") is not None


# ------------------------------------------------------------------ text extraction
def _ocr_image(img: Image.Image) -> str:
    img = ImageOps.exif_transpose(img).convert("L")
    if max(img.size) < 1600:  # small photos OCR badly; upscale
        f = 1600 / max(img.size)
        img = img.resize((int(img.width * f), int(img.height * f)), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    return pytesseract.image_to_string(img, lang=settings.ocr_lang, config="--psm 4", timeout=90)


def extract_text(path: Path, content_type: str) -> str:
    with _ocr_lock:
        if content_type == "application/pdf":
            text = ""
            if shutil.which("pdftotext"):
                r = subprocess.run(["pdftotext", "-layout", "-l", "3", str(path), "-"],
                                   capture_output=True, timeout=60)
                text = r.stdout.decode("utf-8", "ignore")
            if len(text.strip()) > 40 or not ocr_available():
                return text
            # scanned PDF → rasterise first 2 pages and OCR
            with tempfile.TemporaryDirectory() as td:
                subprocess.run(["pdftoppm", "-f", "1", "-l", "2", "-r", "200", "-png", str(path),
                                f"{td}/p"], capture_output=True, timeout=120, check=False)
                return "\n".join(_ocr_image(Image.open(p)) for p in sorted(Path(td).glob("p*.png")))
        if not ocr_available():
            return ""
        return _ocr_image(Image.open(path))


# ------------------------------------------------------------------ field parsing
STORES = ["Amazon", "Flipkart", "Croma", "Reliance Digital", "Vijay Sales", "Poorvika",
          "Sangeetha", "Girias", "Pai International", "Bajaj Electronics", "Tata CLiQ", "JioMart",
          "Myntra", "Nykaa", "Decathlon", "IKEA", "Pepperfry", "Urban Ladder", "Apple",
          "Samsung", "Vasanth & Co", "Lulu", "Viveks", "Harini", "Big Bazaar", "DMart"]
BRANDS = ["Samsung", "LG", "Sony", "Apple", "Whirlpool", "Bosch", "IFB", "Voltas", "Daikin",
          "Godrej", "Haier", "Panasonic", "Philips", "Bajaj", "Havells", "Prestige", "Dell",
          "HP", "Lenovo", "Asus", "Acer", "OnePlus", "Xiaomi", "Redmi", "Realme", "Vivo", "Oppo",
          "Blue Star", "Hitachi", "Carrier", "Lloyd", "Crompton", "Usha", "Kent", "Aquaguard",
          "Eureka Forbes", "Butterfly", "Preethi", "TCL", "boAt", "JBL", "Canon", "Epson",
          "Brother", "Titan", "Honda", "Hero", "TVS", "Dyson", "Xbox", "PlayStation", "Nothing",
          "Motorola", "Nokia", "Google", "Microsoft", "Logitech", "V-Guard", "Orient", "Atomberg",
          "Symphony", "Morphy Richards", "Pigeon", "Hawkins", "Sujata", "Wonderchef", "Faber",
          "Elica", "Kaff", "Glen", "AO Smith", "Racold", "Livpure", "Pureit", "Mi"]

AMOUNT_NUM = r"([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)"
AMOUNT = r"(?:₹|rs\.?|inr)?\s*" + AMOUNT_NUM
TOTAL_KEYS = re.compile(r"(grand\s*total|total\s*amount|net\s*amount|amount\s*payable|invoice\s*value|"
                        r"total\s*payable|net\s*payable|order\s*total|total)", re.I)
DATE_PATTERNS = [
    r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b",
    r"\b(\d{4}-\d{2}-\d{2})\b",
    r"\b(\d{1,2}[\s-]*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s,.-]*\d{2,4})\b",
    r"\b((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b",
]
DATE_KEYS = re.compile(r"(invoice\s*date|bill\s*date|order\s*date|date\s*of\s*(?:invoice|purchase)|dated|date)", re.I)


def _to_decimal(s: str) -> Decimal | None:
    try:
        d = Decimal(s.replace(",", ""))
        return d if 0 < d < Decimal("100000000") else None
    except InvalidOperation:
        return None


def _parse_date(s: str) -> date | None:
    try:
        d = dparser.parse(s, dayfirst=True, fuzzy=False).date()
    except (ValueError, OverflowError):
        return None
    today = today_local()
    if date(2000, 1, 1) <= d <= today:
        return d
    return None


def _find_dates(line: str) -> list[date]:
    out = []
    for pat in DATE_PATTERNS:
        for m in re.finditer(pat, line, re.I):
            d = _parse_date(m.group(1))
            if d:
                out.append(d)
    return out


def parse_fields(text: str) -> ExtractedFields:
    f = ExtractedFields()
    if not text or not text.strip():
        return f
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    low = text.lower()

    # invoice number
    m = re.search(r"(?:invoice|inv|bill|tax\s*invoice)\s*(?:no|number|num|#)\.?\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/]{3,30})",
                  text, re.I)
    if m:
        f.invoice_number = m.group(1).strip("-/")

    # date — prefer lines with an invoice/order date keyword
    keyed, anyd = [], []
    for ln in lines:
        ds = _find_dates(ln)
        if ds:
            (keyed if DATE_KEYS.search(ln) else anyd).extend(ds)
    if keyed or anyd:
        f.purchase_date = (keyed or anyd)[0]

    # total — max amount on "total"-ish lines, excluding sub-total/tax lines
    totals = []
    for ln in lines:
        if TOTAL_KEYS.search(ln) and not re.search(r"sub\s*-?total|tax\s*amount|discount|savings", ln, re.I):
            for a in re.findall(AMOUNT, ln, re.I):
                d = _to_decimal(a)
                if d and d >= 1:
                    totals.append(d)
    if not totals:  # fallback: largest rupee-marked amount
        totals = [d for a in re.findall(r"(?:₹|rs\.?|inr)\s*" + AMOUNT_NUM, text, re.I)
                  if (d := _to_decimal(a))]
    if totals:
        f.purchase_price = max(totals)

    # GSTIN
    m = re.search(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b", text)
    if m:
        f.gstin = m.group(1)

    # vendor
    m = re.search(r"sold\s*by\s*[:\-]?\s*([A-Za-z0-9&.,' ]{3,60})", text, re.I)
    if m:
        f.vendor = m.group(1).strip(" ,.")
    else:
        for s in STORES:
            if s.lower() in low:
                f.vendor = s
                break
        else:
            for ln in lines[:4]:
                if re.search(r"[A-Za-z]{3,}", ln) and not re.search(r"tax\s*invoice|invoice|bill|receipt|gst", ln, re.I):
                    f.vendor = ln[:60]
                    break

    # brand + product name
    for b in sorted(BRANDS, key=len, reverse=True):
        mb = re.search(rf"\b{re.escape(b)}\b", text, re.I if len(b) > 3 else 0)
        if mb:
            f.brand = b
            for ln in lines:
                if re.search(rf"\b{re.escape(b)}\b", ln, re.I if len(b) > 3 else 0) and len(ln) > len(b) + 3:
                    name = re.sub(r"\s{2,}.*$", "", ln)                 # cut trailing table columns
                    name = re.sub(r"^\d+[\s.)-]+", "", name).strip()    # drop leading S.No
                    name = re.sub(r"(\s+(?:₹|rs\.?)?\s*[\d,]+(?:\.\d+)?)+\s*$", "", name, flags=re.I).strip()  # qty/price cols
                    if 4 <= len(name) <= 120:
                        f.name = name
                        break
            break

    # model number
    m = re.search(r"model\s*(?:no|number|name)?\.?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/.]{2,30})", text, re.I)
    if m:
        f.model = m.group(1)

    # serial / IMEI
    m = re.search(r"(?:serial\s*(?:no|number)?|s/?n|imei\s*(?:no|number)?\s*1?)\.?\s*[:\-]?\s*([A-Z0-9]{6,25})",
                  text, re.I)
    if m:
        f.serial_number = m.group(1)

    # warranty period
    m = re.search(r"(\d{1,2})\s*(years?|yrs?|months?|mths?)\s*(?:\w+\s*){0,3}warranty", text, re.I) \
        or re.search(r"warranty\s*(?:period)?\s*[:\-]?\s*(\d{1,2})\s*(years?|yrs?|months?|mths?)", text, re.I)
    if m:
        n = int(m.group(1))
        f.warranty_months = n * 12 if m.group(2).lower().startswith(("y")) else n

    return f
