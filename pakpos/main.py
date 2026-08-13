"""
PakPOS Application Entry Point.

Initializes database, creates directories, launches PySide6 UI.
On first run, shows the setup wizard.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

from pakpos.config.settings import paths, APP_NAME, APP_VERSION
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


def main() -> int:
    """Main entry point."""
    try:
        # Ensure all app directories exist
        paths.ensure_all()
        logger.info("Starting %s v%s", APP_NAME, APP_VERSION)

        # Initialize database
        from pakpos.database.engine import init_database
        init_database()
        logger.info("Database initialized at %s", paths.db)

        # Launch UI
        from pakpos.ui.app import run_app
        return run_app(sys.argv)

    except Exception as e:
        logger.critical("Fatal startup error: %s", e, exc_info=True)
        # Try to show an error dialog if Qt is available
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(
                None,
                f"{APP_NAME} — Startup Error",
                f"A fatal error occurred during startup.\n\n"
                f"Error: {e}\n\n"
                f"Please check the log files at:\n{paths.logs}",
            )
        except Exception:
            print(f"FATAL: {e}", file=sys.stderr)
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
