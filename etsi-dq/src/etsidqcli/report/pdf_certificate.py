"""PDF certificate generator."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
except ImportError:
    raise ImportError("PDF dependencies not installed. Run: pip install reportlab qrcode pillow")


def generate_certificate(
    certificate_key: str,
    user_name: str,
    organization: str,
    dataset_name: str,
    overall_score: float,
    overall_grade: str,
    metrics: dict[str, dict[str, Any]],
    evaluated_at: str,
    issued_at: str,
    verify_url: str = "",
    output_path: str | None = None,
) -> str:
    """Generate a PDF certificate.

    Returns the file path where the PDF was saved.
    """
    if output_path is None:
        output_path = f"certificate_{certificate_key}.pdf"

    w, h = A4  # 595 x 842 points

    c = canvas.Canvas(output_path, pagesize=A4)

    # Colors
    black = HexColor("#111111")
    gray = HexColor("#666666")
    light_gray = HexColor("#CCCCCC")
    dark = HexColor("#1a1a1a")

    # ── Border ──
    margin = 28 * mm
    c.setStrokeColor(light_gray)
    c.setLineWidth(1.5)
    c.rect(margin - 10, margin - 10, w - 2 * margin + 20, h - 2 * margin + 20)
    c.setLineWidth(0.5)
    c.rect(margin - 6, margin - 6, w - 2 * margin + 12, h - 2 * margin + 12)

    # ── Header ──
    y = h - margin - 20

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(gray)
    c.drawCentredString(w / 2, y, "ETSI DATA QUALITY FRAMEWORK")
    y -= 36

    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(dark)
    c.drawCentredString(w / 2, y, "Data Quality Certificate")
    y -= 18

    c.setStrokeColor(light_gray)
    c.setLineWidth(0.5)
    c.line(margin + 20, y, w - margin - 20, y)
    y -= 32

    # ── Certificate key ──
    c.setFont("Helvetica", 9)
    c.setFillColor(gray)
    c.drawCentredString(w / 2, y, "CERTIFICATE KEY")
    y -= 20

    c.setFont("Courier-Bold", 16)
    c.setFillColor(dark)
    c.drawCentredString(w / 2, y, certificate_key)
    y -= 40

    # ── Main info ──
    def draw_field(label: str, value: str, y_pos: float) -> float:
        c.setFont("Helvetica", 9)
        c.setFillColor(gray)
        c.drawString(margin + 20, y_pos, label)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(dark)
        c.drawString(margin + 20, y_pos - 16, str(value))
        return y_pos - 40

    y = draw_field("EVALUATED BY", user_name, y)
    y = draw_field("ORGANIZATION", organization or "—", y)
    y = draw_field("DATASET", dataset_name, y)

    # ── Score section ──
    y -= 10
    c.setStrokeColor(light_gray)
    c.line(margin + 20, y, w - margin - 20, y)
    y -= 28

    c.setFont("Helvetica", 9)
    c.setFillColor(gray)
    c.drawString(margin + 20, y, "OVERALL SCORE")

    score_text = f"{overall_score:.1%}"
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(dark)
    c.drawString(margin + 20, y - 30, score_text)

    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(gray)
    c.drawString(margin + 120, y - 30, f"({overall_grade})")
    y -= 70

    # ── Metrics table ──
    c.setFont("Helvetica", 9)
    c.setFillColor(gray)
    c.drawString(margin + 20, y, "METRIC")
    c.drawString(w / 2 - 10, y, "SCORE")
    c.drawString(w / 2 + 60, y, "GRADE")
    c.drawString(w / 2 + 120, y, "STATUS")
    y -= 6

    c.setStrokeColor(light_gray)
    c.line(margin + 20, y, w - margin - 20, y)
    y -= 18

    for name, m in metrics.items():
        score = m.get("score", 0)
        grade_val = m.get("grade", "—")
        passed = m.get("passed", True)

        c.setFont("Helvetica", 10)
        c.setFillColor(dark)
        c.drawString(margin + 20, y, name.title())

        c.setFont("Courier", 10)
        c.drawString(w / 2 - 10, y, f"{score:.1%}")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(w / 2 + 60, y, grade_val)

        c.setFont("Helvetica", 10)
        if passed:
            c.setFillColor(HexColor("#166534"))
            c.drawString(w / 2 + 120, y, "PASS")
        else:
            c.setFillColor(HexColor("#991B1B"))
            c.drawString(w / 2 + 120, y, "FAIL")

        y -= 20

    # ── Timestamps ──
    y -= 20
    c.setStrokeColor(light_gray)
    c.line(margin + 20, y, w - margin - 20, y)
    y -= 24

    c.setFont("Helvetica", 9)
    c.setFillColor(gray)

    eval_display = evaluated_at[:19] if evaluated_at else "—"
    issue_display = issued_at[:19] if issued_at else "—"

    c.drawString(margin + 20, y, f"Evaluated: {eval_display}")
    c.drawString(w / 2 + 20, y, f"Issued: {issue_display}")
    y -= 30

    # ── QR code ──
    if verify_url:
        try:
            import qrcode

            qr = qrcode.QRCode(version=1, box_size=3, border=2)
            qr.add_data(verify_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")

            buf = io.BytesIO()
            qr_img.save(buf, format="PNG")
            buf.seek(0)

            from reportlab.lib.utils import ImageReader
            img = ImageReader(buf)
            qr_size = 60
            c.drawImage(img, w - margin - qr_size - 10, y - qr_size + 20, qr_size, qr_size)

            c.setFont("Helvetica", 7)
            c.setFillColor(gray)
            c.drawString(w - margin - qr_size - 10, y - qr_size + 10, "Scan to verify")
        except ImportError:
            pass

    # ── Footer ──
    c.setFont("Helvetica", 8)
    c.setFillColor(light_gray)
    c.drawCentredString(w / 2, margin + 10, "This certificate was generated by ETSI Data Quality Framework")
    c.drawCentredString(w / 2, margin, f"Verify at: {verify_url}" if verify_url else "")

    c.save()
    return output_path
