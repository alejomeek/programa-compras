from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer
from reportlab.platypus.tableofcontents import TableOfContents


BASE_DIR = Path(__file__).resolve().parents[1]
MD_PATH = BASE_DIR / "INSTRUCTIVO_USO_APP_COMPRAS.md"
PDF_PATH = BASE_DIR / "INSTRUCTIVO_USO_APP_COMPRAS.pdf"
LOGO_PATH = BASE_DIR / "logo transparente.png"
FONT_REGULAR = BASE_DIR / "assets" / "fonts" / "Lato-Regular.ttf"
FONT_BOLD = BASE_DIR / "assets" / "fonts" / "Lato-Bold.ttf"


def main() -> None:
    font_name, bold_name = register_fonts()
    styles = build_styles(font_name, bold_name)
    story = build_story(styles)
    doc = InstructivoDoc(
        str(PDF_PATH),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.75 * inch,
        title="Instructivo App de Compras Jugando y Educando",
    )
    doc.multiBuild(story, onFirstPage=footer(font_name), onLaterPages=footer(font_name))
    print(PDF_PATH)


def register_fonts() -> tuple[str, str]:
    if FONT_REGULAR.exists() and FONT_BOLD.exists():
        pdfmetrics.registerFont(TTFont("Lato", str(FONT_REGULAR)))
        pdfmetrics.registerFont(TTFont("Lato-Bold", str(FONT_BOLD)))
        return "Lato", "Lato-Bold"
    return "Helvetica", "Helvetica-Bold"


def build_styles(font_name: str, bold_name: str) -> dict:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            fontName=bold_name,
            fontSize=24,
            leading=30,
            textColor=colors.HexColor("#9B5B39"),
            alignment=TA_CENTER,
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSub",
            fontName=font_name,
            fontSize=12,
            leading=17,
            textColor=colors.HexColor("#555555"),
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1Custom",
            fontName=bold_name,
            fontSize=18,
            leading=23,
            textColor=colors.HexColor("#9B5B39"),
            spaceBefore=14,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2Custom",
            fontName=bold_name,
            fontSize=13.5,
            leading=18,
            textColor=colors.HexColor("#333333"),
            spaceBefore=12,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyCustom",
            fontName=font_name,
            fontSize=9.8,
            leading=14.2,
            textColor=colors.HexColor("#333333"),
            spaceAfter=6,
        )
    )
    styles.add(ParagraphStyle(name="BulletCustom", parent=styles["BodyCustom"], leftIndent=18, firstLineIndent=-8, spaceAfter=3))
    styles.add(ParagraphStyle(name="NumberCustom", parent=styles["BodyCustom"], leftIndent=20, firstLineIndent=-16, spaceAfter=3))
    return styles


INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def format_inline(text: str) -> str:
    text = escape(text)
    text = INLINE_CODE_RE.sub(r'<font name="Courier" backColor="#F5F5F5">\1</font>', text)
    return BOLD_RE.sub(r"<b>\1</b>", text)


def flush_list(story: list, items: list[str], styles: dict, ordered: bool = False) -> None:
    if not items:
        return
    for idx, item in enumerate(items, start=1):
        prefix = f"{idx}." if ordered else "-"
        style_name = "NumberCustom" if ordered else "BulletCustom"
        story.append(Paragraph(f"{prefix}&nbsp;&nbsp;{format_inline(item)}", styles[style_name]))
    story.append(Spacer(1, 4))
    items.clear()


def build_story(styles: dict) -> list:
    story: list = []
    if LOGO_PATH.exists():
        image = Image(str(LOGO_PATH), width=1.7 * inch, height=0.8 * inch)
        image.hAlign = "CENTER"
        story.append(image)
        story.append(Spacer(1, 30))

    story.append(Paragraph("Instructivo de uso", styles["CoverTitle"]))
    story.append(Paragraph("App de Compras Jugando y Educando", styles["CoverSub"]))
    story.append(Spacer(1, 18))
    story.append(
        Paragraph(
            "Guia amigable para cargar archivos, interpretar resultados, preparar cantidades finales y generar ordenes de compra en PDF.",
            styles["CoverSub"],
        )
    )
    story.append(PageBreak())

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(fontName="Lato", fontSize=10, name="TOCHeading1", leftIndent=0, firstLineIndent=0, spaceBefore=4, leading=13),
        ParagraphStyle(fontName="Lato", fontSize=9, name="TOCHeading2", leftIndent=12, firstLineIndent=0, spaceBefore=2, leading=12),
    ]
    story.append(Paragraph("Contenido", styles["H1Custom"]))
    story.append(toc)
    story.append(PageBreak())

    list_items: list[str] = []
    ordered = False
    for raw_line in MD_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line:
            flush_list(story, list_items, styles, ordered)
            story.append(Spacer(1, 2))
            continue
        if line.startswith("# "):
            flush_list(story, list_items, styles, ordered)
            continue
        if line.startswith("## "):
            flush_list(story, list_items, styles, ordered)
            story.append(Paragraph(format_inline(line[3:].strip()), styles["H1Custom"]))
            continue
        if line.startswith("### "):
            flush_list(story, list_items, styles, ordered)
            story.append(Paragraph(format_inline(line[4:].strip()), styles["H2Custom"]))
            continue

        bullet_match = re.match(r"^-\s+(.*)", line)
        ordered_match = re.match(r"^\d+\.\s+(.*)", line)
        if bullet_match:
            if list_items and ordered:
                flush_list(story, list_items, styles, ordered)
            ordered = False
            list_items.append(bullet_match.group(1))
            continue
        if ordered_match:
            if list_items and not ordered:
                flush_list(story, list_items, styles, ordered)
            ordered = True
            list_items.append(ordered_match.group(1))
            continue

        flush_list(story, list_items, styles, ordered)
        if line.startswith("**") and line.endswith("**"):
            story.append(Paragraph(format_inline(line), styles["H2Custom"]))
        elif line.startswith("```"):
            continue
        else:
            story.append(Paragraph(format_inline(line), styles["BodyCustom"]))

    flush_list(story, list_items, styles, ordered)
    return story


class InstructivoDoc(SimpleDocTemplate):
    def afterFlowable(self, flowable) -> None:
        if not isinstance(flowable, Paragraph):
            return
        text = flowable.getPlainText()
        if flowable.style.name == "H1Custom":
            key = f"h1-{text}"
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (0, text, self.page, key))
        elif flowable.style.name == "H2Custom":
            key = f"h2-{self.page}-{text}"
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (1, text, self.page, key))


def footer(font_name: str):
    def draw(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.line(doc.leftMargin, 0.55 * inch, letter[0] - doc.rightMargin, 0.55 * inch)
        canvas.drawString(doc.leftMargin, 0.38 * inch, "Jugando y Educando - App de Compras")
        canvas.drawRightString(letter[0] - doc.rightMargin, 0.38 * inch, f"Pagina {doc.page}")
        canvas.restoreState()

    return draw


if __name__ == "__main__":
    main()
