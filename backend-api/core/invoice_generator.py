"""Invoice PDF generation using ReportLab for order completion.

Generates professional invoices in PDF format with:
- Order details (number, date, total)
- Customer information
- Item line items with prices
- Tax calculation
- Payment method
- Company branding
- Digital signature (optional)
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

logger = logging.getLogger("diomika-invoice")


class InvoiceGenerator:
    """Generate professional invoices in PDF format."""

    def __init__(self, company_name: str = "Diomika", company_email: str = "billing@diomika.com"):
        self.company_name = company_name
        self.company_email = company_email
        self.pagesize = A4

    def generate_invoice_pdf(
        self,
        order_id: str,
        customer_name: str,
        customer_email: str,
        customer_address: str,
        order_date: datetime,
        due_date: Optional[datetime] = None,
        items: list[dict] = None,
        subtotal: Decimal = Decimal("0"),
        tax_rate: Decimal = Decimal("0.23"),
        notes: Optional[str] = None,
    ) -> bytes:
        """Generate invoice PDF and return bytes."""
        if items is None:
            items = []

        # Calculate totals
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount

        # Create PDF buffer
        pdf_buffer = io.BytesIO()

        # Create document
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=self.pagesize,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )

        # Build content
        elements = []

        # Header with company info
        elements.append(self._build_header())
        elements.append(Spacer(1, 0.2 * inch))

        # Invoice title and number
        title_style = ParagraphStyle(
            "InvoiceTitle",
            parent=getSampleStyleSheet()["Heading1"],
            fontSize=24,
            textColor=colors.HexColor("#1a1a1a"),
            spaceAfter=6,
        )
        elements.append(Paragraph(f"Invoice #{order_id}", title_style))
        elements.append(Spacer(1, 0.1 * inch))

        # Invoice details (date, due date)
        details_data = [
            ["Invoice Date:", order_date.strftime("%Y-%m-%d")],
            ["Due Date:", (due_date or order_date).strftime("%Y-%m-%d")],
            ["Order ID:", order_id],
        ]
        details_table = Table(details_data, colWidths=[1.5 * inch, 2 * inch])
        details_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(details_table)
        elements.append(Spacer(1, 0.2 * inch))

        # Bill to section
        elements.append(self._build_bill_to_section(customer_name, customer_email, customer_address))
        elements.append(Spacer(1, 0.2 * inch))

        # Line items table
        elements.append(self._build_items_table(items))
        elements.append(Spacer(1, 0.2 * inch))

        # Totals
        elements.append(self._build_totals_table(subtotal, tax_rate, tax_amount, total))
        elements.append(Spacer(1, 0.2 * inch))

        # Notes if provided
        if notes:
            elements.append(self._build_notes_section(notes))
            elements.append(Spacer(1, 0.2 * inch))

        # Footer
        elements.append(self._build_footer())

        # Build PDF
        doc.build(elements)

        # Get PDF bytes
        pdf_buffer.seek(0)
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()

        logger.info(f"Invoice {order_id} generated successfully ({len(pdf_bytes)} bytes)")
        return pdf_bytes

    def _build_header(self):
        """Build company header section."""
        header_style = ParagraphStyle(
            "CompanyHeader",
            parent=getSampleStyleSheet()["Normal"],
            fontSize=14,
            textColor=colors.HexColor("#2563eb"),
            fontName="Helvetica-Bold",
        )
        return Paragraph(self.company_name, header_style)

    def _build_bill_to_section(self, customer_name: str, customer_email: str, customer_address: str):
        """Build bill to section."""
        bill_style = ParagraphStyle(
            "BillTo",
            parent=getSampleStyleSheet()["Normal"],
            fontSize=10,
            fontName="Helvetica",
        )

        title_style = ParagraphStyle(
            "BillToTitle",
            parent=getSampleStyleSheet()["Normal"],
            fontSize=11,
            fontName="Helvetica-Bold",
        )

        elements = []
        elements.append(Paragraph("Bill To:", title_style))
        elements.append(Paragraph(f"<b>{customer_name}</b>", bill_style))
        elements.append(Paragraph(customer_email, bill_style))
        elements.append(Paragraph(customer_address.replace("\n", "<br/>"), bill_style))

        return elements

    def _build_items_table(self, items: list[dict]):
        """Build line items table."""
        # Header row
        data = [
            ["Description", "Quantity", "Unit Price", "Amount"],
        ]

        # Item rows
        for item in items:
            quantity = Decimal(str(item.get("quantity", 0)))
            unit_price = Decimal(str(item.get("unit_price", 0)))
            amount = quantity * unit_price

            data.append(
                [
                    item.get("description", ""),
                    str(quantity),
                    f"${unit_price:.2f}",
                    f"${amount:.2f}",
                ]
            )

        # Create table with proper column widths
        table = Table(data, colWidths=[3 * inch, 1 * inch, 1.25 * inch, 1.25 * inch])

        # Style the table
        table.setStyle(
            TableStyle(
                [
                    # Header
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    # Body
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 1), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
                    # Lines
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ]
            )
        )

        return table

    def _build_totals_table(
        self,
        subtotal: Decimal,
        tax_rate: Decimal,
        tax_amount: Decimal,
        total: Decimal,
    ):
        """Build totals section."""
        data = [
            ["Subtotal:", f"${subtotal:.2f}"],
            ["Tax (23%):", f"${tax_amount:.2f}"],
            ["Total:", f"${total:.2f}"],
        ]

        table = Table(data, colWidths=[4.5 * inch, 1.25 * inch])

        table.setStyle(
            TableStyle(
                [
                    # Subtotal row
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    # Tax row
                    ("FONTNAME", (0, 1), (0, 1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, 1), 10),
                    ("ALIGN", (1, 1), (1, 1), "RIGHT"),
                    # Total row
                    ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#dbeafe")),
                    ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 2), (-1, 2), 12),
                    ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#1e40af")),
                    ("ALIGN", (1, 2), (1, 2), "RIGHT"),
                    ("TOPPADDING", (0, 2), (-1, 2), 8),
                    ("BOTTOMPADDING", (0, 2), (-1, 2), 8),
                ]
            )
        )

        return table

    def _build_notes_section(self, notes: str):
        """Build notes section."""
        notes_style = ParagraphStyle(
            "Notes",
            parent=getSampleStyleSheet()["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#6b7280"),
        )

        title_style = ParagraphStyle(
            "NotesTitle",
            parent=getSampleStyleSheet()["Normal"],
            fontSize=10,
            fontName="Helvetica-Bold",
        )

        elements = []
        elements.append(Paragraph("Notes:", title_style))
        elements.append(Paragraph(notes.replace("\n", "<br/>"), notes_style))

        return elements

    def _build_footer(self):
        """Build footer section."""
        footer_style = ParagraphStyle(
            "Footer",
            parent=getSampleStyleSheet()["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#9ca3af"),
            alignment=TA_CENTER,
        )

        footer_text = f"Thank you for your business! | {self.company_name} • {self.company_email}"
        return Paragraph(footer_text, footer_style)


# Global instance
_invoice_generator: Optional[InvoiceGenerator] = None


def get_invoice_generator() -> InvoiceGenerator:
    """Get global invoice generator instance."""
    global _invoice_generator
    if _invoice_generator is None:
        _invoice_generator = InvoiceGenerator()
    return _invoice_generator
