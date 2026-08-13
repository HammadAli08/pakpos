"""
PakPOS Application Settings & Configuration.

Handles platform-specific paths for Windows (production) and Linux (development).
Never stores mutable data inside the installation directory.
"""
from __future__ import annotations

import os
import sys
import platform
from pathlib import Path
from dataclasses import dataclass, field


def _get_app_data_dir() -> Path:
    """Return the writable application-data directory (platform-aware)."""
    if platform.system() == "Windows":
        base = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
    else:
        # Linux development: use XDG_DATA_HOME or ~/.local/share
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "PakPOS"


APP_DATA_DIR: Path = _get_app_data_dir()
DATA_DIR: Path = APP_DATA_DIR / "data"
BACKUP_DIR: Path = APP_DATA_DIR / "backups"
LOG_DIR: Path = APP_DATA_DIR / "logs"
CONFIG_DIR: Path = APP_DATA_DIR / "config"
EXPORT_DIR: Path = APP_DATA_DIR / "exports"

DB_PATH: Path = DATA_DIR / "pos.db"
DB_URL: str = f"sqlite:///{DB_PATH}"

APP_NAME: str = "PakPOS"
APP_VERSION: str = "1.0.0"
APP_TAGLINE: str = "Simple billing. Local data. Works offline."

# Receipt defaults
DEFAULT_PAPER_WIDTH_MM: int = 80
SUPPORTED_PAPER_WIDTHS: list[int] = [58, 80]

# Backup defaults
BACKUP_RETENTION_DAYS: int = 30
AUTO_BACKUP_ENABLED: bool = True

# Security
BCRYPT_ROUNDS: int = 12
SESSION_TIMEOUT_MINUTES: int = 60

# Performance targets
BARCODE_LOOKUP_TIMEOUT_MS: int = 100
PRODUCT_SEARCH_TIMEOUT_MS: int = 100

# FBR placeholder — NOT implemented
FBR_ENABLED: bool = False


@dataclass
class AppPaths:
    """All writable paths used by PakPOS."""
    app_data: Path = field(default_factory=lambda: APP_DATA_DIR)
    data: Path = field(default_factory=lambda: DATA_DIR)
    backups: Path = field(default_factory=lambda: BACKUP_DIR)
    logs: Path = field(default_factory=lambda: LOG_DIR)
    config: Path = field(default_factory=lambda: CONFIG_DIR)
    exports: Path = field(default_factory=lambda: EXPORT_DIR)
    db: Path = field(default_factory=lambda: DB_PATH)

    def ensure_all(self) -> None:
        """Create all required directories if they don't exist."""
        for path in [self.data, self.backups, self.logs, self.config, self.exports]:
            path.mkdir(parents=True, exist_ok=True)


# Singleton paths instance
paths = AppPaths()
