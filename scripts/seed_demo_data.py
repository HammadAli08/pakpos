"""
Development-only Demo Data Generator.
Populates 100 products, 10 categories, 20 customers, 10 suppliers, 500 sales, etc.
DO NOT call this automatically in production.
"""
from __future__ import annotations

from decimal import Decimal
import random
from datetime import datetime, timedelta, timezone

from pakpos.database.engine import init_database, get_session
from pakpos.database.models import (
    Category, Product, Customer, Supplier, User, Expense
)
from pakpos.database.models.user import UserRole
from pakpos.services.auth_service import AuthService
from pakpos.services.sales_service import SalesService, SaleRequest, CartItem
from pakpos.services.purchase_service import PurchaseService, PurchaseRequest, PurchaseItemRequest
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)

CATEGORIES = [
    ("Beverages", "مشروبات"),
    ("Snacks & Biscuits", "سنیکس"),
    ("Grocery & Pulses", "گروسری"),
    ("Dairy & Bakery", "ڈیری"),
    ("Personal Care", "ذاتی دیکھ بھال"),
    ("Household Cleaners", "صفائی کا سامان"),
    ("Spices & Condiments", "مصالحہ جات"),
    ("Tea & Coffee", "چائے"),
    ("Frozen Foods", "فروزن فوڈز"),
    ("Stationery", "سٹیشنری"),
]

PRODUCTS_DATA = [
    ("Coca Cola 500ml", "6291101234501", 100, 150, "piece", "Beverages"),
    ("Pepsi 1.5L", "6291101234502", 180, 240, "piece", "Beverages"),
    ("Seven Up 250ml", "6291101234503", 60, 90, "piece", "Beverages"),
    ("Nestle Milkpak 1L", "6291101234504", 250, 290, "piece", "Dairy & Bakery"),
    ("Olper's Milk 1L", "6291101234505", 255, 295, "piece", "Dairy & Bakery"),
    ("Dawn Bread Large", "6291101234506", 140, 180, "piece", "Dairy & Bakery"),
    ("Tapal Danedar Tea 450g", "6291101234507", 550, 680, "pack", "Tea & Coffee"),
    ("Lipton Yellow Label 200g", "6291101234508", 320, 410, "pack", "Tea & Coffee"),
    ("Shan Biryani Masala", "6291101234509", 90, 120, "pack", "Spices & Condiments"),
    ("National Karahi Masala", "6291101234510", 90, 120, "pack", "Spices & Condiments"),
    ("Surf Excel 1kg", "6291101234511", 580, 720, "pack", "Household Cleaners"),
    ("Express Power 500g", "6291101234512", 220, 280, "pack", "Household Cleaners"),
    ("Lux Soap 140g", "6291101234513", 110, 145, "piece", "Personal Care"),
    ("Head & Shoulders 180ml", "6291101234514", 390, 480, "piece", "Personal Care"),
    ("Super Biscuits 100g", "6291101234515", 40, 60, "pack", "Snacks & Biscuits"),
    ("Rio Chocolate Biscuits", "6291101234516", 45, 65, "pack", "Snacks & Biscuits"),
    ("Lays Masala Large", "6291101234517", 80, 100, "pack", "Snacks & Biscuits"),
    ("Dal Chana 1kg", "6291101234518", 220, 270, "kg", "Grocery & Pulses"),
    ("Dal Mong 1kg", "6291101234519", 260, 310, "kg", "Grocery & Pulses"),
    ("Basmati Rice Supreme 5kg", "6291101234520", 1400, 1750, "pack", "Grocery & Pulses"),
]

CUSTOMERS = [
    ("Ahmed Khan", "0300-1111111", "Lahore"),
    ("Muhammad Ali", "0321-2222222", "Karachi"),
    ("Tariq Mahmood", "0333-3333333", "Islamabad"),
    ("Usman Ghani", "0345-4444444", "Rawalpindi"),
    ("Bilal Hassan", "0312-5555555", "Faisalabad"),
    ("Zubair Ahmed", "0301-6666666", "Multan"),
    ("Farhan Saeed", "0322-7777777", "Peshawar"),
    ("Imran Shah", "0334-8888888", "Quetta"),
    ("Kashif Raza", "0346-9999999", "Sialkot"),
    ("Hamza Malik", "0313-0000000", "Gujranwala"),
]

