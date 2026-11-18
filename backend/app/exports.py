"""Exportación de los reportes a Excel (.xlsx) y PDF."""
from datetime import date, datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

TEAL = "0E6B6B"


def _fmt(value, kind) -> str:
    if value is None or value == "":
        return "—"
    if kind == "date" and isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if kind == "float":
        return f"{value:.1f}"
    return str(value)


def to_xlsx(report: dict, subtitle: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = report["title"][:31].replace("/", "-").replace(":", "-")
    cols = report["columns"]
    ws.cell(row=1, column=1, value=report["title"]).font = Font(bold=True, size=14, color=TEAL)
    ws.cell(row=2, column=1, value=subtitle).font = Font(italic=True, color="5B727A")
    head = 4
    for j, c in enumerate(cols, 1):
        cell = ws.cell(row=head, column=j, value=c["label"])
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=TEAL)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for i, row in enumerate(report["rows"], head + 1):
        bold = row.get(cols[0]["key"]) == "TOTAL"
        for j, c in enumerate(cols, 1):
            v = row.get(c["key"])
            cell = ws.cell(row=i, column=j, value=v)
            if c["kind"] == "date":
                cell.number_format = "DD/MM/YYYY"
            elif c["kind"] == "float":
                cell.number_format = "0.0"
            if bold:
                cell.font = Font(bold=True)
    for j, c in enumerate(cols, 1):
        longest = max([len(c["label"])] + [len(_fmt(r.get(c["key"]), c["kind"])) for r in report["rows"]])
        ws.column_dimensions[get_column_letter(j)].width = min(max(12, longest + 2), 60)
    ws.freeze_panes = ws.cell(row=head + 1, column=1)
    if report["rows"]:
        ws.auto_filter.ref = f"A{head}:{get_column_letter(len(cols))}{head + len(report['rows'])}"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_pdf(report: dict, subtitle: str) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=report["title"], author="SCCVI")
    ss = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=ss["Title"], textColor=colors.HexColor("#" + TEAL), alignment=0, fontSize=18)
    sub = ParagraphStyle("s", parent=ss["Normal"], textColor=colors.HexColor("#5B727A"), fontSize=9)
    cell = ParagraphStyle("c", parent=ss["Normal"], fontSize=8, leading=10)
    head = ParagraphStyle("h", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")

    cols = report["columns"]
    data = [[Paragraph(escape(c["label"]), head) for c in cols]]
    for r in report["rows"]:
        data.append([Paragraph(escape(_fmt(r.get(c["key"]), c["kind"])), cell) for c in cols])
    story = [Paragraph(escape(report["title"]), title), Paragraph(escape(subtitle), sub), Spacer(1, 10)]
    if report["rows"]:
        weights = [3 if c["kind"] == "text" and c["key"] in ("name", "community", "group") else
                   6 if c["key"] == "detail" else 1.4 for c in cols]
        width = landscape(A4)[0] - 3 * cm
        t = Table(data, colWidths=[width * w / sum(weights) for w in weights], repeatRows=1)
        style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + TEAL)),
                 ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F7F6")]),
                 ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D3E0DE")),
                 ("VALIGN", (0, 0), (-1, -1), "TOP")]
        if report["rows"][-1].get(cols[0]["key"]) == "TOTAL":
            style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E1EFEC")))
        t.setStyle(TableStyle(style))
        story.append(t)
    else:
        story.append(Paragraph("No hay registros para este reporte.", ss["Normal"]))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#5B727A"))
        canvas.drawString(1.5 * cm, 0.9 * cm, "SCCVI · Sistema de Control de Crecimiento y Vacunación Infantil")
        canvas.drawRightString(landscape(A4)[0] - 1.5 * cm, 0.9 * cm, f"Página {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def stamp(community: str | None, user_name: str) -> str:
    where = f"Comunidad: {community}" if community else "Todas las comunidades"
    return f"{where} · Generado el {datetime.now():%d/%m/%Y %H:%M} por {user_name}"
