"""
PrintService — Application print orchestrator.
Decouples POS sale completion and reprint workflows from physical printer backends.
Ensures print failures never throw or rollback database transactions.
"""
from __future__ import annotations

from pathlib import Path
from sqlalchemy.orm import Session

from pakpos.hardware.printer.base import PrinterBackend, PrintResult, PrintStatus, ReceiptData
from pakpos.hardware.printer.printer_manager import PrinterManager
from pakpos.hardware.printer.pdf_backend import PdfBackend
from pakpos.hardware.cash_drawer.drawer_service import CashDrawerService
from pakpos.services.sales_service import SalesService
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class PrintService:
    """Orchestrates receipt printing and PDF generation for sales."""

    def __init__(self, manager: PrinterManager | None = None) -> None:
        self.manager = manager or PrinterManager()

    def print_sale(
        self,
        sale_id: int,
        session: Session,
        backend: PrinterBackend | None = None,
        is_reprint: bool = False,
    ) -> PrintResult:
        """
        Fetch historical sale receipt data and print to configured backend.
        Must never raise exception — returns PrintResult.
        """
        try:
            sales_service = SalesService(session)
            receipt = sales_service.get_receipt_data(sale_id, is_reprint=is_reprint)

            target_backend = backend or self.manager.backend

            # Attempt receipt print
            result = target_backend.print_receipt(receipt)

            # Trigger cash drawer if cash sale
            if receipt.payment_method.lower() == "cash":
                CashDrawerService.open_drawer_if_cash(
                    payment_method=receipt.payment_method,
                    backend=target_backend,
                )

            logger.info(
                "PrintService print_sale: sale_id=%d invoice=%s success=%s status=%s",
                sale_id, receipt.invoice_number, result.success, result.status
            )
            return result

        except Exception as e:
            logger.error("PrintService failed to print sale #%d: %s", sale_id, e, exc_info=True)
            return PrintResult(
                status=PrintStatus.FAILED,
                error=f"Receipt print failed: {e}",
            )

    def reprint_sale(
        self,
        sale_id: int,
        session: Session,
        backend: PrinterBackend | None = None,
    ) -> PrintResult:
        """Reprint an existing completed sale with 'REPRINT' demarcation."""
        return self.print_sale(sale_id, session=session, backend=backend, is_reprint=True)

    def export_pdf(
        self,
        sale_id: int,
        session: Session,
        output_path: str | Path | None = None,
    ) -> PrintResult:
        """Export sale receipt directly to PDF file."""
        try:
            sales_service = SalesService(session)
            receipt = sales_service.get_receipt_data(sale_id)

            pdf_backend = PdfBackend()
            if output_path:
                pdf_backend.export_dir = Path(output_path).parent

            return pdf_backend.print_receipt(receipt)
        except Exception as e:
            logger.error("PrintService failed to export PDF for sale #%d: %s", sale_id, e, exc_info=True)
            return PrintResult(status=PrintStatus.FAILED, error=str(e))
