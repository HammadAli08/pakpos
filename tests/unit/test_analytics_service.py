"""
Unit and Integration Tests for Analytics Service, Repository, and Insights Engine.
Tests all 20 required analytics business requirements using in-memory SQLite.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from pakpos.database.models.sale import Sale, SaleItem, SaleStatus, PaymentMethod
from pakpos.database.models.product import Product
from pakpos.database.models.category import Category
from pakpos.database.models.customer import Customer
from pakpos.analytics.analytics_service import AnalyticsService
from pakpos.analytics.analytics_repository import AnalyticsRepository
from pakpos.analytics.metrics import DateRangeOption
from pakpos.services.sales_service import SalesService, SaleRequest, CartItem


@pytest.fixture
def populated_analytics_db(db_session, sample_category, sample_product, sample_customer, owner_user):
    """Fixture with sales, categories, customers, and stock data."""
    # Create extra category & product
    cat_food = Category(name="Food", name_urdu="خوراک")
    db_session.add(cat_food)
    db_session.flush()

    p_chips = Product(
        name="Lays Potato Chips",
        barcode="6291109999999",
        category_id=cat_food.id,
        purchase_price=Decimal("40.00"),
        sale_price=Decimal("60.00"),
        minimum_stock=Decimal("10"),
        current_stock=Decimal("8"),  # Initial stock 8. After 5 sold, 3 remain (low stock!)
        is_active=True,
    )
    p_out = Product(
        name="Out of Stock Item",
        barcode="6291100000000",
        category_id=cat_food.id,
        purchase_price=Decimal("100.00"),
        sale_price=Decimal("150.00"),
        minimum_stock=Decimal("5"),
        current_stock=Decimal("0"),  # Out of stock!
        is_active=True,
    )
    db_session.add_all([p_chips, p_out])
    db_session.flush()

    # Create completed sales for today
    sales_service = SalesService(db_session)

    # Sale 1: 2x Coca Cola (Cash)
    req1 = SaleRequest(
        items=[
            CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("2"),
                unit_price=sample_product.sale_price,
            )
        ],
        payment_method=PaymentMethod.CASH,
        paid_amount=Decimal("300.00"),
        cashier_id=owner_user.id,
    )
    res1 = sales_service.create_sale(req1)

    # Sale 2: 5x Lays Chips (Credit / Khata)
    req2 = SaleRequest(
        items=[
            CartItem(
                product_id=p_chips.id,
                product_name=p_chips.name,
                barcode=p_chips.barcode,
                quantity=Decimal("5"),
                unit_price=p_chips.sale_price,
            )
        ],
        payment_method=PaymentMethod.CREDIT,
        customer_id=sample_customer.id,
        paid_amount=Decimal("0.00"),
        cashier_id=owner_user.id,
    )
    res2 = sales_service.create_sale(req2)

    # Sale 3: Voided Sale (Should be excluded)
    req3 = SaleRequest(
        items=[
            CartItem(
                product_id=sample_product.id,
                product_name=sample_product.name,
                barcode=sample_product.barcode,
                quantity=Decimal("10"),
                unit_price=sample_product.sale_price,
            )
        ],
        payment_method=PaymentMethod.CASH,
        paid_amount=Decimal("1500.00"),
        cashier_id=owner_user.id,
    )
    res3 = sales_service.create_sale(req3)
    sales_service.void_sale(res3.sale_id, reason="Customer cancelled", user_id=owner_user.id)

    db_session.flush()
    return {
        "p_coke": sample_product,
        "p_chips": p_chips,
        "p_out": p_out,
        "customer": sample_customer,
        "sale1": res1,
        "sale2": res2,
        "sale3_voided": res3,
    }


def test_01_todays_revenue(db_session, populated_analytics_db):
    service = AnalyticsService(db_session)
    kpis = service.get_kpi_cards(DateRangeOption.TODAY)
    rev_card = kpis[0]

    # Expected Today's Revenue: 300 (Coke) + 300 (Chips) = 600
    assert rev_card.raw_value == Decimal("600.00")
    assert "Rs. 600.00" in rev_card.value_formatted


def test_02_yesterdays_revenue(db_session, populated_analytics_db):
    service = AnalyticsService(db_session)
    kpis = service.get_kpi_cards(DateRangeOption.YESTERDAY)
    rev_card = kpis[0]

    # No sales yesterday in fixture
    assert rev_card.raw_value == Decimal("0")


def test_03_revenue_trend(db_session, populated_analytics_db):
    service = AnalyticsService(db_session)
    trend = service.get_revenue_trend(DateRangeOption.TODAY)

    # Today's trend returns 24 hourly points
    assert len(trend) == 24
    total_trend_rev = sum(p.revenue for p in trend)
    assert total_trend_rev == Decimal("600.00")


def test_04_transaction_count(db_session, populated_analytics_db):
    service = AnalyticsService(db_session)
    kpis = service.get_kpi_cards(DateRangeOption.TODAY)
    tx_card = kpis[2]

    # 2 completed transactions (voided sale excluded)
    assert tx_card.raw_value == 2


def test_05_average_order_value(db_session, populated_analytics_db):
    service = AnalyticsService(db_session)
    kpis = service.get_kpi_cards(DateRangeOption.TODAY)
    aov_card = kpis[3]

    # AOV = 600 / 2 = 300
    assert aov_card.raw_value == Decimal("300.00")


def test_06_gross_profit_calculation(db_session, populated_analytics_db):
    service = AnalyticsService(db_session)
    kpis = service.get_kpi_cards(DateRangeOption.TODAY)
    profit_card = kpis[1]

    # Coke: 2 * (150 sale - 100 cost) = 100 profit
    # Chips: 5 * (60 sale - 40 cost) = 100 profit
    # Total Gross Profit = 200
    assert profit_card.raw_value == Decimal("200.00")


def test_07_top_products_by_units(db_session, populated_analytics_db):
    service = AnalyticsService(db_session)
    top = service.get_top_products(DateRangeOption.TODAY, sort_by="units")

    assert len(top) == 2
    # Chips sold 5 units, Coke sold 2 units
    assert top[0].name == "Lays Potato Chips"
    assert top[0].units_sold == Decimal("5")


def test_08_top_products_by_revenue(db_session, populated_analytics_db):
    service = AnalyticsService(db_session)
    top = service.get_top_products(DateRangeOption.TODAY, sort_by="revenue")

    assert len(top) == 2
    # Both generated Rs. 300 revenue
    assert sum(p.revenue for p in top) == Decimal("600.00")


def test_09_category_performance(db_session, populated_analytics_db):
    service = AnalyticsService(db_session)
    cats = service.get_category_performance(DateRangeOption.TODAY)

    assert len(cats) == 2
    # Beverages vs Food (each 50%)
    for c in cats:
        assert c.percentage == 50.0


def test_10_low_stock_detection(db_session, populated_analytics_db):
    health = AnalyticsService(db_session).get_inventory_health()
    assert health.low_stock_count >= 1  # Lays chips has stock 3 <= min 10


def test_11_out_of_stock_detection(db_session, populated_analytics_db):
    health = AnalyticsService(db_session).get_inventory_health()
    assert health.out_of_stock_count >= 1  # Out of stock item


def test_12_khata_total(db_session, populated_analytics_db):
    kpis = AnalyticsService(db_session).get_kpi_cards(DateRangeOption.TODAY)
    khata_card = kpis[4]

    # Sale 2 was 300 on credit
    assert khata_card.raw_value == Decimal("300.00")


def test_13_payment_method_totals(db_session, populated_analytics_db):
    pay_breakdown = AnalyticsService(db_session).get_payment_breakdown(DateRangeOption.TODAY)
    
    cash_pay = next(p for p in pay_breakdown if p.method_code == "cash")
    credit_pay = next(p for p in pay_breakdown if p.method_code == "credit")

    assert cash_pay.amount == Decimal("300.00")
    assert credit_pay.amount == Decimal("300.00")


def test_14_date_range_filtering(db_session, populated_analytics_db):
    service = AnalyticsService(db_session)
    
    # 7 days range should include today's sales
    kpis = service.get_kpi_cards(DateRangeOption.LAST_7_DAYS)
    assert kpis[0].raw_value == Decimal("600.00")


def test_15_zero_sales_behavior(db_session):
    """Empty DB should not throw division errors or display ugly state."""
    service = AnalyticsService(db_session)
    kpis = service.get_kpi_cards(DateRangeOption.TODAY)
    
    assert kpis[0].raw_value == Decimal("0")
    assert kpis[2].raw_value == 0
    assert kpis[3].raw_value == Decimal("0")

    insights = service.get_insights(DateRangeOption.TODAY)
    assert len(insights) >= 1
    assert "No sales" in insights[0].message


def test_16_voided_sale_exclusion(db_session, populated_analytics_db):
    """Voided sales must not count towards revenue or profit."""
    service = AnalyticsService(db_session)
    kpis = service.get_kpi_cards(DateRangeOption.TODAY)

    # 600 revenue, NOT 2100 (which would include the 1500 voided sale)
    assert kpis[0].raw_value == Decimal("600.00")


def test_17_historical_sales_correctness(db_session, sample_product, owner_user):
    """Create a sale dated 5 days ago and verify daily trend."""
    sales_service = SalesService(db_session)
    req = SaleRequest(
        items=[CartItem(sample_product.id, sample_product.name, sample_product.barcode, Decimal("1"), sample_product.sale_price)],
        payment_method=PaymentMethod.CASH,
        paid_amount=Decimal("150.00"),
        cashier_id=owner_user.id,
    )
    res = sales_service.create_sale(req)
    
    # Backdate sale
    five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
    sale_obj = db_session.get(Sale, res.sale_id)
    sale_obj.created_at = five_days_ago
    db_session.flush()

    service = AnalyticsService(db_session)
    trend = service.get_revenue_trend(DateRangeOption.LAST_7_DAYS)

    assert any(p.revenue == Decimal("150.00") for p in trend)


def test_18_percentage_comparisons(db_session):
    service = AnalyticsService(db_session)

    # 100 vs 50 -> +100.0%
    pct, text, is_pos = service._calculate_comparison(Decimal("100"), Decimal("50"), "vs yesterday")
    assert pct == 100.0
    assert "↑ 100.0%" in text
    assert is_pos is True

    # 50 vs 100 -> -50.0%
    pct, text, is_pos = service._calculate_comparison(Decimal("50"), Decimal("100"), "vs yesterday")
    assert pct == -50.0
    assert "↓ 50.0%" in text
    assert is_pos is False


def test_19_previous_period_zero_no_infinity(db_session):
    service = AnalyticsService(db_session)

    # Current = 100, Previous = 0 -> No division by zero crash or +inf%
    pct, text, is_pos = service._calculate_comparison(Decimal("100"), Decimal("0"), "vs yesterday")
    assert pct is None
    assert "No prev sales" in text


def test_20_cache_invalidation_handling(db_session, populated_analytics_db):
    service = AnalyticsService(db_session)
    AnalyticsService.invalidate_cache()
    
    kpis = service.get_kpi_cards(DateRangeOption.TODAY)
    assert kpis[0].raw_value == Decimal("600.00")
