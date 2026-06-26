from __future__ import annotations

import zipfile
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


POINT_SUFFIXES = {
    "Av. 19": "AV19",
    "Bulevar": "BUL",
    "Oviedo": "OVI",
    "Bvista": "BVI",
    "Calle 74": "C74",
    "CEDI": "CEDI",
}

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "logo transparente.png"
FONT_REGULAR = BASE_DIR / "assets" / "fonts" / "Lato-Regular.ttf"
FONT_BOLD = BASE_DIR / "assets" / "fonts" / "Lato-Bold.ttf"

ACCENT = colors.HexColor("#B86B42")
TEXT = colors.HexColor("#333333")
GRAY = colors.HexColor("#666666")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
BORDER = colors.HexColor("#E0E0E0")


def build_purchase_order_zip(
    order_items: pd.DataFrame,
    base_number: str,
    supplier_name: str,
    issue_date,
    notes: str = "",
) -> bytes:
    clean_items = _prepare_items(order_items)
    if clean_items.empty:
        raise ValueError("No hay líneas con Compra final mayor a 0 para generar órdenes de compra.")

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for point, point_items in clean_items.groupby("Punto", sort=False):
            suffix = POINT_SUFFIXES.get(point, _safe_suffix(point))
            order_number = f"{base_number}-{suffix}"
            pdf_bytes = build_purchase_order_pdf(
                point_items=point_items,
                order_number=order_number,
                supplier_name=supplier_name,
                point=point,
                issue_date=issue_date,
                notes=notes,
            )
            zf.writestr(f"{order_number}.pdf", pdf_bytes)
    return zip_buffer.getvalue()


