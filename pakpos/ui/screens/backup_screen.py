"""
BackupScreen — Create and restore database backups.
"""
from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QFileDialog
)

from pakpos.services.backup_service import BackupService, BackupError
from pakpos.utils.logger import get_logger

logger = get_logger(__name__)


class BackupScreen(QWidget):
    """
    Database Backup & Restore Interface.
    """

    def __init__(self, current_user, parent=None) -> None:
        super().__init__(parent)
        self.current_user = current_user
        self.backup_service = BackupService()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        lbl_title = QLabel("Database Backup & Disaster Recovery")
        lbl_title.setObjectName("label_title")
        layout.addWidget(lbl_title)

        btn_layout = QHBoxLayout()
        btn_create = QPushButton("+ Create Manual Backup Now")
        btn_create.setObjectName("btn_success")
        btn_create.clicked.connect(self._on_create_backup)

        btn_restore = QPushButton("Restore Selected Backup")
        btn_restore.setObjectName("btn_warning")
        btn_restore.clicked.connect(self._on_restore_backup)

        btn_layout.addWidget(btn_create)
        btn_layout.addWidget(btn_restore)
        layout.addLayout(btn_layout)

        layout.addWidget(QLabel("Available Backups:"))
        self.list_backups = QListWidget()
        layout.addWidget(self.list_backups)

        self._load_backups()

    def _load_backups(self) -> None:
        self.list_backups.clear()
        backups = self.backup_service.list_backups()
        for b in backups:
            size_kb = b.stat().st_size / 1024
            item = QListWidgetItem(f"{b.name} ({size_kb:.1f} KB)")
            item.setData(100, str(b))
            self.list_backups.addItem(item)

    def _on_create_backup(self) -> None:
        try:
            path = self.backup_service.create_backup(label="manual")
            QMessageBox.information(self, "Backup Created", f"Backup created successfully at:\n{path}")
            self._load_backups()
        except BackupError as e:
            QMessageBox.critical(self, "Backup Failed", str(e))

    def _on_restore_backup(self) -> None:
        current_item = self.list_backups.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Selection Required", "Please select a backup from the list to restore.")
            return

        backup_path = Path(current_item.data(100))
        confirm = QMessageBox.question(
            self,
            "Confirm Database Restore",
            f"Are you sure you want to restore database from:\n{backup_path.name}?\n\n"
            "A safety backup of the current database will be created first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.backup_service.restore_backup(backup_path)
                QMessageBox.information(
                    self, "Restore Complete", "Database restored successfully!\n\nPlease restart PakPOS."
                )
            except BackupError as e:
                QMessageBox.critical(self, "Restore Failed", str(e))
