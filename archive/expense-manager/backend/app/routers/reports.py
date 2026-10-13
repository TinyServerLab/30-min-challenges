import csv
import io
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import current_user
from ..config import settings
from ..database import get_db
from ..models import Transaction, User
from .dashboard import category_slices, month_bounds, totals

router = APIRouter(prefix="/reports", tags=["reports"])


def _range(month: str | None, start: date | None, end: date | None) -> tuple[date, date, str]:
    if month:
        try:
            y, m = (int(x) for x in month.split("-"))
            s, nxt = month_bounds(date(y, m, 1))
        except ValueError:
            raise HTTPException(400, "month must look like 2026-09")
        return s, date.fromordinal(nxt.toordinal() - 1), s.strftime("%B %Y")
    if start and end:
        if end < start:
            raise HTTPException(400, "End date is before start date")
        return start, end, f"{start.isoformat()} to {end.isoformat()}"
    s, nxt = month_bounds(date.today())
    return s, date.fromordinal(nxt.toordinal() - 1), s.strftime("%B %Y")


class MonthlySummary(schemas.BaseModel):
    label: str
    start: date
    end: date
    income: Decimal
    expense: Decimal
    net: Decimal
    savings_rate: float
    expense_by_category: list[schemas.CategorySlice]
    income_by_category: list[schemas.CategorySlice]
    transaction_count: int


@router.get("/summary", response_model=MonthlySummary)
def summary(
    month: str | None = None, start: date | None = None, end: date | None = None,
    _: User = Depends(current_user), db: Session = Depends(get_db),
):
    s, e, label = _range(month, start, end)
    income, expense = totals(db, s, e)
    exp_cats = category_slices(db, s, e, "expense")
    inc_cats = category_slices(db, s, e, "income")
    return MonthlySummary(
        label=label, start=s, end=e, income=income, expense=expense, net=income - expense,
        savings_rate=float((income - expense) / income * 100) if income else 0.0,
        expense_by_category=exp_cats, income_by_category=inc_cats,
        transaction_count=sum(c.count for c in exp_cats + inc_cats),
    )


def _rows(db: Session, s: date, e: date) -> list[Transaction]:
    return db.scalars(
        select(Transaction).where(Transaction.date >= s, Transaction.date <= e)
        .order_by(Transaction.date, Transaction.id)
    ).all()


@router.get("/export.csv")
def export_csv(
    month: str | None = None, start: date | None = None, end: date | None = None,
    _: User = Depends(current_user), db: Session = Depends(get_db),
):
    s, e, label = _range(month, start, end)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "type", "amount", "category", "source", "note", "recurring", "entered_by"])
    for t in _rows(db, s, e):
        w.writerow([t.date.isoformat(), t.type, f"{t.amount:.2f}", t.category.name, t.source.name,
                    t.note or "", "yes" if t.is_recurring else "no", t.user.name])
    buf.seek(0)
    fname = f"ledger_{s.isoformat()}_{e.isoformat()}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


def money(v: Decimal | float) -> str:
    # fpdf core fonts are latin-1; write the symbol only if it survives, else the ISO code
    sym = settings.currency_symbol
    try:
        sym.encode("latin-1")
    except UnicodeEncodeError:
        sym = "INR " if sym == "₹" else ""
    return f"{sym}{Decimal(v):,.2f}"


@router.get("/export.pdf")
def export_pdf(
    month: str | None = None, start: date | None = None, end: date | None = None,
    _: User = Depends(current_user), db: Session = Depends(get_db),
):
    s, e, label = _range(month, start, end)
    income, expense = totals(db, s, e)
    exp_cats = category_slices(db, s, e, "expense")
    inc_cats = category_slices(db, s, e, "income")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, f"{settings.app_name} - {label}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 6, f"{s.isoformat()} to {e.isoformat()}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(60, 8, "Income", border="B")
    pdf.cell(60, 8, "Expense", border="B")
    pdf.cell(60, 8, "Net", border="B", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(60, 8, money(income))
    pdf.cell(60, 8, money(expense))
    pdf.cell(60, 8, money(income - expense), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    def table(title: str, slices: list[schemas.CategorySlice], total: Decimal) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(235, 238, 234)
        pdf.cell(90, 7, "Category", fill=True)
        pdf.cell(25, 7, "Count", fill=True, align="R")
        pdf.cell(40, 7, "Amount", fill=True, align="R")
        pdf.cell(25, 7, "Share", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        if not slices:
            pdf.cell(0, 7, "No entries in this period", new_x="LMARGIN", new_y="NEXT")
        for c in slices:
            share = float(c.total / total * 100) if total else 0.0
            pdf.cell(90, 7, c.name.encode("latin-1", "replace").decode("latin-1"))
            pdf.cell(25, 7, str(c.count), align="R")
            pdf.cell(40, 7, money(c.total), align="R")
            pdf.cell(25, 7, f"{share:.1f}%", align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

    table("Expenses by category", exp_cats, expense)
    table("Income by category", inc_cats, income)

    # transaction listing
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Transactions", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(235, 238, 234)
    widths = (22, 18, 45, 35, 40, 30)
    for w, h in zip(widths, ("Date", "Type", "Category", "Source", "Note", "Amount")):
        pdf.cell(w, 6, h, fill=True, align="R" if h == "Amount" else "L")
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 9)
    for t in _rows(db, s, e):
        note = (t.note or "")[:28].encode("latin-1", "replace").decode("latin-1")
        cells = (t.date.isoformat(), t.type, t.category.name[:26], t.source.name[:20], note, money(t.amount))
        for w, val in zip(widths, cells):
            pdf.cell(w, 6, val.encode("latin-1", "replace").decode("latin-1"), align="R" if w == 30 else "L")
        pdf.ln(6)

    fname = f"ledger_{s.isoformat()}_{e.isoformat()}.pdf"
    return Response(bytes(pdf.output()), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})
