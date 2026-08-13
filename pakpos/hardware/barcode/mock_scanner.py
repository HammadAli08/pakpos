"""
MockBarcodeScanner — used in tests.
Simulates barcode scanning without real hardware.
Real scanner is USB HID keyboard-wedge — handled via BarcodeInput QLineEdit widget.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ScanEvent:
    barcode: str
    timestamp: datetime


class MockBarcodeScanner:
    """
    Test barcode scanner.
    Tests call simulate_scan() to inject a barcode.
    """

    def __init__(self) -> None:
        self._scan_events: list[ScanEvent] = []
        self._last_scan: ScanEvent | None = None

    def simulate_scan(self, barcode: str) -> ScanEvent:
        event = ScanEvent(barcode=barcode, timestamp=datetime.now(timezone.utc))
        self._scan_events.append(event)
        self._last_scan = event
        return event

    @property
    def last_scan(self) -> ScanEvent | None:
        return self._last_scan

    @property
    def scan_count(self) -> int:
        return len(self._scan_events)

    def clear(self) -> None:
        self._scan_events.clear()
        self._last_scan = None
