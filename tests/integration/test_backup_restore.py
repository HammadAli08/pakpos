"""
Integration test: Backup & Restore Flow
Backup → Modify DB → Restore → Verify records
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from pakpos.services.backup_service import BackupService
from pakpos.database.models.product import Product


class TestBackupRestoreFlow:

    def test_backup_and_restore_cycle(self, db_engine, db_session, sample_product):
        """Verify backup creates zip and restore recovers state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            fake_db = tmp_path / "test_pos.db"
            backup_dir = tmp_path / "backups"

            # Create dummy DB file
            fake_db.write_text("DUMMY DB CONTENT 12345", encoding="utf-8")

            service = BackupService(db_path=fake_db, backup_dir=backup_dir)

            # 1. Create backup
            backup_file = service.create_backup(label="unit_test")
            assert backup_file.exists()
            assert len(service.list_backups()) == 1

            # 2. Modify original DB file
            fake_db.write_text("CORRUPTED OR DELETED CONTENT", encoding="utf-8")

            # 3. Restore backup
            service.restore_backup(backup_file)

            # 4. Content is restored back to original
            restored_text = fake_db.read_text(encoding="utf-8")
            assert restored_text == "DUMMY DB CONTENT 12345"
