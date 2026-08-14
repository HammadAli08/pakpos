"""
Regression Test Suite for Inventory Data Synchronization & Persistence.
Verifies single source of truth across Checkout, Products & Stock, Reports, and Database.
"""
from __future__ import annotations

from decimal import Decimal
import pytest

from pakpos.database.engine import init_database, get_session
from pakpos.database.models.product import Product
from pakpos.database.models.category import Category
from pakpos.database.models.user import User, UserRole
from pakpos.database.repositories.product_repo import ProductRepository
from pakpos.services.sales_service import SalesService, SaleRequest, CartItem
from pakpos.services.report_service import ReportService
from pakpos.services.auth_service import AuthService
from pakpos.database.models.sale import PaymentMethod, Sale
from pakpos.utils.validators import ValidationError
from pakpos.config.settings import DB_PATH, APP_DATA_DIR


class TestInventorySynchronization:

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Initialize database for test."""
        db_file = tmp_path / "test_sync.db"
        db_url = f"sqlite:///{db_file}"
        init_database(db_url)
        yield

    @pytest.fixture
    def test_user_id(self) -> int:
        with get_session() as session:
            auth = AuthService(session)
            user = auth.create_user("cashier_test", "Test Cashier", "password123", UserRole.CASHIER)
            session.commit()
            return user.id

    @pytest.fixture
    def sample_category_id(self) -> int:
        with get_session() as session:
            cat = Category(name="Beverages", name_urdu="مشروبات")
            session.add(cat)
            session.commit()
            return cat.id

    @pytest.fixture
    def coca_cola_product_id(self, sample_category_id) -> int:
        """Create Coca Cola 500ml with initial stock of 100."""
        with get_session() as session:
            coke = Product(
                name="Coca Cola 500ml",
                barcode="6291100000001",
                sku="COKE-500ML",
                category_id=sample_category_id,
                unit="piece",
                purchase_price=Decimal("100.00"),
                sale_price=Decimal("150.00"),
                minimum_stock=Decimal("5"),
                current_stock=Decimal("100"),
                tax_rate=Decimal("0"),
                is_active=True,
            )
            session.add(coke)
            session.commit()
            return coke.id

    def test_1_single_product_stock_update(self, coca_cola_product_id, test_user_id):
        """TEST 1 — SINGLE PRODUCT STOCK UPDATE (100 -> 93)."""
        with get_session() as session:
            service = SalesService(session)
            repo = ProductRepository(session)
            coke = repo.get_by_id(coca_cola_product_id)

            req = SaleRequest(
                items=[CartItem(
                    product_id=coke.id,
                    product_name=coke.name,
                    barcode=coke.barcode,
                    quantity=Decimal("7"),
                    unit_price=coke.sale_price,
                )],
                payment_method=PaymentMethod.CASH,
                paid_amount=Decimal("1050"),
                cashier_id=test_user_id,
            )

            service.create_sale(req)
            session.commit()

        # 1. Assert database record directly via fresh session
        with get_session() as session:
            repo = ProductRepository(session)
            coke_db = repo.get_by_id(coca_cola_product_id)
            assert coke_db.current_stock == Decimal("93")

            # 2. Assert ProductRepository query returns 93
            assert repo.get_by_id(coca_cola_product_id).current_stock == Decimal("93")

            # 3. Assert Checkout barcode search returns 93
            scanned_prod = repo.get_by_barcode("6291100000001")
            assert scanned_prod.current_stock == Decimal("93")

    def test_2_multiple_product_stock_update(self, sample_category_id, test_user_id):
        """TEST 2 — MULTIPLE PRODUCT STOCK UPDATE (A:100->93, B:97->95, C:94->90)."""
        ids = {}
        with get_session() as session:
            p_a = Product(name="Prod A", barcode="101", unit="pc", purchase_price=10, sale_price=20, current_stock=Decimal("100"), minimum_stock=5, category_id=sample_category_id, is_active=True)
            p_b = Product(name="Prod B", barcode="102", unit="pc", purchase_price=10, sale_price=20, current_stock=Decimal("97"), minimum_stock=5, category_id=sample_category_id, is_active=True)
            p_c = Product(name="Prod C", barcode="103", unit="pc", purchase_price=10, sale_price=20, current_stock=Decimal("94"), minimum_stock=5, category_id=sample_category_id, is_active=True)
            session.add_all([p_a, p_b, p_c])
            session.commit()
            ids['a'], ids['b'], ids['c'] = p_a.id, p_b.id, p_c.id

        with get_session() as session:
            service = SalesService(session)
            req = SaleRequest(
                items=[
                    CartItem(product_id=ids['a'], product_name="Prod A", barcode="101", quantity=Decimal("7"), unit_price=Decimal("20")),
                    CartItem(product_id=ids['b'], product_name="Prod B", barcode="102", quantity=Decimal("2"), unit_price=Decimal("20")),
                    CartItem(product_id=ids['c'], product_name="Prod C", barcode="103", quantity=Decimal("4"), unit_price=Decimal("20")),
                ],
                payment_method=PaymentMethod.CASH,
                paid_amount=Decimal("300"),
                cashier_id=test_user_id,
            )
            service.create_sale(req)
            session.commit()

        with get_session() as session:
            repo = ProductRepository(session)
            assert repo.get_by_id(ids['a']).current_stock == Decimal("93")
            assert repo.get_by_id(ids['b']).current_stock == Decimal("95")
            assert repo.get_by_id(ids['c']).current_stock == Decimal("90")

    def test_3_ui_reload_after_sale(self, coca_cola_product_id, test_user_id):
        """TEST 3 — UI RELOAD AFTER SALE."""
        from pakpos.ui.screens.products_screen import ProductsScreen
        from PySide6.QtWidgets import QApplication
        import sys

        app = QApplication.instance() or QApplication(["-platform", "offscreen"])

        with get_session() as session:
            user = session.get(User, test_user_id)
            screen = ProductsScreen(current_user=user)

        # Before sale: table loaded with initial stock 100
        assert screen.table.rowCount() > 0

        # Perform sale of 7 units in service layer
        with get_session() as session:
            service = SalesService(session)
            req = SaleRequest(
                items=[CartItem(product_id=coca_cola_product_id, product_name="Coca Cola 500ml", barcode="6291100000001", quantity=Decimal("7"), unit_price=Decimal("150"))],
                payment_method=PaymentMethod.CASH,
                paid_amount=Decimal("1050"),
                cashier_id=test_user_id,
            )
            service.create_sale(req)
            session.commit()

        # Refresh screen directly from database
        screen.refresh()

        # Find row for Coca Cola and verify stock text is 93
        found_stock = None
        for row in range(screen.table.rowCount()):
            item_id = screen.table.item(row, 0)
            if item_id and item_id.text() == str(coca_cola_product_id):
                found_stock = screen.table.item(row, 6).text()
                break

        assert found_stock == "93"

    def test_4_stale_session_regression(self, sample_category_id, test_user_id):
        """TEST 4 — STALE SESSION REGRESSION (Cross-session visibility)."""
        # Session 1: Initial product creation
        with get_session() as s1:
            p1 = Product(name="Cross-Session Product", barcode="CS99", unit="pc", purchase_price=10, sale_price=50, current_stock=Decimal("100"), minimum_stock=5, is_active=True, category_id=sample_category_id)
            s1.add(p1)
            s1.commit()
            p1_id = p1.id

        # Session 2: Sales service executes sale in separate transaction/session
        with get_session() as s2:
            service = SalesService(s2)
            req = SaleRequest(
                items=[CartItem(product_id=p1_id, product_name="Cross-Session Product", barcode="CS99", quantity=Decimal("7"), unit_price=Decimal("50"))],
                payment_method=PaymentMethod.CASH,
                paid_amount=Decimal("350"),
                cashier_id=test_user_id,
            )
            service.create_sale(req)
            s2.commit()

        # Session 3: Products & Stock screen loads fresh database query
        with get_session() as s3:
            repo3 = ProductRepository(s3)
            p3 = repo3.get_by_id(p1_id)
            assert p3.current_stock == Decimal("93")

    def test_5_rollback_single_item(self, coca_cola_product_id, test_user_id):
        """TEST 5 — ROLLBACK (Attempt to sell 101 units when stock is 100)."""
        with get_session() as session:
            service = SalesService(session)
            req = SaleRequest(
                items=[CartItem(product_id=coca_cola_product_id, product_name="Coca Cola 500ml", barcode="6291100000001", quantity=Decimal("101"), unit_price=Decimal("150"))],
                payment_method=PaymentMethod.CASH,
                paid_amount=Decimal("16000"),
                cashier_id=test_user_id,
            )

            with pytest.raises(ValidationError, match="Insufficient stock"):
                service.create_sale(req)

        # Assert zero sales created and stock remains 100
        with get_session() as session:
            sales_count = session.query(Sale).count()
            assert sales_count == 0

            repo = ProductRepository(session)
            assert repo.get_by_id(coca_cola_product_id).current_stock == Decimal("100")

    def test_6_multi_item_atomic_rollback(self, sample_category_id, test_user_id):
        """TEST 6 — MULTI-ITEM ATOMIC ROLLBACK (A=100, B=5. Attempt A*3, B*10)."""
        with get_session() as session:
            p_a = Product(name="Item A", barcode="A10", unit="pc", purchase_price=10, sale_price=20, current_stock=Decimal("100"), minimum_stock=5, category_id=sample_category_id, is_active=True)
            p_b = Product(name="Item B", barcode="B10", unit="pc", purchase_price=10, sale_price=20, current_stock=Decimal("5"), minimum_stock=1, category_id=sample_category_id, is_active=True)
            session.add_all([p_a, p_b])
            session.commit()
            id_a, id_b = p_a.id, p_b.id

        with get_session() as session:
            service = SalesService(session)
            req = SaleRequest(
                items=[
                    CartItem(product_id=id_a, product_name="Item A", barcode="A10", quantity=Decimal("3"), unit_price=Decimal("20")),
                    CartItem(product_id=id_b, product_name="Item B", barcode="B10", quantity=Decimal("10"), unit_price=Decimal("20")),
                ],
                payment_method=PaymentMethod.CASH,
                paid_amount=Decimal("500"),
                cashier_id=test_user_id,
            )

            with pytest.raises(ValidationError, match="Insufficient stock"):
                service.create_sale(req)

        with get_session() as session:
            repo = ProductRepository(session)
            assert repo.get_by_id(id_a).current_stock == Decimal("100")
            assert repo.get_by_id(id_b).current_stock == Decimal("5")

    def test_7_report_synchronization(self, coca_cola_product_id, test_user_id):
        """TEST 7 — REPORT SYNCHRONIZATION."""
        with get_session() as session:
            service = SalesService(session)
            req = SaleRequest(
                items=[CartItem(product_id=coca_cola_product_id, product_name="Coca Cola 500ml", barcode="6291100000001", quantity=Decimal("7"), unit_price=Decimal("150"))],
                payment_method=PaymentMethod.CASH,
                paid_amount=Decimal("1050"),
                cashier_id=test_user_id,
            )
            service.create_sale(req)
            session.commit()

        with get_session() as session:
            report_service = ReportService(session)
            summary = report_service.get_today_summary()
            assert summary.total_transactions == 1
            assert summary.total_revenue == Decimal("1050")

    def test_8_repeated_sales_cumulative_decrement(self, coca_cola_product_id, test_user_id):
        """TEST 8 — REPEATED SALES (100 -> 93 -> 88 -> 80)."""
        # Sale 1: 7 units
        with get_session() as session:
            service = SalesService(session)
            req1 = SaleRequest(
                items=[CartItem(product_id=coca_cola_product_id, product_name="Coca Cola 500ml", barcode="6291100000001", quantity=Decimal("7"), unit_price=Decimal("150"))],
                payment_method=PaymentMethod.CASH, paid_amount=Decimal("1050"), cashier_id=test_user_id,
            )
            service.create_sale(req1)
            session.commit()

        with get_session() as session:
            repo = ProductRepository(session)
            assert repo.get_by_id(coca_cola_product_id).current_stock == Decimal("93")

        # Sale 2: 5 units
        with get_session() as session:
            service = SalesService(session)
            req2 = SaleRequest(
                items=[CartItem(product_id=coca_cola_product_id, product_name="Coca Cola 500ml", barcode="6291100000001", quantity=Decimal("5"), unit_price=Decimal("150"))],
                payment_method=PaymentMethod.CASH, paid_amount=Decimal("750"), cashier_id=test_user_id,
            )
            service.create_sale(req2)
            session.commit()

        with get_session() as session:
            repo = ProductRepository(session)
            assert repo.get_by_id(coca_cola_product_id).current_stock == Decimal("88")

        # Sale 3: 8 units
        with get_session() as session:
            service = SalesService(session)
            req3 = SaleRequest(
                items=[CartItem(product_id=coca_cola_product_id, product_name="Coca Cola 500ml", barcode="6291100000001", quantity=Decimal("8"), unit_price=Decimal("150"))],
                payment_method=PaymentMethod.CASH, paid_amount=Decimal("1200"), cashier_id=test_user_id,
            )
            service.create_sale(req3)
            session.commit()

        with get_session() as session:
            repo = ProductRepository(session)
            assert repo.get_by_id(coca_cola_product_id).current_stock == Decimal("80")

    def test_9_packaged_database_path(self):
        """TEST 9 — PACKAGED DATABASE PATH VERIFICATION."""
        db_str = str(DB_PATH.resolve())
        assert "PakPOS" in db_str
        assert "pos.db" in db_str
        assert not ("_MEI" in db_str or "tmp" in db_str.lower())
