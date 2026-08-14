"""
AppEvents — Centralized application event bus for decoupled signal propagation.
Emits Qt signals when core business actions occur (sales, inventory changes, customer updates).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AppEvents(QObject):
    """Global event bus instance."""
    sale_completed = Signal(int)       # sale_id
    sale_voided = Signal(int)          # sale_id
    inventory_changed = Signal(int)    # product_id (or 0 for bulk)
    customer_changed = Signal(int)     # customer_id (or 0 for general balance changes)


# Global singleton instance
app_events = AppEvents()
