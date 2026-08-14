"""
A4ReceiptRenderer — ReportLab-based renderer for professional A4 invoice documents.
Used for A4 testing mode, PDF exports, and standard Windows desktop printers.
Does NOT stretch thermal receipts onto A4.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from pakpos.hardware.printer.base import ReceiptData
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class A4ReceiptRenderer:
    """Renders ReceiptData into an A4 PDF document."""

    def render_pdf(self, r: ReceiptData, target: str | Path | BinaryIO | None = None) -> bytes:
        """
        Generate A4 PDF bytes or write to target file/stream.
        Returns pdf content bytes.
        """
        buffer = io.BytesIO()
        output_dest = target if (target and not isinstance(target, (str, Path))) else buffer

        doc = SimpleDocTemplate(
            output_dest,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        # Custom styles
        style_title = ParagraphStyle(
            'InvoiceTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=26,
            textColor=colors.HexColor('#1a1d23'),
            alignment=TA_LEFT
        )

        style_subtitle = ParagraphStyle(
            'InvoiceSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#4b5563'),
            alignment=TA_LEFT
        )

        style_meta_label = ParagraphStyle(
            'MetaLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#374151')
        )

        style_meta_val = ParagraphStyle(
            'MetaVal',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#1f2937')
        )

        style_th = ParagraphStyle(
            'TH',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=11,
            textColor=colors.whitesmoke,
            alignment=TA_LEFT
        )
        style_th_r = ParagraphStyle('TH_R', parent=style_th, alignment=TA_RIGHT)

        style_td = ParagraphStyle(
            'TD',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#1f2937'),
            alignment=TA_LEFT
        )
        style_td_r = ParagraphStyle('TD_R', parent=style_td, alignment=TA_RIGHT)

        story = []

        # ─── HEADER: Shop Info & Invoice Header ───
        shop_details = [
            f"<b>{r.shop_name}</b>",
            r.shop_address,
            f"Phone: {r.shop_phone}",
        ]
        if r.tax_number:
            shop_details.append(f"NTN/STRN: {r.tax_number}")

        shop_p = Paragraph("<br/>".join(shop_details), style_subtitle)
        inv_type_str = "TAX INVOICE / RECEIPT" if not r.is_reprint else "DUPLICATE RECEIPT (REPRINT)"
        title_p = Paragraph(f"<b>{inv_type_str}</b>", style_title)

        header_table = Table([[shop_p, title_p]], colWidths=[320, 200])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 15))

        # ─── META DETAILS TABLE ───
        date_str = f"{r.sale_date} {r.sale_time}".strip() or r.created_at
        meta_data = [
            [
                Paragraph("<b>Invoice Number:</b>", style_meta_label),
                Paragraph(r.invoice_number, style_meta_val),
                Paragraph("<b>Date:</b>", style_meta_label),
                Paragraph(date_str, style_meta_val),
            ],
            [
                Paragraph("<b>Cashier:</b>", style_meta_label),
                Paragraph(r.cashier_name, style_meta_val),
                Paragraph("<b>Payment Method:</b>", style_meta_label),
                Paragraph(r.payment_method.upper(), style_meta_val),
            ]
        ]
        if r.customer_name:
            cust_str = r.customer_name
            if r.customer_phone:
                cust_str += f" ({r.customer_phone})"
            meta_data.append([
                Paragraph("<b>Customer:</b>", style_meta_label),
                Paragraph(cust_str, style_meta_val),
                Paragraph("", style_meta_label),
                Paragraph("", style_meta_val),
            ])

        meta_table = Table(meta_data, colWidths=[100, 160, 100, 160])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#edf2f7')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 15))

        # ─── LINE ITEMS TABLE ───
        items_data = [
            [
                Paragraph("#", style_th),
                Paragraph("Item Description", style_th),
                Paragraph("Qty", style_th_r),
                Paragraph("Unit Price (Rs.)", style_th_r),
                Paragraph("Total (Rs.)", style_th_r),
            ]
        ]

        for idx, item in enumerate(r.items, 1):
            name = str(item.get("name", ""))
            qty = f"{item.get('qty', 1):g}"
            price = f"{item.get('unit_price', 0):,.2f}"
            tot = f"{item.get('total', 0):,.2f}"
            items_data.append([
                Paragraph(str(idx), style_td),
                Paragraph(name, style_td),
                Paragraph(qty, style_td_r),
                Paragraph(price, style_td_r),
                Paragraph(tot, style_td_r),
            ])

        items_table = Table(items_data, colWidths=[30, 240, 60, 95, 95])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d6cdf')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 15))

        # ─── TOTALS & SUMMARY BLOCK ───
        summary_rows = [
            [Paragraph("Subtotal:", style_meta_label), Paragraph(f"Rs. {r.subtotal:,.2f}", style_td_r)],
        ]
        if r.discount > 0:
            summary_rows.append([Paragraph("Discount:", style_meta_label), Paragraph(f"-Rs. {r.discount:,.2f}", style_td_r)])
        if r.tax > 0:
            summary_rows.append([Paragraph("Tax:", style_meta_label), Paragraph(f"Rs. {r.tax:,.2f}", style_td_r)])

        summary_rows.append([
            Paragraph("<b>GRAND TOTAL:</b>", style_meta_label),
            Paragraph(f"<b>Rs. {r.total:,.2f}</b>", style_td_r)
        ])
        summary_rows.append([
            Paragraph("Paid Amount:", style_meta_label),
            Paragraph(f"Rs. {r.paid_amount:,.2f}", style_td_r)
        ])
        if r.change > 0:
            summary_rows.append([Paragraph("Change:", style_meta_label), Paragraph(f"Rs. {r.change:,.2f}", style_td_r)])
        if r.due_amount > 0:
            summary_rows.append([Paragraph("<b>Balance Due:</b>", style_meta_label), Paragraph(f"<b>Rs. {r.due_amount:,.2f}</b>", style_td_r)])

        summary_table = Table(summary_rows, colWidths=[120, 110])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
        ]))

        # Optional QR Code
        qr_flowable = None
        if r.qr_payload:
            try:
                import qrcode
                qr_img = qrcode.make(r.qr_payload)
                qr_buf = io.BytesIO()
                qr_img.save(qr_buf, format="PNG")
                qr_buf.seek(0)
                qr_flowable = RLImage(qr_buf, width=70, height=70)
            except Exception as e:
                logger.warning("Failed to generate QR code for PDF: %s", e)

        notes_p = Paragraph(f"<b>Terms / Notes:</b><br/>{r.footer}", style_subtitle)
        if qr_flowable:
            bottom_table = Table([[notes_p, qr_flowable, summary_table]], colWidths=[200, 90, 230])
        else:
            bottom_table = Table([[notes_p, summary_table]], colWidths=[290, 230])

        bottom_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (-1, 0), (-1, 0), 'RIGHT'),
        ]))
        story.append(KeepTogether(bottom_table))
        story.append(Spacer(1, 20))

        # Build PDF
        doc.build(story)

        pdf_bytes = buffer.getvalue()
        if isinstance(target, (str, Path)):
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_bytes(pdf_bytes)

        return pdf_bytes
