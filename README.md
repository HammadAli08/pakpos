# PakPOS

**Simple billing. Local data. Works offline.**

A production-quality, offline-first Windows Point of Sale (POS) application for Pakistani retail shops.

---

## What Is PakPOS?

PakPOS is a Windows desktop POS application built specifically for Pakistani small and medium retail businesses — kiryana stores, general stores, mini marts, hardware shops, mobile/accessory shops, and clothing stores.

**Core features:**
- Full billing and cashiering
- Inventory management with stock movements
- Customer Khata (credit ledger)
- Supplier management and purchases
- Sales returns
- Professional receipt printing (thermal 58mm/80mm)
- USB barcode scanner support (keyboard-wedge HID)
- Offline-first — works without internet
- Local SQLite database — your data stays on your machine
- Automatic and manual backups
- Multi-user with role-based access (Owner / Manager / Cashier)
- FBR-ready architecture (implementation requires official API)

---

## Architecture

```
PySide6 UI
    │
    ▼
Services (business logic)
    │
    ▼
Repositories (data access)
    │
    ▼
SQLAlchemy 2.0 → SQLite
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| SQLite | No database server required; single-file backup |
| PySide6 | Native Windows UI, no browser/Electron |
| PyInstaller | Bundles Python — user installs nothing |
| Inno Setup | Professional Windows installer |
| Offline-first | Pakistani shops may have unreliable internet |
| bcrypt | Secure password hashing, no plaintext ever |

---

## Development Setup (Fedora Linux)

### Prerequisites

- Python 3.12+
- `uv` (Python package manager)
- `git`

### Install

```bash
git clone <repo-url>
cd pakpos
uv sync
```

### Run

```bash
uv run python -m pakpos.main
```

### Test

```bash
uv run pytest tests/ -v
```

### Seed Demo Data (Development Only)

```bash
uv run python scripts/seed_demo_data.py
```

---

## Windows Build (via GitHub Actions)

The Windows `.exe` and installer are built automatically on every push to `main` using a `windows-latest` GitHub Actions runner.

**You do NOT need Windows locally for development.**

Build artifacts are uploaded to GitHub Actions:
- `PakPOS-Setup.exe` — Windows installer

See `.github/workflows/windows-build.yml` for details.

---

## Database

### Location (Windows)

```
%PROGRAMDATA%\PakPOS\data\pos.db
```

### Backups

```
%PROGRAMDATA%\PakPOS\backups\
```

### Location (Linux Development)

```
~/.local/share/PakPOS/data/pos.db
```

### Migrations

```bash
uv run alembic upgrade head
```

---

## Barcode Scanner

Supports USB HID keyboard-wedge scanners (the most common type).

The scanner sends barcode characters as keyboard input followed by Enter.

**To test your scanner before setup:**
1. Open Notepad
2. Click in the text area
3. Scan any barcode
4. The barcode digits should appear followed by a newline

No special drivers needed for keyboard-wedge scanners.

See `docs/HARDWARE.md` for detailed setup.

---

## Thermal Printer

Supports:
- Any Windows-installed printer (via Windows print dialog)
- ESC/POS compatible printers (raw mode, optional)

Paper widths: 58mm and 80mm

**To test:**
1. Go to Settings → Printer
2. Select your printer
3. Click "Print Test Receipt"

See `docs/HARDWARE.md` for setup.

---

## User Roles

| Role | Permissions |
|------|-------------|
| Owner | Full access including settings, users, reports |
| Manager | Sales, purchases, inventory, reports |
| Cashier | Sales, basic customer functions only |

---

## Backup & Restore

### Manual Backup
Settings → Backup → Backup Now

### Automatic Backup
Runs daily (configurable).

Backups are timestamped ZIP files:
```
2026-08-13_23-00.zip
2026-08-12_23-00.zip
```

### Restore
Settings → Backup → Restore

**A safety backup is always created before restoration.**

---

## FBR / Tax

Tax fields, invoice metadata, and QR-ready invoice fields are built into the data model.

**FBR integration is NOT implemented** in v1.0.

A `FBRIntegrationService` interface exists for future implementation using the official FBR API.

Do NOT claim FBR compliance without official implementation and legal verification.

---

## Troubleshooting

### Application won't start
- Check `%PROGRAMDATA%\PakPOS\logs\` for error details
- Run Settings → Diagnostics

### Printer not printing
- Open Settings → Printer → Test Print
- Verify the printer is selected and installed in Windows

### Barcode scanner not working
- Open Notepad, scan a barcode — if it appears, the scanner works
- Go to Settings → Scanner Test

### Database corruption
- Do NOT delete the database file manually
- Use Settings → Backup → Restore

---

## License

MIT License — see `LICENSE`

---

## Version

1.0.0
