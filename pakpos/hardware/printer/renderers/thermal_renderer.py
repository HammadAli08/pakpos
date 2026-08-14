"""
ThermalReceiptRenderer — Layout engine for 80mm/58mm thermal receipts.
Calculates column layout dynamically and formats receipt text cleanly.
Does NOT execute hardware commands; outputs clean structured ReceiptLine objects or plain text.
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from enum import Enum
from pakpos.hardware.printer.base import ReceiptData, PrinterProfile


class LineAlignment(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class FontSize(str, Enum):
    NORMAL = "normal"
    LARGE = "large"
    DOUBLE_HEIGHT = "double_height"


@dataclass
class ReceiptLine:
    """A single logical line or instruction on a receipt."""
    text: str = ""
    align: LineAlignment = LineAlignment.LEFT
    bold: bool = False
    size: FontSize = FontSize.NORMAL
    is_separator: bool = False
    is_cut: bool = False
    is_qr: bool = False
    qr_data: str | None = None
    is_barcode: bool = False
    barcode_data: str | None = None
    is_logo: bool = False
    logo_path: str | None = None


class ThermalReceiptRenderer:
    """Renders ReceiptData into structured ReceiptLine items and ASCII representations."""

    def __init__(self, profile: PrinterProfile | None = None) -> None:
        self.profile = profile or PrinterProfile()

    def get_columns(self, paper_width_mm: int) -> int:
        """Determine number of columns based on paper width."""
        if paper_width_mm <= 58:
            return 40
        return self.profile.columns if self.profile.columns else 48

    def render_lines(self, r: ReceiptData) -> list[ReceiptLine]:
        """Convert ReceiptData to an ordered list of ReceiptLine instructions."""
        width = self.get_columns(r.paper_width_mm)
        lines: list[ReceiptLine] = []

        # 1. Logo (if configured)
        if r.logo_path:
            lines.append(ReceiptLine(is_logo=True, logo_path=r.logo_path, align=LineAlignment.CENTER))

        # 2. Shop Header
        lines.append(ReceiptLine(r.shop_name, align=LineAlignment.CENTER, bold=True, size=FontSize.LARGE))
        if r.shop_address:
            lines.append(ReceiptLine(r.shop_address, align=LineAlignment.CENTER))
        if r.shop_phone:
            lines.append(ReceiptLine(f"Ph: {r.shop_phone}", align=LineAlignment.CENTER))
        if r.tax_number:
            lines.append(ReceiptLine(f"NTN/STRN: {r.tax_number}", align=LineAlignment.CENTER))

        lines.append(ReceiptLine(r.shop_name if not r.is_reprint else "*** SALE REPRINT ***", align=LineAlignment.CENTER, bold=r.is_reprint))
        lines.append(ReceiptLine(is_separator=True))

        # 3. Meta Details
        lines.append(ReceiptLine(f"Invoice: {r.invoice_number}", bold=True))
        date_str = r.sale_date or r.created_at
        if date_str:
            lines.append(ReceiptLine(f"Date: {date_str} {r.sale_time}".strip()))
        lines.append(ReceiptLine(f"Cashier: {r.cashier_name}"))

        if r.customer_name:
            cust_line = f"Customer: {r.customer_name}"
            if r.customer_phone:
                cust_line += f" ({r.customer_phone})"
            lines.append(ReceiptLine(cust_line))

        lines.append(ReceiptLine(is_separator=True))

        # 4. Item Table Headers
        # Columns layout: Name (left), Qty (right), Price (right), Total (right)
        if width <= 40:
            # 58mm compact headers: ITEM (18) QTY (4) TOTAL (16)
            name_w, qty_w, tot_w = 18, 5, 15
            hdr = f"{'ITEM':<{name_w}}{'QTY':>{qty_w}}{'TOTAL':>{tot_w}}"
            lines.append(ReceiptLine(hdr, bold=True))
            lines.append(ReceiptLine(is_separator=True))

            for item in r.items:
                name = str(item.get("name", ""))
                qty = f"{item.get('qty', 1):g}"
                tot = f"Rs.{item.get('total', 0):,.2f}"
                # Wrap item name if longer than column width
                wrapped_name = textwrap.wrap(name, width=name_w)
                if not wrapped_name:
                    wrapped_name = [""]

                first_line = f"{wrapped_name[0]:<{name_w}}{qty:>{qty_w}}{tot:>{tot_w}}"
                lines.append(ReceiptLine(first_line))
                for extra in wrapped_name[1:]:
                    lines.append(ReceiptLine(f"{extra:<{name_w}}"))
        else:
            # 80mm header: ITEM (20) QTY (5) PRICE (10) TOTAL (11)
            name_w, qty_w, prc_w, tot_w = 20, 5, 11, 10
            hdr = f"{'ITEM':<{name_w}}{'QTY':>{qty_w}}{'PRICE':>{prc_w}}{'TOTAL':>{tot_w}}"
            lines.append(ReceiptLine(hdr, bold=True))
            lines.append(ReceiptLine(is_separator=True))

            for item in r.items:
                name = str(item.get("name", ""))
                qty = f"{item.get('qty', 1):g}"
                price = f"{item.get('unit_price', 0):,.2f}"
                tot = f"{item.get('total', 0):,.2f}"

                wrapped_name = textwrap.wrap(name, width=name_w)
                if not wrapped_name:
                    wrapped_name = [""]

                first_line = f"{wrapped_name[0]:<{name_w}}{qty:>{qty_w}}{price:>{prc_w}}{tot:>{tot_w}}"
                lines.append(ReceiptLine(first_line))
                for extra in wrapped_name[1:]:
                    lines.append(ReceiptLine(f"{extra:<{name_w}}"))

        lines.append(ReceiptLine(is_separator=True))

        # 5. Financial Summary Box
        label_w = width - 14
        val_w = 14

        lines.append(ReceiptLine(f"{'Subtotal':<{label_w}}{f'Rs.{r.subtotal:,.2f}':>{val_w}}"))
        if r.discount > 0:
            lines.append(ReceiptLine(f"{'Discount':<{label_w}}{f'-Rs.{r.discount:,.2f}':>{val_w}}"))
        if r.tax > 0:
            lines.append(ReceiptLine(f"{'Tax':<{label_w}}{f'Rs.{r.tax:,.2f}':>{val_w}}"))

        lines.append(ReceiptLine(f"{'TOTAL':<{label_w}}{f'Rs.{r.total:,.2f}':>{val_w}}", bold=True, size=FontSize.NORMAL))
        lines.append(ReceiptLine(is_separator=True))

        # 6. Payment Info
        pay_str = f"{'Payment (' + r.payment_method.upper() + ')':<{label_w}}{f'Rs.{r.paid_amount:,.2f}':>{val_w}}"
        lines.append(ReceiptLine(pay_str))
        if r.change > 0:
            lines.append(ReceiptLine(f"{'Change':<{label_w}}{f'Rs.{r.change:,.2f}':>{val_w}}"))
        if r.due_amount > 0:
            lines.append(ReceiptLine(f"{'Balance Due (Khata)':<{label_w}}{f'Rs.{r.due_amount:,.2f}':>{val_w}}", bold=True))

        lines.append(ReceiptLine(is_separator=True))

        # 7. QR Code / Barcode (if present)
        if r.qr_payload:
            lines.append(ReceiptLine(is_qr=True, qr_data=r.qr_payload, align=LineAlignment.CENTER))

        # 8. Footer Message
        if r.footer:
            for footer_line in r.footer.split("\n"):
                lines.append(ReceiptLine(footer_line.strip(), align=LineAlignment.CENTER))

        lines.append(ReceiptLine(is_cut=True))
        return lines

    def render_to_text(self, r: ReceiptData) -> str:
        """Render receipt directly to formatted plain text string."""
        width = self.get_columns(r.paper_width_mm)
        sep_char = "-" * width
        lines = self.render_lines(r)

        output: list[str] = []
        for line in lines:
            if line.is_cut:
                continue
            if line.is_separator:
                output.append(sep_char)
                continue
            if line.is_qr:
                output.append(f"[QR: {line.qr_data}]".center(width))
                continue
            if line.is_logo:
                output.append("[SHOP LOGO]".center(width))
                continue

            txt = line.text
            if line.align == LineAlignment.CENTER:
                output.append(txt.center(width))
            elif line.align == LineAlignment.RIGHT:
                output.append(txt.rjust(width))
            else:
                output.append(txt.ljust(width))

        return "\n".join(output)
