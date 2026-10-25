from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
)


def generate_pdf(title: str, content: str) -> bytes:
    # Create a PDF in memory instead of saving it on the server
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title=title,
        author="DraftMate AI",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocumentTitle",
        parent=styles["Title"],
        fontSize=19,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#243B64"),
        spaceAfter=8 * mm,
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#243B64"),
        spaceBefore=5 * mm,
        spaceAfter=2 * mm,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "DocumentBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=15,
        spaceAfter=3 * mm,
        splitLongWords=True,
    )

    story = [
        Paragraph(escape(title), title_style),
        HRFlowable(
            width="100%",
            thickness=1,
            color=colors.HexColor("#CBD5E1"),
        ),
        Spacer(1, 5 * mm),
    ]

    # Convert the generated text into readable PDF paragraphs
    for line in content.splitlines():
        line = line.strip()

        if not line:
            story.append(Spacer(1, 2 * mm))
            continue

        safe_line = escape(line)

        # Recognize common headings and numbered sections
        if (
            line.startswith("# ")
            or line.startswith("## ")
            or line.startswith("### ")
        ):
            heading = line.lstrip("#").strip()
            story.append(Paragraph(escape(heading), heading_style))

        elif len(line) < 100 and (
            line.isupper()
            or (
                line[:1].isdigit()
                and (". " in line[:5] or ") " in line[:5])
            )
        ):
            story.append(Paragraph(safe_line, heading_style))

        else:
            story.append(Paragraph(safe_line, body_style))

    # Add a footer to every page
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.line(22 * mm, 15 * mm, A4[0] - 22 * mm, 15 * mm)

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(22 * mm, 10 * mm, "Generated with DraftMate AI")
        canvas.drawRightString(
            A4[0] - 22 * mm,
            10 * mm,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=add_footer,
        onLaterPages=add_footer,
    )

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes