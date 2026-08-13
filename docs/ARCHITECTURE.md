# PakPOS — Architecture

## Overview

PakPOS is a Windows desktop Point of Sale application built on PySide6 and SQLite.
The architecture follows strict layer separation to ensure testability, maintainability,
and the ability to add features (cloud sync, FBR, multi-branch) without breaking the core.

---

## Layer Diagram

```
┌─────────────────────────────────────────────────┐
│                 PySide6 UI Layer                │
│  windows/ │ screens/ │ dialogs/ │ widgets/      │
│  ← No SQL, No business logic, No direct DB →   │
└────────────────────┬────────────────────────────┘
                     │ calls
┌────────────────────▼────────────────────────────┐
│              Services Layer                     │
│  SalesService │ InventoryService │ AuthService  │
│  PurchaseService │ ReportService │ BackupService │
│  ← No PySide6 imports →                        │
└────────────────────┬────────────────────────────┘
                     │ calls
┌────────────────────▼────────────────────────────┐
│            Repositories Layer                   │
│  ProductRepo │ SaleRepo │ CustomerRepo          │
│  SupplierRepo │ ExpenseRepo │ StockMovementRepo  │
│  ← No business logic, only data access →       │
└────────────────────┬────────────────────────────┘
                     │ uses
┌────────────────────▼────────────────────────────┐
│         SQLAlchemy 2.0 Models + SQLite          │
│  products │ sales │ purchases │ customers       │
│  suppliers │ stock_movements │ audit_log        │
└─────────────────────────────────────────────────┘
```

---

## Hardware Abstraction

```
┌─────────────────────────────────────────────────┐
│            Hardware Abstraction Layer           │
│                                                 │
│  PrinterBase (ABC)                              │
│  ├── MockPrinterAdapter  (tests, Fedora)        │
│  ├── WindowsPrinterAdapter  (Windows production)│
│  └── EscPosPrinterAdapter  (optional ESC/POS)  │
│                                                 │
│  BarcodeScannerBase (ABC)                       │
│  ├── MockBarcodeScanner  (tests)                │
│  └── HIDKeyboardWedge  (production, via UI)     │
│                                                 │
│  CashDrawerBase (ABC)                           │
│  └── EscPosCashDrawer  (optional)               │
└─────────────────────────────────────────────────┘
```

---

## Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `users` | Authentication, roles |
| `categories` | Product categories |
| `products` | Product master with pricing |
| `customers` | Customer ledger |
| `suppliers` | Supplier master |
| `sales` | Sale header |
| `sale_items` | Sale line items |
| `purchases` | Purchase header |
| `purchase_items` | Purchase line items |
| `payments` | Customer/supplier payments |
| `expenses` | Business expenses |
| `stock_movements` | Full inventory audit trail |
| `audit_log` | All important system actions |
| `settings` | Application configuration |

### Stock Movement Types

```
PURCHASE          → stock increase via purchase
SALE              → stock decrease via sale
SALE_RETURN       → stock increase via return
PURCHASE_RETURN   → stock decrease
DAMAGE            → stock decrease with reason
ADJUSTMENT        → manual admin adjustment
OPENING_STOCK     → initial stock entry
```

### Transaction Atomicity

The following operations are always atomic (all-or-nothing):

**Sale Transaction:**
```sql
BEGIN;
  INSERT INTO sales ...
  INSERT INTO sale_items ... (multiple)
  UPDATE products SET current_stock = current_stock - qty ...
  INSERT INTO stock_movements ... (multiple)
  INSERT INTO payments ... (if cash)
  UPDATE customers SET balance = ... (if credit)
  INSERT INTO audit_log ...
COMMIT;
```

**Purchase Transaction:**
```sql
BEGIN;
  INSERT INTO purchases ...
  INSERT INTO purchase_items ... (multiple)
  UPDATE products SET current_stock = current_stock + qty ...
  INSERT INTO stock_movements ... (multiple)
  UPDATE suppliers SET balance = ... (if credit)
  INSERT INTO audit_log ...
COMMIT;
```

---

## SQLite Configuration

