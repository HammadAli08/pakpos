"""
ProductGridWidget — Professional product card grid with category filter tabs.
Designed for cashier terminal speed and visual clarity.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, List

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QSizePolicy, QStyleOption, QStyle
)

from pakpos.database.engine import get_session
from pakpos.database.repositories.product_repo import ProductRepository
from pakpos.database.models.category import Category
from pakpos.database.models.product import Product
from pakpos.utils.formatters import format_currency
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class ProductCard(QFrame):
    """
    Visual Product Card for retail cashier selection.
    Displays product name, selling price, and stock status badge.
    """
    clicked = Signal(object)  # Emits Product
    out_of_stock_clicked = Signal(object)  # Emits Product

    def __init__(self, product: Product, parent=None) -> None:
        super().__init__(parent)
        self.product_id = product.id
        self.product_name = product.name
        self.barcode = product.barcode
        self.sale_price = product.sale_price
        self.current_stock = product.current_stock
        self.minimum_stock = product.minimum_stock
        self.tax_rate = product.tax_rate or Decimal("0")
        self.is_out_of_stock = self.current_stock <= 0

        self.setObjectName("product_card")
        self.setCursor(Qt.CursorShape.PointingHandCursor if not self.is_out_of_stock else Qt.CursorShape.ForbiddenCursor)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setMinimumSize(QSize(140, 115))
        self.setMaximumSize(QSize(260, 140))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Style card
        bg_color = "#1f2228" if not self.is_out_of_stock else "#16181d"
        border_color = "#2d3139" if not self.is_out_of_stock else "#272a30"
        opacity = "1.0" if not self.is_out_of_stock else "0.55"

        self.setStyleSheet(f"""
            QFrame#product_card {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                opacity: {opacity};
            }}
            QFrame#product_card:hover {{
                border: 1px solid {"#2d6cdf" if not self.is_out_of_stock else "#dc3545"};
                background-color: {"#252932" if not self.is_out_of_stock else "#1b1d23"};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Product Name
        lbl_name = QLabel(self.product_name)
        lbl_name.setWordWrap(True)
        lbl_name.setStyleSheet("font-weight: 600; font-size: 13px; color: #e8eaed; line-height: 1.2;")

        # Price
        lbl_price = QLabel(format_currency(self.sale_price))
        lbl_price.setStyleSheet("font-weight: 700; font-size: 14px; color: #20c997;")

        # Stock Status Badge
        if self.current_stock <= 0:
            stock_str = "Out of Stock"
            badge_style = "color: #dc3545; background-color: rgba(220, 53, 69, 0.15); border-radius: 4px; padding: 2px 6px; font-weight: 600; font-size: 11px;"
        elif self.current_stock <= self.minimum_stock:
            stock_str = f"Low Stock: {float(self.current_stock):g}"
            badge_style = "color: #fd7e14; background-color: rgba(253, 126, 20, 0.15); border-radius: 4px; padding: 2px 6px; font-weight: 600; font-size: 11px;"
        else:
            stock_str = f"Stock: {float(self.current_stock):g}"
            badge_style = "color: #9ca3af; font-size: 11px;"

        lbl_stock = QLabel(stock_str)
        lbl_stock.setStyleSheet(badge_style)

        layout.addWidget(lbl_name, 1)
        layout.addWidget(lbl_price)
        layout.addWidget(lbl_stock, 0, Qt.AlignmentFlag.AlignLeft)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_out_of_stock:
                self.out_of_stock_clicked.emit(self)
            else:
                self.clicked.emit(self)
        super().mousePressEvent(event)


