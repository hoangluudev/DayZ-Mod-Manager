"""
Lazy Loading Dialog Component

Provides a reusable progress dialog for long-running operations.
"""

from PySide6.QtWidgets import QProgressDialog, QApplication
from PySide6.QtCore import Qt

from shared.utils.locale_manager import tr


class LazyLoadingDialog:
    """Reusable lazy loading dialog with indeterminate progress."""

    def __init__(self, title: str = "", message: str = "", parent=None):
        self.title = title or tr("common.loading")
        self.message = message or tr("common.please_wait")
        self.parent = parent
        self.dialog = None

    def show(self):
        """Show the loading dialog."""
        self.dialog = QProgressDialog(self.message, tr("common.cancel"), 0, 0, self.parent)
        self.dialog.setWindowTitle(self.title)
        self.dialog.setWindowModality(Qt.WindowModal)
        self.dialog.setAutoReset(False)
        self.dialog.setAutoClose(False)
        self.dialog.show()
        QApplication.processEvents()  # Allow UI to update

    def hide(self):
        """Hide the loading dialog."""
        if self.dialog:
            self.dialog.hide()
            self.dialog = None

    def is_cancelled(self) -> bool:
        """Check if the operation was cancelled."""
        return self.dialog and self.dialog.wasCanceled() if self.dialog else False

    def set_message(self, message: str):
        """Update the loading message."""
        if self.dialog:
            self.dialog.setLabelText(message)
            QApplication.processEvents()