Every connection applies:

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;  -- 64MB cache
PRAGMA temp_store = MEMORY;
```

---

## File Structure

```
pakpos/
├── main.py                    # Entry point
├── config/
│   └── settings.py            # AppSettings, paths, constants
├── database/
│   ├── engine.py              # SQLAlchemy engine + session factory
│   ├── models/                # ORM models (one per table)
│   │   ├── product.py
│   │   ├── category.py
│   │   ├── customer.py
│   │   ├── supplier.py
│   │   ├── sale.py
│   │   ├── purchase.py
│   │   ├── payment.py
│   │   ├── expense.py
│   │   ├── stock_movement.py
│   │   ├── user.py
│   │   └── audit.py
│   └── repositories/          # Data access (one per aggregate)
│       ├── base.py
│       ├── product_repo.py
│       ├── sale_repo.py
│       ├── purchase_repo.py
│       ├── customer_repo.py
│       ├── supplier_repo.py
│       └── expense_repo.py
├── services/                  # Business logic
│   ├── sales_service.py
│   ├── inventory_service.py
│   ├── purchase_service.py
│   ├── customer_service.py
│   ├── supplier_service.py
│   ├── report_service.py
│   ├── backup_service.py
│   ├── auth_service.py
│   └── audit_service.py
├── hardware/
│   ├── printer/
│   │   ├── base.py            # PrinterBase ABC
│   │   ├── mock_adapter.py    # Tests and Fedora
│   │   └── windows_adapter.py # Windows production
│   ├── barcode/
│   │   ├── base.py
│   │   └── mock_scanner.py
│   └── cash_drawer/
│       └── base.py
├── ui/
│   ├── app.py                 # QApplication setup
│   ├── windows/
│   │   ├── main_window.py     # Main nav shell
│   │   ├── login_window.py    # Login screen
│   │   └── setup_wizard.py    # First-run wizard
│   ├── screens/               # Full-page screens
│   │   ├── pos_screen.py      # ← Most important
│   │   ├── products_screen.py
│   │   ├── purchases_screen.py
│   │   ├── customers_screen.py
│   │   ├── suppliers_screen.py
│   │   ├── inventory_screen.py
│   │   ├── reports_screen.py
│   │   ├── dashboard_screen.py
│   │   ├── settings_screen.py
│   │   ├── backup_screen.py
│   │   └── diagnostics_screen.py
│   ├── dialogs/
│   │   ├── payment_dialog.py
│   │   ├── return_dialog.py
│   │   ├── customer_dialog.py
│   │   └── product_dialog.py
│   └── widgets/
│       ├── barcode_input.py   # BarcodeInput QLineEdit
│       ├── cart_widget.py     # Cart table
│       └── numeric_pad.py     # On-screen numpad
└── utils/
    ├── validators.py
    ├── formatters.py          # Currency, date formatting
    └── logger.py              # Structured application logging
```

---

## Security Model

| Concern | Solution |
|---------|----------|
| Password storage | bcrypt cost=12 |
| SQL injection | SQLAlchemy parameterized queries only |
| Plaintext secrets | None allowed in source or logs |
| Session timeout | Configurable idle timeout |
| Role enforcement | Service layer checks role before action |
| Audit trail | All important actions logged |

---

## Deployment Architecture

### Development (Fedora)

```
Developer → uv sync → pytest → uv run pakpos
```

### Production Build (GitHub Actions)

```
Push to main
    │
    ▼
windows-latest runner
    │
    ├── uv sync --frozen
    ├── pytest tests/
    ├── pyinstaller pakpos.spec
    └── iscc installer/pakpos.iss
            │
            ▼
       PakPOS-Setup.exe (artifact)
```

### Windows Installation

```
PakPOS-Setup.exe
    │
    ├── Install to C:\Program Files\PakPOS\
    ├── Create %PROGRAMDATA%\PakPOS\{data,backups,logs,config}\
    ├── Create Start Menu shortcut
    ├── Create Desktop shortcut (optional)
    └── Register uninstaller
```

---

## Future Architecture Hooks

The following are designed for future extension but NOT implemented in v1.0:

| Feature | Hook |
|---------|------|
| Cloud sync | `SyncService` interface in services/ |
| FBR integration | `FBRIntegrationService` stub |
| Multi-branch | `BranchRepository` placeholder |
| Mobile app | REST API can be added as optional server |
| AI insights | Deterministic insights layer, AI-extensible |
