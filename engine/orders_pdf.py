"""PDF inmutable de una orden de compra ya validada.

Este módulo no abre conexiones ni conoce Supabase/Storage. Recibe el snapshot
que se va a emitir y devuelve bytes PDF para que la frontera privada de API lo
almacene. Así el documento siempre representa exactamente los ítems, costos y
cantidades aprobados en esa emisión.
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Mapping

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

__all__ = ["build_purchase_order_pdf"]

_ROOT = Path(__file__).resolve().parents[1]
_LOGO_PATH = _ROOT / "logo transparente.png"
_FONT_REGULAR = _ROOT / "assets" / "fonts" / "Lato-Regular.ttf"
_FONT_BOLD = _ROOT / "assets" / "fonts" / "Lato-Bold.ttf"
_TEXT = colors.HexColor("#333333")
_MUTED = colors.HexColor("#666666")
_ACCENT = colors.HexColor("#1D4ED8")
_LIGHT = colors.HexColor("#F5F7FA")
_BORDER = colors.HexColor("#D9E0EA")


def build_purchase_order_pdf(
    *,
    order_number: str,
    supplier_name: str,
    destination_name: str,
    issued_at: date | datetime | str,
    items: Iterable[Mapping[str, Any]],
    notes: str = "",
) -> bytes:
    """Construye el PDF de una OC con cantidades, costos y totales solamente."""
    normalized = [_normalize_item(item) for item in items]
    if not normalized:
        raise ValueError("Una orden debe tener al menos una línea para emitir PDF.")

    _register_fonts()
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Orden de compra {order_number}",
        author="DIDACTICOS JUGANDO Y EDUCANDO SAS",
    )
    styles = _styles()
    story: list[Any] = []

    story.append(
        Table(
            [[_logo(), Paragraph(
                "<b>DIDÁCTICOS JUGANDO Y EDUCANDO SAS</b><br/>"
                "Avenida 19 #114A-22 · Bogotá, Colombia<br/>"
                "NIT: 901144615-6",
                styles["POCompany"],
            )]],
            colWidths=[70 * mm, 108 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]),
        )
    )
    story.extend([Spacer(1, 20 * mm), Paragraph("ORDEN DE COMPRA", styles["POEyebrow"]),
                  Paragraph(escape(order_number), styles["POTitle"]), Spacer(1, 7 * mm)])
    story.append(
        Table(
            [[
                Paragraph(f"<font color='#666666'>Emisión</font><br/><b>{_date(issued_at)}</b>", styles["POMeta"]),
                Paragraph(
                    "<font color='#666666'>Proveedor</font><br/><b>%s</b><br/>"
                    "<font color='#666666'>Destino</font><br/><b>%s</b>"
                    % (escape(supplier_name), escape(destination_name)),
                    styles["POMeta"],
                ),
            ]],
            colWidths=[72 * mm, 106 * mm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]),
        )
    )
    story.append(Spacer(1, 12 * mm))

    rows: list[list[Any]] = [["Producto", "EAN", "Cant.", "Costo unit.", "Total línea"]]
    for item in normalized:
        rows.append([
            Paragraph(escape(item["product_name"]), styles["POCell"]),
            item["ean"],
            _units(item["quantity"]),
            _cop(item["unit_cost"]),
            _cop(item["quantity"] * item["unit_cost"]),
        ])
    table = Table(rows, colWidths=[69 * mm, 35 * mm, 18 * mm, 28 * mm, 28 * mm], repeatRows=1)
    table_style = [
        ("BACKGROUND", (0, 0), (-1, 0), _LIGHT),
        ("FONTNAME", (0, 0), (-1, 0), "Lato-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), _TEXT),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (-1, -1), "Lato"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.35, _BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for index in range(1, len(rows)):
        if index % 2 == 0:
            table_style.append(("BACKGROUND", (0, index), (-1, index), _LIGHT))
    table.setStyle(TableStyle(table_style))
    story.extend([table, Spacer(1, 10 * mm)])

    total_units = sum(item["quantity"] for item in normalized)
    subtotal = sum(item["quantity"] * item["unit_cost"] for item in normalized)
    totals = Table(
        [["Total unidades", _units(total_units)], ["Total compra", _cop(subtotal)]],
        colWidths=[48 * mm, 42 * mm],
        hAlign="RIGHT",
        style=TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Lato"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, _BORDER),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTNAME", (1, -1), (1, -1), "Lato-Bold"),
            ("TEXTCOLOR", (0, -1), (-1, -1), _ACCENT),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]),
    )
    story.append(totals)
    if notes.strip():
        story.extend([Spacer(1, 14 * mm), Paragraph(f"<b>Notas:</b> {escape(notes.strip())}", styles["PONotes"])])

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output.getvalue()


def _normalize_item(item: Mapping[str, Any]) -> dict[str, Any]:
    try:
        quantity = int(item["quantity"])
        unit_cost = float(item["unit_cost"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Cada línea de la orden requiere cantidad y costo numéricos.") from exc
    product_name = str(item.get("product_name") or "").strip()
    ean = str(item.get("ean") or "").strip()
    if not product_name or not ean or quantity <= 0 or unit_cost < 0:
        raise ValueError("Cada línea requiere producto, EAN, cantidad positiva y costo no negativo.")
    return {"product_name": product_name, "ean": ean, "quantity": quantity, "unit_cost": unit_cost}


def _register_fonts() -> None:
    if "Lato" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Lato", str(_FONT_REGULAR)))
    if "Lato-Bold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Lato-Bold", str(_FONT_BOLD)))


def _styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="POCompany", fontName="Lato", fontSize=9, leading=13, textColor=_MUTED, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="POEyebrow", fontName="Lato-Bold", fontSize=8, leading=11, textColor=_MUTED))
    styles.add(ParagraphStyle(name="POTitle", fontName="Lato-Bold", fontSize=20, leading=24, textColor=_ACCENT))
    styles.add(ParagraphStyle(name="POMeta", fontName="Lato", fontSize=10, leading=15, textColor=_TEXT))
    styles.add(ParagraphStyle(name="POCell", fontName="Lato", fontSize=8.5, leading=10, textColor=_TEXT))
    styles.add(ParagraphStyle(name="PONotes", fontName="Lato", fontSize=9, leading=13, textColor=_TEXT))
    return styles


def _logo() -> Any:
    if _LOGO_PATH.exists():
        image = Image(str(_LOGO_PATH), width=38 * mm, height=18 * mm)
        image.hAlign = "LEFT"
        return image
    return Paragraph("", getSampleStyleSheet()["Normal"])


def _footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("Lato", 8)
    canvas.setFillColor(_MUTED)
    y = 13 * mm
    canvas.setStrokeColor(_BORDER)
    canvas.line(doc.leftMargin, y + 6, A4[0] - doc.rightMargin, y + 6)
    canvas.drawString(doc.leftMargin, y, "Orden de compra emitida por Didácticos Jugando y Educando SAS")
    canvas.drawRightString(A4[0] - doc.rightMargin, y, f"Página {doc.page}")
    canvas.restoreState()


def _date(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _cop(value: float) -> str:
    return "$ " + f"{value:,.0f}".replace(",", ".")


def _units(value: int) -> str:
    return f"{value:,}".replace(",", ".")
