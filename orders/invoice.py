"""
PDF invoice / bill generation for orders.

`generate_invoice_pdf(order)` renders a tax invoice for an Order instance and
returns the raw PDF bytes. Data is pulled dynamically from the order, its user,
and its line items so every bill reflects the real purchase.

reportlab is imported lazily so the rest of the orders app keeps working even if
the dependency is missing in some environment; the view surfaces a clear error.
"""
from decimal import Decimal
from io import BytesIO

# ---- Seller details (issuer of the invoice) ----
SELLER_NAME = "Nidhi Masala Foods"
SELLER_TAGLINE = "Pure & Authentic Indian Spices"
SELLER_ADDRESS = "Plot 14, MIDC Industrial Area,<br/>Pune, Maharashtra 411019"
SELLER_GSTIN = "27ABCDE1234F1Z5"
SELLER_EMAIL = "support@nidhimasala.com"


def _money(value):
    """Format a Decimal/number as an INR amount string."""
    return f"Rs. {Decimal(str(value or 0)):,.2f}"


def _order_number(order):
    return f"ORD-{order.id:06d}"


def _customer_name(user):
    if not user:
        return "Guest"
    name = (getattr(user, "name", "") or "").strip()
    if name:
        return name
    full = f"{user.first_name} {user.last_name}".strip()
    return full or user.email


def generate_invoice_pdf(order) -> bytes:
    """Render a tax invoice PDF for the given Order and return its bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    )

    BRAND = colors.HexColor("#B91C1C")
    DARK = colors.HexColor("#1F2937")
    MUTED = colors.HexColor("#6B7280")
    LIGHT = colors.HexColor("#F3F4F6")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("BrandName", fontName="Helvetica-Bold", fontSize=22,
                              textColor=BRAND, leading=24))
    styles.add(ParagraphStyle("Tag", fontName="Helvetica", fontSize=8,
                              textColor=MUTED, leading=10))
    styles.add(ParagraphStyle("H", fontName="Helvetica-Bold", fontSize=9,
                              textColor=DARK, leading=12))
    styles.add(ParagraphStyle("N", fontName="Helvetica", fontSize=9,
                              textColor=DARK, leading=13))
    styles.add(ParagraphStyle("Nm", fontName="Helvetica", fontSize=8,
                              textColor=MUTED, leading=11))
    styles.add(ParagraphStyle("InvTitle", fontName="Helvetica-Bold", fontSize=16,
                              textColor=DARK, alignment=2, leading=18))
    styles.add(ParagraphStyle("RightSmall", fontName="Helvetica", fontSize=8,
                              textColor=MUTED, alignment=2, leading=11))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Invoice {_order_number(order)}")
    el = []

    # ---- Header: brand + invoice title ----
    created = order.created_at
    header = Table([[
        [Paragraph(SELLER_NAME, styles["BrandName"]),
         Paragraph(SELLER_TAGLINE, styles["Tag"])],
        [Paragraph("TAX INVOICE", styles["InvTitle"]),
         Paragraph(f"Invoice No: {_order_number(order)}", styles["RightSmall"]),
         Paragraph(f"Date: {created.strftime('%d %b %Y, %I:%M %p')}", styles["RightSmall"])],
    ]], colWidths=[95 * mm, 79 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(header)
    el.append(Spacer(1, 6))
    el.append(HRFlowable(width="100%", thickness=2, color=BRAND))
    el.append(Spacer(1, 10))

    # ---- Seller / buyer block ----
    user = order.user
    seller = [
        Paragraph("From", styles["Nm"]),
        Paragraph(SELLER_NAME, styles["H"]),
        Paragraph(SELLER_ADDRESS, styles["Nm"]),
        Paragraph(f"GSTIN: {SELLER_GSTIN}", styles["Nm"]),
        Paragraph(SELLER_EMAIL, styles["Nm"]),
    ]
    ship_addr = (order.shipping_address or "").replace("\n", "<br/>")
    buyer = [
        Paragraph("Bill To", styles["Nm"]),
        Paragraph(_customer_name(user), styles["H"]),
        Paragraph(ship_addr or "-", styles["Nm"]),
        Paragraph(f"Phone: {order.phone_number or '-'}", styles["Nm"]),
    ]
    if user and getattr(user, "email", None):
        buyer.append(Paragraph(user.email, styles["Nm"]))
    party = Table([[seller, buyer]], colWidths=[87 * mm, 87 * mm])
    party.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(party)
    el.append(Spacer(1, 14))

    # ---- Line items ----
    rows = [["#", "Item", "Pack", "Qty", "Rate", "Amount"]]
    for i, item in enumerate(order.items.all(), 1):
        line_total = item.price * item.quantity
        rows.append([
            str(i),
            Paragraph(item.product_name, styles["N"]),
            item.product_weight or "-",
            str(item.quantity),
            _money(item.price),
            _money(line_total),
        ])

    tbl = Table(rows, colWidths=[8 * mm, 80 * mm, 22 * mm, 14 * mm, 24 * mm, 26 * mm],
                repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    el.append(tbl)
    el.append(Spacer(1, 12))

    # ---- Totals (from stored order values) ----
    tot_rows = [
        ["Subtotal", _money(order.subtotal)],
    ]
    if order.discount_amount and order.discount_amount > 0:
        label = "Discount"
        if order.coupon_code:
            label = f"Discount ({order.coupon_code})"
        tot_rows.append([label, "- " + _money(order.discount_amount)])
    tot_rows.append(["GST", _money(order.tax)])
    tot_rows.append([
        "Shipping",
        "FREE" if (order.shipping_charge or 0) == 0 else _money(order.shipping_charge),
    ])
    tot_rows.append(["Grand Total", _money(order.total_amount)])

    tot = Table(tot_rows, colWidths=[40 * mm, 34 * mm], hAlign="RIGHT")
    tot.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TEXTCOLOR", (0, 0), (-1, -2), DARK),
        ("LINEABOVE", (0, -1), (-1, -1), 1, DARK),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 11.5),
        ("TEXTCOLOR", (0, -1), (-1, -1), BRAND),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    el.append(tot)
    el.append(Spacer(1, 18))

    # ---- Payment + footer ----
    el.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
    el.append(Spacer(1, 6))
    pay_status = (order.payment_status or "pending").upper()
    el.append(Paragraph(
        f"Payment: {order.get_payment_method_display()} &bull; Status: <b>{pay_status}</b>",
        styles["Nm"]))
    el.append(Spacer(1, 4))
    el.append(Paragraph(
        "Thank you for shopping with Nidhi Masala! This is a computer-generated "
        "invoice and does not require a signature.",
        styles["Nm"]))

    doc.build(el)
    return buf.getvalue()
