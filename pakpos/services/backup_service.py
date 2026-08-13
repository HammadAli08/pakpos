"""
Backup Service — creates and restores ZIP backups of the database.
Safety rules:
- Never overwrite the only backup
- Always timestamp backups
- Always create a safety backup before restoring
"""
from __future__ import annotations

import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from pakpos.config.settings import DB_PATH, BACKUP_DIR, BACKUP_RETENTION_DAYS
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class BackupError(Exception):
    pass


class BackupService:

    def __init__(
        self,
        db_path: Path = DB_PATH,
        backup_dir: Path = BACKUP_DIR,
        retention_days: int = BACKUP_RETENTION_DAYS,
    ) -> None:
        self._db_path = db_path
        self._backup_dir = backup_dir
        self._retention_days = retention_days

    def create_backup(self, label: str = "") -> Path:
        """Create a timestamped ZIP backup of the database."""
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        suffix = f"_{label}" if label else ""
        filename = f"pakpos_backup_{timestamp}{suffix}.zip"
        backup_path = self._backup_dir / filename

        if not self._db_path.exists():
            raise BackupError(f"Database not found at {self._db_path}")

        try:
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(self._db_path, arcname="pos.db")
            logger.info("Backup created: %s", backup_path)
        except Exception as e:
            logger.error("Backup failed: %s", e, exc_info=True)
            raise BackupError(f"Backup failed: {e}") from e

        self._prune_old_backups()
        return backup_path

    def restore_backup(self, backup_path: Path) -> None:
        """
        Restore a backup.
        1. Verify the backup is valid
        2. Create a safety backup of the current database
        3. Restore
        """
        if not backup_path.exists():
            raise BackupError(f"Backup file not found: {backup_path}")

        # Verify ZIP contains pos.db
        try:
            with zipfile.ZipFile(backup_path, "r") as zf:
                if "pos.db" not in zf.namelist():
                    raise BackupError("Invalid backup: pos.db not found in archive")
        except zipfile.BadZipFile as e:
            raise BackupError(f"Corrupt backup file: {e}") from e

        # Safety backup before restore
        if self._db_path.exists():
            self.create_backup(label="pre_restore_safety")

        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(backup_path, "r") as zf:
                db_bytes = zf.read("pos.db")
                self._db_path.write_bytes(db_bytes)
            logger.info("Database restored from: %s", backup_path)
        except Exception as e:
            logger.error("Restore failed: %s", e, exc_info=True)
            raise BackupError(f"Restore failed: {e}") from e

    def list_backups(self) -> list[Path]:
        """Return all backup files sorted newest first."""
        if not self._backup_dir.exists():
            return []
        return sorted(
            self._backup_dir.glob("pakpos_backup_*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def _prune_old_backups(self) -> None:
        """Delete backups older than retention_days but keep at least 3."""
        backups = self.list_backups()
        if len(backups) <= 3:
            return
        cutoff = datetime.now(timezone.utc).timestamp() - (self._retention_days * 86400)
        for backup in backups[3:]:
            if backup.stat().st_mtime < cutoff:
                backup.unlink()
                logger.info("Pruned old backup: %s", backup.name)