def build_purchase_order_pdf(
    point_items: pd.DataFrame,
    order_number: str,
    supplier_name: str,
    point: str,
    issue_date,
    notes: str = "",
) -> bytes:
    _register_fonts()
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Orden de Compra {order_number}",
        author="DIDACTICOS JUGANDO Y EDUCANDO SAS",
    )
    styles = _styles()
    story = []

    header_table_data = [
        [
            _logo(),
            Paragraph(
                "<b>DIDACTICOS JUGANDO Y EDUCANDO SAS</b><br/>"
                "AVENIDA 19 114 A 22<br/>"
                "BOGOTA<br/>"
                "Colombia<br/>"
                "NIT: 901144615-6",
                styles["POCompany"],
            ),
        ]
    ]
    header = Table(header_table_data, colWidths=[70 * mm, 100 * mm])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 28 * mm))
    story.append(Paragraph(order_number, styles["POTitle"]))
    story.append(Spacer(1, 8 * mm))

    meta = Table(
        [
            [
                Paragraph("<font color='#666666'>Emision</font><br/><b>%s</b>" % _format_date(issue_date), styles["POMeta"]),
                Paragraph(
                    "<font color='#666666'>Proveedor</font><br/><b>%s</b><br/><font color='#666666'>Destino</font><br/><b>%s</b>"
                    % (_escape(supplier_name), _escape(point)),
                    styles["POMeta"],
                ),
            ]
        ],
        colWidths=[72 * mm, 98 * mm],
    )
    meta.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(meta)
    story.append(Spacer(1, 14 * mm))

    rows = [["Producto", "SKU", "EAN", "Cant.", "Costo unit.", "Total linea"]]
    for _, item in point_items.iterrows():
        qty = int(item["Compra final"])
        unit_cost = float(item["Costo unitario"] or 0)
        sku = "" if str(item.get("Estado producto", "")) == "Nuevo" else str(item.get("SKU", ""))
        rows.append(
            [
                Paragraph(_escape(str(item.get("Producto", ""))), styles["POCellText"]),
                sku,
                str(item.get("EAN", "")),
                qty,
                _format_cop(unit_cost),
                _format_cop(qty * unit_cost),
            ]
        )

    table = Table(rows, colWidths=[58 * mm, 22 * mm, 31 * mm, 15 * mm, 28 * mm, 31 * mm], repeatRows=1)
    table_style = [
        ("FONTNAME", (0, 0), (-1, 0), "Lato-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEXT),
        ("LINEBELOW", (0, 0), (-1, 0), 1, TEXT),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (-1, -1), "Lato"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 1), (-1, -1), 0.4, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for row in range(1, len(rows)):
        if row % 2 == 0:
            table_style.append(("BACKGROUND", (0, row), (-1, row), LIGHT_GRAY))
    table.setStyle(TableStyle(table_style))
    story.append(table)
    story.append(Spacer(1, 10 * mm))

    total_units = int(point_items["Compra final"].sum())
    total_value = float((point_items["Compra final"] * point_items["Costo unitario"]).sum())
    totals = Table(
        [
            ["Total unidades", f"{total_units:,}".replace(",", ".")],
            ["Total compra", _format_cop(total_value)],
        ],
        colWidths=[48 * mm, 42 * mm],
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Lato"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (1, -1), (1, -1), "Lato-Bold"),
                ("TEXTCOLOR", (0, -1), (-1, -1), ACCENT),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(totals)

    if notes.strip():
        story.append(Spacer(1, 18 * mm))
        story.append(Paragraph(f"<b>Notas:</b> {_escape(notes.strip())}", styles["PONotes"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output.getvalue()


def _prepare_items(order_items: pd.DataFrame) -> pd.DataFrame:
    if order_items is None or order_items.empty:
        return pd.DataFrame()
    df = order_items.copy()
    df["Compra final"] = pd.to_numeric(df["Compra final"], errors="coerce").fillna(0).clip(lower=0).round().astype(int)
    df["Costo unitario"] = pd.to_numeric(df["Costo unitario"], errors="coerce").fillna(0)
    df["Total línea"] = df["Compra final"] * df["Costo unitario"]
    return df[df["Compra final"] > 0].copy()


def _register_fonts() -> None:
    if "Lato" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Lato", str(FONT_REGULAR)))
    if "Lato-Bold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Lato-Bold", str(FONT_BOLD)))


def _styles() -> dict:
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(name="POCompany", fontName="Lato", fontSize=10, leading=14, textColor=GRAY, alignment=TA_RIGHT))
    base.add(ParagraphStyle(name="POTitle", fontName="Lato-Bold", fontSize=20, leading=24, textColor=ACCENT))
    base.add(ParagraphStyle(name="POMeta", fontName="Lato", fontSize=11, leading=16, textColor=TEXT))
    base.add(ParagraphStyle(name="POCellText", fontName="Lato", fontSize=9, leading=11, textColor=TEXT))
    base.add(ParagraphStyle(name="PONotes", fontName="Lato", fontSize=10, leading=14, textColor=TEXT))
    return base


def _logo():
    if LOGO_PATH.exists():
        img = Image(str(LOGO_PATH), width=38 * mm, height=18 * mm)
        img.hAlign = "LEFT"
        return img
    return Paragraph("", getSampleStyleSheet()["Normal"])


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Lato", 8)
    canvas.setFillColor(GRAY)
    y = 13 * mm
    canvas.setStrokeColor(BORDER)
    canvas.line(doc.leftMargin, y + 6, A4[0] - doc.rightMargin, y + 6)
    canvas.drawString(doc.leftMargin, y, "Orden de compra emitida por Didacticos Jugando y Educando SAS")
    canvas.drawRightString(A4[0] - doc.rightMargin, y, f"Pagina {doc.page}")
    canvas.restoreState()


def _format_date(value) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def _format_cop(value) -> str:
    try:
        return "$ " + f"{float(value):,.0f}".replace(",", ".")
    except Exception:
        return "$ 0"


def _safe_suffix(value: str) -> str:
    return "".join(ch for ch in str(value).upper() if ch.isalnum())[:8] or "PUNTO"


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
