"""
Comprehensive Unit & Integration Test Suite for PakPOS Production-Grade Receipt Printing.
Tests all 19 hardware, rendering, resilience, and data integrity test cases.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy.orm import Session

from pakpos.database.models.product import Product
from pakpos.database.models.category import Category
from pakpos.database.models.sale import Sale, SaleItem, SaleStatus, PaymentMethod
from pakpos.database.models.customer import Customer
from pakpos.database.models.user import User, UserRole
from pakpos.hardware.printer.base import (
    ReceiptData, PrinterStatus, PrintStatus, PrintResult
)
from pakpos.hardware.printer.renderers.thermal_renderer import ThermalReceiptRenderer, PrinterProfile
from pakpos.hardware.printer.renderers.a4_renderer import A4ReceiptRenderer
from pakpos.hardware.printer.pdf_backend import PdfBackend
from pakpos.hardware.printer.thermal_escpos_backend import ThermalEscPosBackend
from pakpos.hardware.printer.mock_adapter import MockPrinterAdapter
from pakpos.hardware.printer.printer_manager import PrinterManager
from pakpos.services.sales_service import SalesService, SaleRequest, CartItem
from pakpos.services.print_service import PrintService
from pakpos.services.auth_service import AuthService


@pytest.fixture
def seed_printing_db(db_session: Session):
    """Seed test database with product, user, customer, and sale."""
    auth_svc = AuthService(db_session)
    user = auth_svc.create_user("cashier_test", "Cashier Test", "Pass1234!", UserRole.CASHIER)


    category = Category(name="Groceries")
    db_session.add(category)
    db_session.flush()

    p1 = Product(
        name="Super Basmati Rice 5kg Extra Long Grain Premium Bag",
        barcode="8901234567890",
        purchase_price=Decimal("1500.00"),
        sale_price=Decimal("1800.00"),
        current_stock=Decimal("50.000"),
        minimum_stock=Decimal("5.000"),
        category_id=category.id,
    )
    p2 = Product(
        name="Lipton Tea 950g",
        barcode="8909876543210",
        purchase_price=Decimal("1200.00"),
        sale_price=Decimal("1500.00"),
        current_stock=Decimal("30.000"),
        minimum_stock=Decimal("2.000"),
        category_id=category.id,
    )

    db_session.add_all([p1, p2])

    cust = Customer(name="Tariq Mahmood", phone="0300-1122334", address="Lahore")
    db_session.add(cust)
    db_session.commit()

    return {"user": user, "p1": p1, "p2": p2, "customer": cust}


# T1: ReceiptData from sale
def test_receipt_data_from_sale(db_session: Session, seed_printing_db):
    data = seed_printing_db
    sales_svc = SalesService(db_session)

    req = SaleRequest(
        items=[
            CartItem(product_id=data["p1"].id, product_name=data["p1"].name, barcode=data["p1"].barcode, quantity=Decimal("2"), unit_price=Decimal("1800.00")),
        ],
        payment_method=PaymentMethod.CASH,
        paid_amount=Decimal("4000.00"),
        customer_id=data["customer"].id,
        cashier_id=data["user"].id,
    )
    sale_res = sales_svc.create_sale(req)
    db_session.commit()

    receipt = sales_svc.get_receipt_data(sale_res.sale_id)
    assert receipt.invoice_number == sale_res.invoice_number
    assert receipt.total == 3600.0
    assert receipt.paid_amount == 4000.0
    assert receipt.change == 400.0
    assert receipt.customer_name == "Tariq Mahmood"
    assert receipt.customer_phone == "0300-1122334"
    assert len(receipt.items) == 1
    assert receipt.items[0]["name"] == data["p1"].name


# T2: ESC/POS lines produced
def test_escpos_lines_produced():
    r = ReceiptData(
        shop_name="PakPOS Test", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier", items=[{"name": "Item 1", "qty": 1, "total": 100.0}],
        subtotal=100.0, discount=0.0, tax=0.0, total=100.0, paid_amount=100.0, change=0.0, payment_method="CASH"
    )
    lines = ThermalReceiptRenderer().render_lines(r)
    assert len(lines) > 5
    assert any(line.text and "INV-001" in line.text for line in lines)


# T3: 80mm line width
def test_80mm_line_width():
    r = ReceiptData(
        shop_name="Test Store Name That Is Very Long", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier", items=[{"name": "Very Long Product Description Wrapping Test", "qty": 1, "total": 100.0}],
        subtotal=100.0, discount=0.0, tax=0.0, total=100.0, paid_amount=100.0, change=0.0, payment_method="CASH",
        paper_width_mm=80
    )
    text = ThermalReceiptRenderer().render_to_text(r)
    for line in text.split("\n"):
        assert len(line) <= 48, f"Line exceeds 48 chars: {line}"


# T4: 58mm line width
def test_58mm_line_width():
    r = ReceiptData(
        shop_name="Test Store Name That Is Very Long", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier", items=[{"name": "Very Long Product Description Wrapping Test", "qty": 1, "total": 100.0}],
        subtotal=100.0, discount=0.0, tax=0.0, total=100.0, paid_amount=100.0, change=0.0, payment_method="CASH",
        paper_width_mm=58
    )
    text = ThermalReceiptRenderer().render_to_text(r)
    for line in text.split("\n"):
        assert len(line) <= 40, f"Line exceeds 40 chars: {line}"


# T5: A4 PDF generated
def test_a4_pdf_generated():
    r = ReceiptData(
        shop_name="PakPOS Store", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier", items=[{"name": "Item 1", "qty": 1, "total": 100.0}],
        subtotal=100.0, discount=0.0, tax=0.0, total=100.0, paid_amount=100.0, change=0.0, payment_method="CASH"
    )
    pdf_bytes = A4ReceiptRenderer().render_pdf(r)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


# T6: PDF file saved
def test_pdf_file_saved(tmp_path: Path):
    r = ReceiptData(
        shop_name="PakPOS Store", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier", items=[{"name": "Item 1", "qty": 1, "total": 100.0}],
        subtotal=100.0, discount=0.0, tax=0.0, total=100.0, paid_amount=100.0, change=0.0, payment_method="CASH"
    )
    backend = PdfBackend(export_dir=tmp_path)
    res = backend.print_receipt(r)
    assert res.success
    assert backend.get_last_pdf_path() is not None
    assert backend.get_last_pdf_path().exists()


# T7: Long product name wrap
def test_long_product_name_wrap():
    long_name = "Super Long Product Name That Needs Multiple Lines Wrapping On 80mm Receipt Layout"
    r = ReceiptData(
        shop_name="Shop", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier",
        items=[{"name": long_name, "qty": 1, "unit_price": 100.0, "total": 100.0}],
        subtotal=100.0, discount=0.0, tax=0.0, total=100.0, paid_amount=100.0, change=0.0, payment_method="CASH"
    )
    lines = ThermalReceiptRenderer().render_lines(r)
    rendered_text = ThermalReceiptRenderer().render_to_text(r)
    assert "Super Long Product" in rendered_text
    assert "Layout" in rendered_text


# T8: Multi-product alignment
def test_multi_product_alignment():
    r = ReceiptData(
        shop_name="Shop", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier",
        items=[
            {"name": "Prod A", "qty": 1, "unit_price": 10.0, "total": 10.0},
            {"name": "Prod B", "qty": 100, "unit_price": 2.5, "total": 250.0},
        ],
        subtotal=260.0, discount=0.0, tax=0.0, total=260.0, paid_amount=300.0, change=40.0, payment_method="CASH"
    )
    text = ThermalReceiptRenderer().render_to_text(r)
    assert "Prod A" in text
    assert "Prod B" in text


# T9: Large quantity format
def test_large_quantity_format():
    r = ReceiptData(
        shop_name="Shop", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier",
        items=[{"name": "Bulk Item", "qty": 1000.5, "unit_price": 10.0, "total": 10005.0}],
        subtotal=10005.0, discount=0.0, tax=0.0, total=10005.0, paid_amount=10005.0, change=0.0, payment_method="CASH"
    )
    text = ThermalReceiptRenderer().render_to_text(r)
    assert "1000.5" in text


# T10: Item discount
def test_item_discount():
    r = ReceiptData(
        shop_name="Shop", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier",
        items=[{"name": "Item A", "qty": 1, "unit_price": 100.0, "total": 90.0}],
        subtotal=100.0, discount=10.0, tax=0.0, total=90.0, paid_amount=100.0, change=10.0, payment_method="CASH"
    )
    text = ThermalReceiptRenderer().render_to_text(r)
    assert "Discount" in text
    assert "10.00" in text


# T11: Tax amount
def test_tax_amount():
    r = ReceiptData(
        shop_name="Shop", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier",
        items=[{"name": "Item A", "qty": 1, "unit_price": 100.0, "total": 100.0}],
        subtotal=100.0, discount=0.0, tax=17.0, total=117.0, paid_amount=120.0, change=3.0, payment_method="CASH"
    )
    text = ThermalReceiptRenderer().render_to_text(r)
    assert "Tax" in text
    assert "17.00" in text


# T12: Cash payment details
def test_cash_payment_details():
    r = ReceiptData(
        shop_name="Shop", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier",
        items=[{"name": "Item A", "qty": 1, "unit_price": 100.0, "total": 100.0}],
        subtotal=100.0, discount=0.0, tax=0.0, total=100.0, paid_amount=500.0, change=400.0, payment_method="CASH"
    )
    text = ThermalReceiptRenderer().render_to_text(r)
    assert "Payment (CASH)" in text
    assert "Change" in text
    assert "400.00" in text


# T13: Credit payment details
def test_credit_payment_details():
    r = ReceiptData(
        shop_name="Shop", shop_address="Address", shop_phone="123",
        invoice_number="INV-001", cashier_name="Cashier",
        items=[{"name": "Item A", "qty": 1, "unit_price": 100.0, "total": 100.0}],
        subtotal=100.0, discount=0.0, tax=0.0, total=100.0, paid_amount=0.0, change=0.0,
        payment_method="CREDIT", customer_name="Tariq Mahmood", customer_phone="0300-1122334", due_amount=100.0
    )
    text = ThermalReceiptRenderer().render_to_text(r)
    assert "Customer: Tariq Mahmood" in text
    assert "Balance Due (Khata)" in text
    assert "100.00" in text


# T14: Printer failure resilience
def test_printer_failure_resilience(db_session: Session, seed_printing_db):
    data = seed_printing_db
    sales_svc = SalesService(db_session)

    req = SaleRequest(
        items=[CartItem(product_id=data["p1"].id, product_name=data["p1"].name, barcode=data["p1"].barcode, quantity=Decimal("1"), unit_price=Decimal("1800.00"))],
        payment_method=PaymentMethod.CASH, paid_amount=Decimal("2000.00"), customer_id=None, cashier_id=data["user"].id,
    )
    sale_res = sales_svc.create_sale(req)
    db_session.commit()

    # Create dummy backend that fails
    class FailingBackend(MockPrinterAdapter):
        def print_receipt(self, receipt: ReceiptData) -> PrintResult:
            return PrintResult(status=PrintStatus.FAILED, error="Hardware disconnect test")

    print_svc = PrintService()
    res = print_svc.print_sale(sale_res.sale_id, session=db_session, backend=FailingBackend())

    assert not res.success
    assert res.status == PrintStatus.FAILED
    # Verify sale is still committed in DB
    sale_in_db = db_session.get(Sale, sale_res.sale_id)
    assert sale_in_db is not None
    assert sale_in_db.status == SaleStatus.COMPLETED


# T15: Retry print no new sale
def test_retry_print_no_new_sale(db_session: Session, seed_printing_db):
    data = seed_printing_db
    sales_svc = SalesService(db_session)

    req = SaleRequest(
        items=[CartItem(product_id=data["p1"].id, product_name=data["p1"].name, barcode=data["p1"].barcode, quantity=Decimal("1"), unit_price=Decimal("1800.00"))],
        payment_method=PaymentMethod.CASH, paid_amount=Decimal("2000.00"), customer_id=None, cashier_id=data["user"].id,
    )
    sale_res = sales_svc.create_sale(req)
    db_session.commit()

    initial_count = db_session.query(Sale).count()

    print_svc = PrintService()
    # Retry print
    res = print_svc.reprint_sale(sale_res.sale_id, session=db_session, backend=MockPrinterAdapter())
    assert res.success

    # Count must remain unchanged
    final_count = db_session.query(Sale).count()
    assert final_count == initial_count


# T16: Reprint invoice unchanged
def test_reprint_invoice_unchanged(db_session: Session, seed_printing_db):
    data = seed_printing_db
    sales_svc = SalesService(db_session)

    req = SaleRequest(
        items=[CartItem(product_id=data["p1"].id, product_name=data["p1"].name, barcode=data["p1"].barcode, quantity=Decimal("1"), unit_price=Decimal("1800.00"))],
        payment_method=PaymentMethod.CASH, paid_amount=Decimal("2000.00"), customer_id=None, cashier_id=data["user"].id,
    )
    sale_res = sales_svc.create_sale(req)
    db_session.commit()

    r1 = sales_svc.get_receipt_data(sale_res.sale_id, is_reprint=False)
    r2 = sales_svc.get_receipt_data(sale_res.sale_id, is_reprint=True)

    assert r1.invoice_number == r2.invoice_number
    assert r2.is_reprint is True


# T17: Historical price on reprint
def test_historical_price_on_reprint(db_session: Session, seed_printing_db):
    data = seed_printing_db
    sales_svc = SalesService(db_session)

    req = SaleRequest(
        items=[CartItem(product_id=data["p1"].id, product_name=data["p1"].name, barcode=data["p1"].barcode, quantity=Decimal("1"), unit_price=Decimal("1800.00"))],
        payment_method=PaymentMethod.CASH, paid_amount=Decimal("2000.00"), customer_id=None, cashier_id=data["user"].id,
    )
    sale_res = sales_svc.create_sale(req)
    db_session.commit()

    # Now change product price in master catalog
    data["p1"].sale_price = Decimal("2500.00")
    db_session.commit()

    # Get receipt data — must retain original sale price 1800.00
    receipt = sales_svc.get_receipt_data(sale_res.sale_id, is_reprint=True)
    assert receipt.items[0]["unit_price"] == 1800.0
    assert receipt.total == 1800.0


# T18: No printer fallback to PDF
def test_no_printer_fallback_to_pdf(db_session: Session, seed_printing_db, tmp_path: Path):
    data = seed_printing_db
    sales_svc = SalesService(db_session)

    req = SaleRequest(
        items=[CartItem(product_id=data["p1"].id, product_name=data["p1"].name, barcode=data["p1"].barcode, quantity=Decimal("1"), unit_price=Decimal("1800.00"))],
        payment_method=PaymentMethod.CASH, paid_amount=Decimal("2000.00"), customer_id=None, cashier_id=data["user"].id,
    )
    sale_res = sales_svc.create_sale(req)
    db_session.commit()

    print_svc = PrintService()
    res = print_svc.export_pdf(sale_res.sale_id, session=db_session, output_path=tmp_path / "out.pdf")
    assert res.success


# T19: Printing modules import
def test_printing_modules_import():
    from pakpos.hardware.printer.base import ReceiptData, PrinterBase, PrinterStatus
    from pakpos.hardware.printer.renderers.thermal_renderer import ThermalReceiptRenderer
    from pakpos.hardware.printer.renderers.a4_renderer import A4ReceiptRenderer
    from pakpos.hardware.printer.pdf_backend import PdfBackend
    from pakpos.hardware.printer.thermal_escpos_backend import ThermalEscPosBackend
    from pakpos.hardware.printer.printer_manager import PrinterManager
    from pakpos.services.print_service import PrintService

    assert ReceiptData is not None
    assert ThermalReceiptRenderer is not None
    assert A4ReceiptRenderer is not None
    assert PdfBackend is not None
    assert ThermalEscPosBackend is not None
    assert PrinterManager is not None
    assert PrintService is not None
