"""
BarcodeInput QLineEdit Widget.

Optimized for USB HID keyboard-wedge scanners.
Captures scanned text + Enter key cleanly.
Emits `barcode_scanned(str)` signal on completion.
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QLineEdit


class BarcodeInput(QLineEdit):
    """
    Dedicated QLineEdit for scanner and manual search input.
    """
    barcode_scanned = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("Scan Barcode or Search Product (F1 / Enter)...")
        self.setClearButtonEnabled(True)
        self.returnPressed.connect(self._on_return)

    def _on_return(self) -> None:
        text = self.text().strip()
        if text:
            self.barcode_scanned.emit(text)
            self.clear()