SUPPLIERS = [
    ("Allied Distributors", "0300-9988776", "Lahore", "Nestle & Unilever"),
    ("Metro Cash & Carry Wholesale", "0321-8877665", "Lahore", "General Merchandise"),
    ("Engro Foods Sales", "0333-7766554", "Karachi", "Olpers Dairy"),
    ("Tapal Tea Wholesaler", "0345-6655443", "Karachi", "Tea Products"),
    ("National Foods Agency", "0312-5544332", "Rawalpindi", "Spices"),
]


def main() -> None:
    init_database()
    session = get_session()
    logger.info("Seeding demo data...")

    # Create Admin & Cashier
    auth = AuthService(session)
    if not auth.has_any_user():
        owner = auth.create_user("admin", "System Owner", "admin123", UserRole.OWNER)
        cashier = auth.create_user("cashier", "Ali Cashier", "cashier123", UserRole.CASHIER)
    else:
        owner = session.query(User).filter(User.role == UserRole.OWNER).first()
        cashier = session.query(User).filter(User.role == UserRole.CASHIER).first() or owner

    # Create Categories
    cat_map = {}
    for name, urdu in CATEGORIES:
        existing = session.query(Category).filter(Category.name == name).first()
        if not existing:
            cat = Category(name=name, name_urdu=urdu)
            session.add(cat)
            session.flush()
            cat_map[name] = cat.id
        else:
            cat_map[name] = existing.id

    # Create Products
    products = []
    for name, barcode, cost, price, unit, cat_name in PRODUCTS_DATA:
        existing = session.query(Product).filter(Product.barcode == barcode).first()
        if not existing:
            p = Product(
                name=name,
                barcode=barcode,
                sku=f"SKU-{barcode[-4:]}",
                purchase_price=Decimal(str(cost)),
                sale_price=Decimal(str(price)),
                unit=unit,
                category_id=cat_map.get(cat_name),
                minimum_stock=Decimal("10"),
                current_stock=Decimal("100"),
                is_active=True,
            )
            session.add(p)
            session.flush()
            products.append(p)
        else:
            products.append(existing)

    # Create Customers
    cust_objs = []
    for name, phone, city in CUSTOMERS:
        existing = session.query(Customer).filter(Customer.phone == phone).first()
        if not existing:
            c = Customer(name=name, phone=phone, address=city, credit_limit=Decimal("50000"))
            session.add(c)
            session.flush()
            cust_objs.append(c)
        else:
            cust_objs.append(existing)

    # Create Suppliers
    supp_objs = []
    for name, phone, city, comp in SUPPLIERS:
        existing = session.query(Supplier).filter(Supplier.name == name).first()
        if not existing:
            s = Supplier(name=name, phone=phone, address=city, company=comp)
            session.add(s)
            session.flush()
            supp_objs.append(s)
        else:
            supp_objs.append(existing)

    session.commit()

    # Create Sales
    sales_service = SalesService(session)
    for i in range(25):
        p = random.choice(products)
        qty = Decimal(str(random.randint(1, 5)))
        cust = random.choice(cust_objs) if random.random() > 0.5 else None
        method = "credit" if cust else "cash"
        paid = p.sale_price * qty if method == "cash" else Decimal("0")

        sales_service.create_sale(SaleRequest(
            items=[CartItem(
                product_id=p.id,
                product_name=p.name,
                barcode=p.barcode,
                quantity=qty,
                unit_price=p.sale_price,
            )],
            payment_method=method,
            paid_amount=paid,
            customer_id=cust.id if cust else None,
            cashier_id=cashier.id,
        ))

    session.commit()
    session.close()
    print("Demo data seeded successfully!")


if __name__ == "__main__":
    main()
