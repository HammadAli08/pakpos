# PakPOS — Agent & Contributor Guide

## Project Identity

**Name**: PakPOS  
**Tagline**: Simple billing. Local data. Works offline.  
**Version**: 1.0.0  
**Platform**: Windows 10/11 desktop (developed on Fedora Linux)  
**GUI Framework**: PySide6  
**Database**: SQLite via SQLAlchemy 2.0  
**Packaging**: PyInstaller → Inno Setup  
**CI/CD**: GitHub Actions (windows-latest)

---

## Development Environment

- **Fedora Linux x86_64**
- Python 3.12+ (managed via `uv`)
- No C/C++ compiler intentionally required
- No Windows toolchain required for development
- Windows build happens on GitHub Actions `windows-latest` runner

### Confirmed Available

| Tool | Minimum Version |
|------|----------------|
| Python | 3.12 |
| uv | 0.8+ |
| git | 2.x |
| PySide6 | 6.7+ |
| SQLAlchemy | 2.0+ |
| pytest | 7+ |

---

## Architecture Rules

### Layer Separation (MANDATORY)

```
UI (PySide6 widgets)
       │
       ▼
Services (business logic)
       │
       ▼
Repositories (data access)
       │
       ▼
SQLAlchemy Models → SQLite
```

- **UI must never contain SQL or business logic**
- **Services must never import PySide6**
- **Repositories must never contain business logic**
- **Models must never call services**

### File Layout

```
pakpos/
├── config/        # App settings, paths, constants
├── database/
│   ├── models/    # SQLAlchemy ORM models
│   └── repositories/  # Data access layer
├── services/      # Business logic
├── hardware/      # Printer, barcode, cash drawer abstractions
├── ui/            # All PySide6 code
└── utils/         # Shared utilities (logging, validation, formatting)
```

---

## Coding Rules

### Python

1. Use Python 3.12+ type hints everywhere
2. Use dataclasses or Pydantic-style for DTOs between layers
3. No raw SQL in UI or service layers; use repository methods
4. All database operations must be wrapped in explicit transactions
5. Never mutate `current_stock` without creating a `StockMovement` record
6. Use `argon2-cffi` or `bcrypt` for password hashing; never store plaintext

### Error Handling

1. Never show raw Python exceptions to end users
2. Log exceptions with full traceback to application log
3. Show friendly error dialog with error reference code
4. Sale safety: if print fails, KEEP the saved sale — do not roll back

### Database

1. Enable `PRAGMA foreign_keys = ON` on every connection
2. Enable WAL mode: `PRAGMA journal_mode = WAL`
3. Use parameterized queries only; no string interpolation in SQL
4. Index: barcode, sku, product name, invoice_number, sale date, customer_id, supplier_id
5. Financial records: NEVER physically delete (use void/deactivate)

### Security

1. Passwords must use bcrypt (cost factor ≥ 12)
2. No secrets in source code
3. No plaintext passwords in logs or backups
4. Input validation at service layer (not just UI)

---

## Testing Rules

### Required Tests

Every service function must have a unit test.  
Every integration flow must have an integration test.

### Mandatory Flows to Test

1. **Sale flow**: Product → Cart → Sale → Inventory decrease → Stock movement → Ledger
2. **Purchase flow**: Purchase → Inventory increase → Stock movement → Supplier ledger
3. **Return flow**: Return → Inventory increase → Financial adjustment
4. **Backup/Restore**: Backup → Delete DB → Restore → Verify records

### Test Conventions

- Use `pytest` with `conftest.py` for shared fixtures
- Use in-memory SQLite for unit tests
- Use `MockPrinterAdapter` — never a real printer in tests
- Use `MockBarcodeScanner` — never real hardware in tests
- No external API calls in tests (offline-first enforced in tests too)

### Test Command

```bash
uv run pytest tests/ -v
```

---

## Hardware Abstraction Rules

### Printer

```python
class PrinterBase(ABC):
    def print_receipt(self, receipt: Receipt) -> PrintResult: ...
    def print_test(self) -> PrintResult: ...
    def is_available(self) -> bool: ...
```

Implementations:
- `MockPrinterAdapter` — used in tests, saves to file
- `WindowsPrinterAdapter` — uses Windows printing APIs (Windows only)
- `EscPosPrinterAdapter` — raw ESC/POS (optional, for compatible printers)

**Sale must be saved before print attempt. Print failure must NOT roll back the sale.**

### Barcode Scanner

USB keyboard-wedge: scanner types barcode as keyboard input + Enter.  
`BarcodeInput` widget captures this in the search field.  
`MockBarcodeScanner` used in tests.

### Cash Drawer

ESC/POS pulse command. Config only in MVP. Graceful no-op if unsupported.

---

## Critical Business Rules

1. **Offline-first**: All normal operations work without internet
2. **Atomic transactions**: Sale = sale + items + stock movements + ledger (all or nothing)
3. **Stock audit trail**: Every stock change → StockMovement record
4. **Financial integrity**: No void/cancel without audit trail
5. **No fake features**: Every button must do what it says
6. **Backup safety**: Never overwrite-only backup; always keep previous
7. **Restore safety**: Always create safety backup before restore

---

## Deployment Rules

### Build Process (GitHub Actions only for Windows .exe)

1. `windows-latest` runner
2. Install Python 3.12
3. Install uv
4. `uv sync --frozen`
5. `uv run pytest tests/` — must pass
6. `uv run pyinstaller pakpos.spec`
7. Compile Inno Setup → `PakPOS-Setup.exe`
8. Upload artifacts

### Database Paths (Windows)

- Database: `%PROGRAMDATA%\PakPOS\data\pos.db`
- Backups: `%PROGRAMDATA%\PakPOS\backups\`
- Logs: `%PROGRAMDATA%\PakPOS\logs\`
- Config: `%PROGRAMDATA%\PakPOS\config\`

**Never store mutable data inside `C:\Program Files\PakPOS\`**

### Version Strategy

- `MAJOR.MINOR.PATCH`
- Database migrations via Alembic
- Upgrade = backup → migrate → validate → restart

---

## What Requires Windows Hardware Testing

The following CANNOT be verified on Fedora:

| Feature | Fedora | Windows |
|---------|--------|---------|
| Thermal printer printing | MockPrinter ✓ | Real hardware required |
| USB barcode scanner | MockScanner ✓ | Real hardware required |
| Cash drawer pulse | Config only | Real hardware required |
| Windows-installed printer | N/A | Real hardware required |
| Final installer UX | N/A | Real installer test required |

---

## FBR Note

FBR integration is NOT implemented in this version.  
A `FBRIntegrationService` interface exists as a placeholder.  
Tax fields, invoice metadata, and QR fields are designed for future compliance.  
Do NOT claim FBR compliance without official API implementation and legal verification.

---

## Things We Will Never Do

- Install gcc/g++/clang/MSVC for PakPOS build (pre-existing system gcc is irrelevant)
- Add a web server or FastAPI for the local single-PC version
- Add cloud sync without explicit requirement
- Call any external API during normal POS operation
- Fake FBR integration
- Store passwords in plaintext
- Allow silent data loss
- Roll back a saved sale because printing failed
- Delete financial records
