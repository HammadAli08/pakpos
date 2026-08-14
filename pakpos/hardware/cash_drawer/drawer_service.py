"""
CashDrawerService — Abstraction for cash drawer triggering.
Only triggers cash drawer kick for CASH sales when drawer support is enabled.
Does not raise exceptions — graceful fallback if unsupported or absent.
"""
from __future__ import annotations

from pakpos.hardware.printer.base import PrinterBackend
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class CashDrawerService:
    """Controls cash drawer opening logic."""

    @staticmethod
    def open_drawer_if_cash(
        payment_method: str,
        backend: PrinterBackend | None = None,
        enabled: bool = True,
    ) -> bool:
        """
        Trigger cash drawer opening if payment_method is CASH and feature enabled.
        """
        if not enabled:
            return False

        if str(payment_method).lower() != "cash":
            logger.debug("Cash drawer not triggered: payment method '%s' is not CASH", payment_method)
            return False

        if backend is None:
            from pakpos.hardware.printer.printer_manager import PrinterManager
            backend = PrinterManager().backend

        try:
            success = backend.trigger_cash_drawer()
            logger.info("Cash drawer open requested: success=%s", success)
            return success
        except Exception as e:
            logger.warning("Cash drawer trigger error (ignored): %s", e)
            return False
