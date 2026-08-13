"""
NumericPad — Touch-friendly on-screen numpad widget.
Emits `number_clicked(str)` and `action_clicked(str)` signals.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QGridLayout, QPushButton, QSizePolicy


class NumericPad(QWidget):
    """
    On-screen keypad for touch checkout counters.
    """
    digit_clicked = Signal(str)
    clear_clicked = Signal()
    enter_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        grid = QGridLayout(self)
        grid.setSpacing(6)

        buttons = [
            ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
            ("0", 3, 0), ("00", 3, 1), (".", 3, 2),
        ]

        for text, r, c in buttons:
            btn = QPushButton(text)
            btn.setObjectName("btn_secondary")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.clicked.connect(lambda _, t=text: self.digit_clicked.emit(t))
            grid.addWidget(btn, r, c)

        btn_clr = QPushButton("C")
        btn_clr.setObjectName("btn_danger")
        btn_clr.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        btn_clr.clicked.connect(self.clear_clicked.emit)
        grid.addWidget(btn_clr, 0, 3, 2, 1)

        btn_ent = QPushButton("OK")
        btn_ent.setObjectName("btn_success")
        btn_ent.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        btn_ent.clicked.connect(self.enter_clicked.emit)
        grid.addWidget(btn_ent, 2, 3, 2, 1)
