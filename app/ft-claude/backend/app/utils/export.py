import csv
import io
from datetime import date
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from app.models import Transaction


def transactions_to_csv(rows: list[Transaction]) -> io.StringIO:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Type", "Category", "Source", "Amount", "Recurring", "Note"])
    for t in rows:
        writer.writerow([
            t.txn_date.isoformat(),
            t.type.value,
            t.category.name if t.category else "",
            t.source.name if t.source else "",
            f"{t.amount:.2f}",
            "yes" if t.recurring else "no",
            t.note or "",
        ])
    buf.seek(0)
    return buf


def transactions_to_pdf(rows: list[Transaction], start: date, end: date) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Personal Finance Tracker — Transaction Report", styles["Title"]),
        Paragraph(f"{start.isoformat()} to {end.isoformat()}", styles["Normal"]),
        Spacer(1, 0.5 * cm),
    ]

    total_income = sum((t.amount for t in rows if t.type.value == "income"), Decimal("0"))
    total_expense = sum((t.amount for t in rows if t.type.value == "expense"), Decimal("0"))
    elements.append(Paragraph(
        f"Total income: {total_income:.2f} &nbsp;&nbsp; "
        f"Total expense: {total_expense:.2f} &nbsp;&nbsp; "
        f"Net: {(total_income - total_expense):.2f}",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 0.5 * cm))

    data = [["Date", "Type", "Category", "Source", "Amount", "Note"]]
    for t in rows:
        data.append([
            t.txn_date.isoformat(),
            t.type.value,
            t.category.name if t.category else "",
            t.source.name if t.source else "",
            f"{t.amount:.2f}",
            (t.note or "")[:40],
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    elements.append(table)

    doc.build(elements)
    buf.seek(0)
    return buf
