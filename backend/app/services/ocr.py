"""
OCR pipeline for statement photos and receipts.

Design principle (rule #7/#8): OCR output is NEVER trusted blindly. Every
extracted row is returned with needs_review=True and a confidence score;
nothing is committed to the ledger until the user confirms/edits it.
"""
import re
from datetime import date, datetime
from pathlib import Path

from dateutil import parser as dateparser

from app.services.categorize import categorize

DATE_AMOUNT_LINE = re.compile(
    r"^\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s*\d{0,4})"
    r"\s+(.+?)\s*([+\-]?₹?\s?[\d,]+(?:\.\d{1,2})?)\s*$"
)
TOTAL_LINE = re.compile(r"(total|amount due|grand total)\D{0,10}([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)
ANY_DATE = re.compile(r"(?:\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}|\d{1,2}[-/]?[A-Za-z]{3,9}[-/]?\d{2,4})")
BANK_DATE_PREFIX = re.compile(
    r"^\s*(?:\d+\s+)?(?P<date>"
    r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|"
    r"\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}|"
    r"\d{1,2}[-/]?[A-Za-z]{3,9}[-/]?\d{2,4}"
    r")\s+(?P<rest>.+)$", re.IGNORECASE
)
MONEY_TOKEN = re.compile(r"[+-]?(?:₹|Rs\.?|INR\s*)?\s*[\d,]+(?:\.\d{1,2})?")
BANK_DEBIT_MARKERS = {"DR", "DEBIT", "WITHDRAWAL", "WITHDRAW", "WITHDRAWS", "WDL", "DR."}
BANK_CREDIT_MARKERS = {"CR", "CREDIT", "DEPOSIT", "DEPOSITS", "CREDITED", "CR."}
CANARA_CLASSIC_ROW = re.compile(
    r"^\s*(?P<date>\d{1,2}[-/]?[A-Za-z]{3,9}[-/]?\d{2,4}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\s+"
    r"(?P<value_date>\d{1,2}[-/]?[A-Za-z]{3,9}[-/]?\d{2,4}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\s+"
    r"(?P<branch>\d{1,6})\s+"
    r"(?P<ref>[^ ]*)\s+"
    r"(?P<description>.+?)\s+"
    r"(?P<withdraw>[-]?(?:₹|Rs\.?\s*)?[\d,]+(?:\.\d{1,2})?)\s+"
    r"(?P<deposit>[-]?(?:₹|Rs\.?\s*)?[\d,]+(?:\.\d{1,2})?)\s+"
    r"(?P<balance>[-]?(?:₹|Rs\.?\s*)?[\d,]+(?:\.\d{1,2})?)\s*$",
    re.IGNORECASE,
)



NOISE_LINE = re.compile(
    r"^(page\s+\d+\s+of\s+\d+|end\s+of\s+statement|statement\s+continues|"
    r"continued\s+on\s+next\s+page|this\s+is\s+a\s+(?:computer|system)[- ]generated|"
    r"\**\s*end\s+of\s+statement\s*\**)",
    re.IGNORECASE,
)

# Repeated bank-name banners and column-header rows (e.g. a table header
# reprinted at the top of every page) must never be glued onto a wrapped
# transaction narration -- a header word like "Deposit" or "Credit" would
# otherwise be misread as a debit/credit marker for that transaction.
HEADER_LINE = re.compile(
    r"^(?:[A-Z][A-Z .&]{3,40}BANK\b.*|.*\(continued\)\s*$)|"
    r"^(?:date\s+narration|narration\s+chq|txn\s+date|transaction\s+date|"
    r"trans\s+date|value\s+date|particulars?\b|remarks?\b).*"
    r"(?:withdraw|deposit|debit|credit|balance)",
    re.IGNORECASE,
)


def _strip_noise_lines(lines: list[str]) -> list[str]:
    """Drop common page-break/footer/header boilerplate so it doesn't get
    glued onto a wrapped transaction narration during line assembly."""
    return [line for line in lines if line and not NOISE_LINE.match(line.strip())]


CANARA_EPASS_DATE_ONLY = re.compile(r"^\d{2}-\d{2}-\d{4}$")
CANARA_EPASS_MONEY = re.compile(r"^[+-]?(?:₹|Rs\.?\s*)?[\d,]+(?:\.\d{1,2})?$")

def _parse_canara_epassbook_text(text: str) -> list[dict]:
    """Parse Canara e-Passbook PDFs extracted by PyMuPDF.

    In this format a transaction is emitted as:
    date -> wrapped narration -> Chq -> amount -> balance.
    The amount and balance are separate text lines, not one table row.
    """
    raw_lines = [re.sub(r"\s+", " ", raw).strip() for raw in text.splitlines()]
    results: list[dict] = []
    seen = set()
    current_date = None
    block: list[str] = []
    previous_balance = None

    def emit_transaction(date_str: str, parts: list[str], amount_str: str, balance_str: str) -> None:
        nonlocal previous_balance
        try:
            amount = _money_value(amount_str)
            balance = _money_value(balance_str)
        except (ValueError, TypeError):
            return
        if amount <= 0:
            return

        narration = " ".join(
            x for x in parts
            if x and not x.lower().startswith("chq:")
        )
        narration = re.sub(r"\s+", " ", narration).strip(" -|:")
        if not narration:
            return

        upper = narration.upper()
        if re.search(r"\bUPI/CR/", upper):
            inferred_type = "income"
        elif re.search(r"\bUPI/DR/", upper):
            inferred_type = "expense"
        elif re.search(r"\b(?:CR|CREDIT)\b", upper):
            inferred_type = "income"
        elif re.search(r"\b(?:DR|DEBIT)\b", upper):
            inferred_type = "expense"
        else:
            inferred_type = _infer_type_from_balance(previous_balance, balance, amount)
        if inferred_type is None:
            return

        signed = ("+" if inferred_type == "income" else "-") + amount_str.lstrip("+-")
        row = _statement_row(date_str, narration, signed, inferred_type, confidence_cap=0.92)
        if row:
            key = (row["date"], row["merchant"].lower(), row["amount_rupees"], row["type"])
            if key not in seen:
                seen.add(key)
                results.append(row)
        previous_balance = balance

    for line in raw_lines:
        if not line:
            continue
        if CANARA_EPASS_DATE_ONLY.fullmatch(line):
            current_date = line
            block = []
            continue
        if current_date is None:
            continue

        # Ignore statement-level closing balance after all transactions.
        if line.lower() == "closing balance":
            break

        if CANARA_EPASS_MONEY.fullmatch(line) and block and CANARA_EPASS_MONEY.fullmatch(block[-1]):
            # The last two numeric-only lines are exactly transaction amount
            # and running balance. Everything before them is narration/chq.
            amount_str = block[-1]
            balance_str = line
            emit_transaction(current_date, block[:-1], amount_str, balance_str)
            block = []
            continue

        block.append(line)

    return results

class OCRUnavailableError(Exception):
    pass


def extract_text_from_image(image_path: str) -> str:
    """Runs Tesseract OCR on an image file. Raises OCRUnavailableError if
    the tesseract binary isn't installed on the host, so callers can show a
    clean message instead of a 500 error."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise OCRUnavailableError(f"OCR libraries not installed: {e}")

    try:
        image = Image.open(image_path)
        return pytesseract.image_to_string(image)
    except Exception as e:
        raise OCRUnavailableError(f"OCR engine unavailable or failed: {e}")


def _parse_amount(raw: str) -> tuple[float, str]:
    cleaned = raw.replace("₹", "").replace(",", "").strip()
    txn_type = "expense"
    if cleaned.startswith("+"):
        txn_type = "income"
    cleaned = cleaned.lstrip("+-").strip()
    return float(cleaned), txn_type


def _statement_row(date_str: str, merchant: str, amount_str: str, inferred_type: str | None = None, confidence_cap: float = 0.85) -> dict | None:
    try:
        txn_date = dateparser.parse(date_str, dayfirst=not bool(re.match(r"^\d{4}[/\-.]", date_str.strip())), fuzzy=True).date()
        amount_rupees, parsed_type = _parse_amount(amount_str)
    except (ValueError, OverflowError):
        return None

    inferred_type = inferred_type or parsed_type
    merchant = re.sub(r"\s+", " ", merchant).strip(" -|:")
    if not merchant or amount_rupees <= 0:
        return None

    category, source, confidence = categorize(merchant)
    if inferred_type == "income":
        category = "Income"

    return {
        "date": txn_date.isoformat(),
        "merchant": merchant,
        "description": merchant,
        "amount_rupees": amount_rupees,
        "type": inferred_type,
        "category": category,
        "category_source": source,
        "confidence": round(min(confidence, confidence_cap), 2),
        "needs_review": True,
    }


def _money_value(raw: str) -> float:
    cleaned = re.sub(r"[^0-9.]", "", raw.replace(",", ""))
    return float(cleaned) if cleaned else 0.0


def _clean_bank_merchant(text: str) -> str:
    text = re.sub(r"\b(?:DR|DEBIT|CR|CREDIT|WITHDRAWAL|WITHDRAW|DEPOSIT|DEPOSITS)\.?\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -|:/")
    # Remove leading serial numbers commonly emitted by bank PDFs.
    text = re.sub(r"^\d{1,6}\s+", "", text)
    return text


def _infer_type_from_balance(previous_balance: float | None, current_balance: float | None, amount: float) -> str | None:
    if previous_balance is None or current_balance is None or amount <= 0:
        return None
    eps = max(0.02, amount * 0.00001)
    if abs((previous_balance - amount) - current_balance) <= eps:
        return "expense"
    if abs((previous_balance + amount) - current_balance) <= eps:
        return "income"
    return None


def _generic_bank_row(line: str, previous_balance: float | None = None) -> tuple[dict | None, float | None]:
    """Handle common SBI/HDFC/ICICI/Axis/PNB/BOB/Union/IDBI/Kotak/etc. rows.

    The parser deliberately uses the *right-hand numeric tail* rather than the
    first number in the narration. This avoids treating cheque numbers, UTRs,
    phone numbers and reference IDs as transaction amounts.
    """
    m = BANK_DATE_PREFIX.match(line)
    if not m:
        return None, previous_balance
    date_str, rest = m.group("date"), m.group("rest")

    tokens = list(MONEY_TOKEN.finditer(rest))
    if not tokens:
        return None, previous_balance

    # Indian bank statements almost always print monetary columns with two
    # decimal places (e.g. "450.00", "0.00") or thousands separators (e.g.
    # "55,000"). Bare digit runs without either -- order/reference numbers
    # glued onto a narration ("PAYMENT-99281"), or a year picked up from a
    # wrapped narration line ("...FOR JUNE 2026...") -- are not amounts.
    # When there are enough properly-formatted candidates to fill the
    # debit/credit/balance columns, restrict to those first so a stray
    # reference number can't be mistaken for the transaction amount; fall
    # back to the unfiltered token list otherwise so unusually formatted
    # statements (no decimals at all) still get parsed.
    decimal_tokens = [t for t in tokens if "." in t.group(0) or "," in t.group(0)]
    candidate_tokens = decimal_tokens if len(decimal_tokens) >= 2 else tokens

    # Only treat the final 1-3 numeric values as monetary columns. Anything
    # earlier is likely a reference/cheque/UTR number inside the narration.
    tail = candidate_tokens[-3:]
    # Long unformatted digit strings (UTR/account/reference numbers) are not
    # transaction amounts. Indian bank statements usually print money with a
    # decimal point or thousands separators; keep short integer amounts.
    filtered_tail = []
    for token in tail:
        raw_token = token.group(0).strip()
        digits_only = re.sub(r"\D", "", raw_token)
        if len(digits_only) >= 10 and "," not in raw_token and "." not in raw_token:
            continue
        filtered_tail.append(token)
    if not filtered_tail:
        return None, previous_balance
    tail = filtered_tail
    values = [_money_value(x.group(0)) for x in tail]
    marker_words = re.findall(r"\b[A-Z]{2,12}\.?\b", rest.upper())
    marker_set = set(marker_words)
    inferred_type = None
    if marker_set & BANK_CREDIT_MARKERS:
        inferred_type = "income"
    elif marker_set & BANK_DEBIT_MARKERS:
        inferred_type = "expense"

    current_balance = None
    amount = None
    amount_token = None

    # Most Indian bank statement tables end with either:
    #   debit credit balance
    #   withdrawal deposit balance
    #   amount balance
    #   debit/credit amount balance
    # Therefore the last value is normally the running/closing balance.
    if len(values) >= 2:
        current_balance = values[-1]
        candidate_values = values[:-1]
        nonzero = [(v, tail[i]) for i, v in enumerate(candidate_values) if v > 0]
        if nonzero:
            # If both debit and credit columns are non-zero, retain the first
            # non-zero value and lower confidence; this is rare but reviewable.
            amount, amount_token = nonzero[0]
        else:
            amount = 0.0
    else:
        amount = values[-1]
        amount_token = tail[-1]

    if not amount or amount <= 0:
        return None, current_balance if current_balance is not None else previous_balance

    # An explicit +/- sign on the selected transaction amount is authoritative
    # and must not be overwritten by a balance-based inference.
    explicit_sign = amount_token.group(0).strip() if amount_token is not None else ""
    if explicit_sign.startswith("+"):
        inferred_type = "income"
    elif explicit_sign.startswith("-"):
        inferred_type = "expense"
    else:
        balance_type = _infer_type_from_balance(previous_balance, current_balance, amount)
        if balance_type:
            inferred_type = balance_type

    if inferred_type is None:
        # Description-level clues are useful when the statement has no explicit
        # debit/credit column (e.g. UPI/CR, UPI/DR, IMPS/CR, NEFT/DR).
        upper = rest.upper()
        if re.search(r"(?:UPI|IMPS|NEFT|RTGS|ACH)[^\n]{0,80}\bCR\b", upper):
            inferred_type = "income"
        elif re.search(r"(?:UPI|IMPS|NEFT|RTGS|ACH)[^\n]{0,80}\bDR\b", upper):
            inferred_type = "expense"

    # Remove the selected monetary tail from the narration. Keep non-tail
    # numbers because they can be meaningful parts of UPI/UTR references.
    narration_end = tail[0].start()
    merchant = _clean_bank_merchant(rest[:narration_end])
    if not merchant:
        return None, current_balance

    amount_str = str(amount)
    if inferred_type == "income":
        amount_str = "+" + amount_str
    elif inferred_type == "expense":
        amount_str = "-" + amount_str

    cap = 0.72 if len(values) == 1 else 0.78
    if inferred_type is None:
        cap = min(cap, 0.58)

    row = _statement_row(date_str, merchant, amount_str, inferred_type, confidence_cap=cap)
    return row, current_balance


def parse_statement_text(text: str) -> list[dict]:
    """Parses OCR/PDF-extracted bank statement text into reviewable candidates.

    Supports the original simple ``DATE MERCHANT AMOUNT`` format plus common
    bank-statement rows containing debit/credit markers or multiple numeric
    columns (transaction amount + balance). Because PDF layouts vary by bank,
    every candidate remains editable and flagged for review.
    """
    # Canara e-Passbook PDFs have a distinctive extraction shape: transaction
    # dates are standalone lines and the amount/balance cells are emitted as
    # separate numeric-only lines. Detect and parse that layout first.
    canara_epass_rows = _parse_canara_epassbook_text(text)
    if canara_epass_rows:
        return canara_epass_rows

    results = []
    seen = set()
    previous_balance = None
    lines = _strip_noise_lines([re.sub(r"\s+", " ", raw).strip() for raw in text.splitlines()])

    # Canara Bank's classic statement layout is:
    # TRANS DATE | VALUE DATE | BRANCH | REF/CHQ.NO | DESCRIPTION |
    # WITHDRAWS | DEPOSIT | BALANCE.  Generic parsers often mistake the
    # branch/ref columns for monetary columns. Handle this layout explicitly.
    # Narrations can wrap over several PDF text lines, so we first assemble
    # obvious continuation lines onto the previous transaction.
    assembled = []
    for line in lines:
        if not line:
            continue
        if CANARA_CLASSIC_ROW.match(line):
            assembled.append(line)
        elif assembled and not BANK_DATE_PREFIX.match(line) and not re.match(
            r"^(TRANS\s+DATE|VALUE\s+DATE|BRANCH|REF/?CHQ|DESCRIPTION|WITHDRAWS|DEPOSIT|BALANCE|STATEMENT|CANARA\s+BANK)",
            line,
            flags=re.IGNORECASE,
        ) and not HEADER_LINE.match(line) and not re.match(r"^\d{1,2}[-/]?[A-Za-z]{3,9}[-/]?\d{2,4}\s", line):
            # Keep wrapped narration/reference text with the most recent row.
            assembled[-1] += " " + line
        else:
            assembled.append(line)

    for raw_line in assembled:
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue

        # CAMS/Canara e-statement exports use a different layout where the
        # transaction type appears before the amount and running balance, e.g.
        # "... DEBIT 2500.00 801.62 353748".  Narrations can contain many
        # numeric IDs, so never select an amount from the beginning of the row.
        cams = re.search(
            r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\s+(.+?)\s+\b(DEBIT|CREDIT)\b\s+(.+)$",
            line,
            flags=re.IGNORECASE,
        )
        if cams:
            date_str, before_type, marker, after_type = cams.groups()
            amounts = re.findall(r"[+-]?(?:₹|Rs\.?\s*)?[\d,]+(?:\.\d{1,2})?", after_type)
            # Prefer properly-formatted monetary values (decimal point or
            # thousands separator) over bare digit runs, so a stray number
            # after the DEBIT/CREDIT marker (e.g. a year from a wrapped
            # narration) isn't mistaken for the transaction amount.
            decimal_amounts = [a for a in amounts if "." in a or "," in a]
            if decimal_amounts:
                amounts = decimal_amounts
            if amounts:
                amount_str = amounts[0]
                inferred_type = "income" if marker.upper() == "CREDIT" else "expense"
                if not amount_str.lstrip().startswith(("+", "-")):
                    amount_str = ("+" if inferred_type == "income" else "-") + amount_str
                # Strip common CAMS metadata (transaction id, value date, mode)
                # when present, while retaining the actual narration.
                merchant = before_type
                merchant = re.sub(r"^//[A-Za-z0-9]+\s*", "", merchant)
                merchant = re.sub(r"\b(?:OTHERS|PAYMENT|AM|PM)\b", "", merchant, flags=re.IGNORECASE)
                row = _statement_row(date_str, merchant, amount_str, inferred_type, confidence_cap=0.82)
                if row:
                    key = (row["date"], row["merchant"].lower(), row["amount_rupees"], row["type"])
                    if key not in seen:
                        seen.add(key)
                        results.append(row)
                continue

        canara = CANARA_CLASSIC_ROW.match(line)
        if canara:
            data = canara.groupdict()
            withdraw = data["withdraw"]
            deposit = data["deposit"]
            # Canara uses 0.00 in the unused debit/credit column. Prefer the
            # non-zero monetary column; if both are non-zero, keep debit as
            # expense because the row is ambiguous and remains reviewable.
            try:
                wd = float(re.sub(r"[^0-9.]", "", withdraw.replace(",", "")) or 0)
                cr = float(re.sub(r"[^0-9.]", "", deposit.replace(",", "")) or 0)
            except ValueError:
                wd = cr = 0.0
            if wd > 0:
                amount_str, inferred_type = "-" + withdraw.lstrip("+-"), "expense"
            elif cr > 0:
                amount_str, inferred_type = "+" + deposit.lstrip("+-"), "income"
            else:
                amount_str, inferred_type = "", None
            if amount_str:
                row = _statement_row(data["date"], data["description"], amount_str, inferred_type, confidence_cap=0.90)
                if row:
                    key = (row["date"], row["merchant"].lower(), row["amount_rupees"], row["type"])
                    if key not in seen:
                        seen.add(key)
                        results.append(row)
                continue

        # Generic Indian-bank table parser. This covers the common layouts used
        # by public and private banks (SBI, HDFC, ICICI, Axis, Kotak, PNB, BOB,
        # Union Bank, Bank of India, Canara, IDBI, IndusInd, Yes Bank, etc.)
        # without hard-coding a separate parser for every bank.
        generic_row, generic_balance = _generic_bank_row(line, previous_balance)
        if generic_row:
            previous_balance = generic_balance
            key = (generic_row["date"], generic_row["merchant"].lower(), generic_row["amount_rupees"], generic_row["type"])
            if key not in seen:
                seen.add(key)
                results.append(generic_row)
            continue
        if generic_balance is not None:
            previous_balance = generic_balance

        # Prefer the legacy parser only when there is a single amount on the
        # line. Bank PDF/table rows often contain both transaction amount and
        # running balance, which needs the column-aware path below.
        date_prefix = re.match(
            r"^\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s*\d{0,4})\s+(.+)$",
            line,
        )
        numeric_values = re.findall(r"[+-]?(?:₹|Rs\.?\s*)?[\d,]+(?:\.\d{1,2})?", date_prefix.group(2)) if date_prefix else []
        match = DATE_AMOUNT_LINE.match(line) if len(numeric_values) <= 1 else None
        if match:
            row = _statement_row(*match.groups())
            if row:
                key = (row["date"], row["merchant"].lower(), row["amount_rupees"], row["type"])
                if key not in seen:
                    seen.add(key)
                    results.append(row)
                continue

        # Common PDF/table extraction shape:
        # DATE NARRATION [DR|DEBIT|CR|CREDIT] amount [balance].
        date_match = re.match(
            r"^\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s*\d{0,4})\s+(.+)$",
            line,
        )
        if not date_match:
            continue

        date_str, remainder = date_match.groups()
        markers = re.findall(r"\b(CR|CREDIT|DR|DEBIT)\b", remainder, flags=re.IGNORECASE)
        inferred_type = None
        if markers:
            marker = markers[-1].upper()
            inferred_type = "income" if marker in {"CR", "CREDIT"} else "expense"

        signed_amounts = re.findall(r"[+-]?(?:₹|Rs\.?\s*)?[\d,]+(?:\.\d{1,2})?", remainder, flags=re.IGNORECASE)
        if not signed_amounts:
            continue

        # The first amount after the narration is normally the debit/credit
        # amount; later values are usually the running balance.
        amount_str = signed_amounts[0]
        amount_start = remainder.find(amount_str)
        merchant = remainder[:amount_start]
        merchant = re.sub(r"\b(CR|CREDIT|DR|DEBIT)\b", "", merchant, flags=re.IGNORECASE)
        # A bank PDF may put the transaction amount before the DR/CR marker
        # (e.g. "UPI-AMAZON 1,299.00 DR"). Strip any trailing marker too.
        merchant = re.sub(r"\b(CR|CREDIT|DR|DEBIT)\b", "", merchant, flags=re.IGNORECASE)

        # Preserve explicit signs when available; otherwise use DR/CR marker.
        if inferred_type == "income" and not amount_str.lstrip().startswith("+"):
            amount_str = "+" + amount_str
        elif inferred_type == "expense" and not amount_str.lstrip().startswith(("-", "+")):
            amount_str = "-" + amount_str

        row = _statement_row(date_str, merchant, amount_str, inferred_type, confidence_cap=0.70)
        if row:
            key = (row["date"], row["merchant"].lower(), row["amount_rupees"], row["type"])
            if key not in seen:
                seen.add(key)
                results.append(row)
    return results


def parse_receipt_text(text: str) -> dict:
    """Best-effort extraction of merchant / date / total from a receipt photo."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    merchant = lines[0] if lines else "Unknown merchant"

    total_amount = None
    for line in lines:
        m = TOTAL_LINE.search(line)
        if m:
            try:
                total_amount = float(m.group(2).replace(",", ""))
            except ValueError:
                pass

    txn_date = date.today()
    for line in lines:
        m = ANY_DATE.search(line)
        if m:
            try:
                txn_date = dateparser.parse(m.group(0), dayfirst=True, fuzzy=True).date()
                break
            except (ValueError, OverflowError):
                continue

    category, source, confidence = categorize(merchant)
    return {
        "merchant": merchant,
        "date": txn_date.isoformat(),
        "amount_rupees": total_amount,
        "category": category,
        "category_source": source,
        "confidence": round(min(confidence, 0.85), 2) if total_amount else 0.0,
        "needs_review": True,
        "raw_text": text[:2000],
    }