class ProductGridWidget(QWidget):
    """
    Grid Container displaying product cards and horizontal category filter tabs.
    """
    product_selected = Signal(object)  # Emits Card or Product dict
    out_of_stock_selected = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._categories: List[Category] = []
        self._active_category_id: Optional[int] = None
        self._current_query: str = ""
        self._cards: List[ProductCard] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # ─── CATEGORY FILTER BAR ───
        self.category_scroll = QScrollArea()
        self.category_scroll.setFixedHeight(50)
        self.category_scroll.setWidgetResizable(True)
        self.category_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.category_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.category_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.category_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:horizontal { height: 4px; background: #141619; border: none; margin: 0px; }
            QScrollBar::handle:horizontal { background: #374151; border-radius: 2px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; height: 0px; }
        """)

        self.category_container = QWidget()
        self.category_layout = QHBoxLayout(self.category_container)
        self.category_layout.setContentsMargins(0, 2, 0, 4)
        self.category_layout.setSpacing(6)
        self.category_scroll.setWidget(self.category_container)

        main_layout.addWidget(self.category_scroll)

        # ─── PRODUCT CARDS SCROLL AREA ───
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.grid_scroll.setWidget(self.grid_container)

        main_layout.addWidget(self.grid_scroll)
        self.load_categories()

    def load_categories(self) -> None:
        """Load category filter buttons from DB."""
        # Clear existing buttons
        while self.category_layout.count():
            item = self.category_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add 'All' button
        btn_all = QPushButton("All Products")
        btn_all.setProperty("category_id", None)
        btn_all.setCheckable(True)
        btn_all.setChecked(self._active_category_id is None)
        btn_all.setStyleSheet(self._get_cat_btn_style(self._active_category_id is None))
        btn_all.clicked.connect(lambda: self._on_category_clicked(None))
        self.category_layout.addWidget(btn_all)

        with get_session() as session:
            try:
                categories = session.query(Category).filter(Category.is_active == True).all()
                self._categories = categories
                for cat in categories:
                    formatted_name = cat.name.replace("_", " ")
                    btn = QPushButton(formatted_name)
                    btn.setProperty("category_id", cat.id)
                    btn.setCheckable(True)
                    btn.setChecked(self._active_category_id == cat.id)
                    btn.setStyleSheet(self._get_cat_btn_style(self._active_category_id == cat.id))
                    btn.clicked.connect(lambda _, c_id=cat.id: self._on_category_clicked(c_id))
                    self.category_layout.addWidget(btn)
            except Exception as e:
                logger.error("Failed to load categories: %s", e)

        self.category_layout.addStretch()

    def _get_cat_btn_style(self, is_active: bool) -> str:
        if is_active:
            return """
                QPushButton {
                    background-color: #2d6cdf;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: 600;
                    font-size: 12px;
                }
            """
        return """
            QPushButton {
                background-color: #22252c;
                color: #9ca3af;
                border: 1px solid #2d3139;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2a2e37;
                color: #e8eaed;
            }
        """

    def _on_category_clicked(self, category_id: Optional[int]) -> None:
        self._active_category_id = category_id
        # Update tab button styles
        for i in range(self.category_layout.count()):
            item = self.category_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QPushButton):
                btn = item.widget()
                c_id = btn.property("category_id")
                is_active = (c_id == category_id)
                btn.setChecked(is_active)
                btn.setStyleSheet(self._get_cat_btn_style(is_active))

        self.refresh_products(self._current_query)

    def refresh_products(self, query: str = "") -> None:
        """Filter and display product cards."""
        self._current_query = query
        # Clear grid layout
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        with get_session() as session:
            repo = ProductRepository(session)
            if query:
                products = repo.search(query, limit=50)
            else:
                products = repo.get_all(active_only=True)

            # Filter by category if selected
            if self._active_category_id is not None:
                products = [p for p in products if p.category_id == self._active_category_id]

            if not products:
                # Empty state for product grid search
                lbl_empty = QLabel("No products found")
                lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_empty.setStyleSheet("color: #6b7280; font-size: 14px; margin-top: 30px;")
                self.grid_layout.addWidget(lbl_empty, 0, 0, 1, 3)
                return

            cols = 3
            for idx, p in enumerate(products):
                card = ProductCard(p)
                card.clicked.connect(self.product_selected.emit)
                card.out_of_stock_clicked.connect(self.out_of_stock_selected.emit)
                row = idx // cols
                col = idx % cols
                self.grid_layout.addWidget(card, row, col)
                self._cards.append(card)

    def get_first_available_card(self) -> Optional[ProductCard]:
        for card in self._cards:
            if not card.is_out_of_stock:
                return card
        return None
