"""
Reusable Table Component with checkbox support, actions, and flexible fields.
Based on QTableWidget from mods_tab.py.
"""

from typing import List, Dict, Any, Callable, Optional
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QWidget, QHBoxLayout, QPushButton, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from shared.ui.theme_manager import ThemeManager


class TableColumn:
    """Represents a table column configuration."""
    def __init__(self, key: str, header: str, width_mode: QHeaderView.ResizeMode = QHeaderView.ResizeToContents,
                 fixed_width: Optional[int] = None, alignment: Qt.AlignmentFlag = Qt.AlignLeft):
        self.key = key
        self.header = header
        self.width_mode = width_mode
        self.fixed_width = fixed_width
        self.alignment = alignment


class TableAction:
    """Represents an action button in the table."""
    def __init__(self, key: str, text: str, callback: Callable[[int], None], icon: Optional[str] = None):
        self.key = key
        self.text = text
        self.callback = callback
        self.icon = icon


class ReusableTable(QTableWidget):
    """
    Reusable table component with:
    - Checkbox column for selection
    - Flexible columns via props
    - Action buttons column
    - Single/multi selection support
    - Alternating row colors
    """

    # Signals
    item_selected = Signal(list)  # Emits list of selected row indices
    checkbox_toggled = Signal(int, bool)  # Row index, checked state

    def __init__(self, columns: List[TableColumn], actions: Optional[List[TableAction]] = None,
                 has_checkbox: bool = True, selection_mode: QAbstractItemView.SelectionMode = QAbstractItemView.SelectRows,
                 parent=None):
        super().__init__(parent)

        self.columns = columns
        self.actions = actions or []
        self.has_checkbox = has_checkbox
        self.selection_mode = selection_mode
        self._data = []  # Store row data

        self._setup_table()
        self._connect_signals()

    def _setup_table(self):
        """Setup table structure and appearance."""
        # Calculate column count
        col_count = len(self.columns)
        if self.has_checkbox:
            col_count += 1
        if self.actions:
            col_count += 1

        self.setColumnCount(col_count)
        self.setSelectionBehavior(self.selection_mode)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)  # Enable column sorting

        # Set headers
        headers = []
        if self.has_checkbox:
            headers.append("")  # Checkbox column
        headers.extend([col.header for col in self.columns])
        if self.actions:
            headers.append("")  # Actions column

        self.setHorizontalHeaderLabels(headers)

        # Configure header resize modes
        header = self.horizontalHeader()
        col_idx = 0

        if self.has_checkbox:
            header.setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
            col_idx += 1

        for col in self.columns:
            if col.fixed_width:
                header.setSectionResizeMode(col_idx, QHeaderView.Fixed)
                self.setColumnWidth(col_idx, col.fixed_width)
            else:
                header.setSectionResizeMode(col_idx, col.width_mode)
            col_idx += 1

        if self.actions:
            header.setSectionResizeMode(col_idx, QHeaderView.Fixed)
            self.setColumnWidth(col_idx, 80)  # Fixed width for actions

        # Set row height
        try:
            self.verticalHeader().setDefaultSectionSize(36)
        except Exception:
            pass

    def _connect_signals(self):
        """Connect table signals."""
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemChanged.connect(self._on_item_changed)

    def _on_selection_changed(self):
        """Handle row selection changes."""
        selected_rows = set()
        for item in self.selectedItems():
            selected_rows.add(item.row())
        self.item_selected.emit(list(selected_rows))

    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle item changes (checkboxes)."""
        if item.column() == 0 and self.has_checkbox:  # Checkbox column
            checkbox = self.cellWidget(item.row(), 0)
            if isinstance(checkbox, QCheckBox):
                self.checkbox_toggled.emit(item.row(), checkbox.isChecked())

    def set_data(self, data: List[Dict[str, Any]]):
        """Set table data."""
        self._data = data
        self.setRowCount(len(data))

        for row_idx, row_data in enumerate(data):
            col_idx = 0

            # Checkbox column
            if self.has_checkbox:
                checkbox = QCheckBox()
                checkbox.setChecked(row_data.get('checked', False))
                self.setCellWidget(row_idx, col_idx, checkbox)
                col_idx += 1

            # Data columns
            for col in self.columns:
                value = row_data.get(col.key, "")
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(col.alignment)
                
                # Set custom properties
                if col.key == "status" and "status_color" in row_data:
                    item.setForeground(QColor(row_data["status_color"]))
                if col.key == "status" and "status_icon" in row_data:
                    try:
                        from shared.ui.icons import Icons
                        item.setIcon(Icons.get_icon(row_data["status_icon"], size=16))
                    except Exception:
                        pass
                
                self.setItem(row_idx, col_idx, item)
                col_idx += 1

            # Actions column
            if self.actions:
                actions_widget = self._create_actions_widget(row_idx)
                self.setCellWidget(row_idx, col_idx, actions_widget)

    def get_row_data(self, row_idx: int) -> Optional[Dict[str, Any]]:
        """Get data for a specific row."""
        if 0 <= row_idx < len(self._data):
            return self._data[row_idx]
        return None

    def get_checked_rows(self) -> List[Dict[str, Any]]:
        """Get data for all checked rows."""
        checked_rows = []
        for row_idx in range(self.rowCount()):
            if self.has_checkbox:
                checkbox_widget = self.cellWidget(row_idx, 0)
                if isinstance(checkbox_widget, QCheckBox) and checkbox_widget.isChecked():
                    row_data = self.get_row_data(row_idx)
                    if row_data:
                        checked_rows.append(row_data)
        return checked_rows

    def _create_actions_widget(self, row_idx: int) -> QWidget:
        """Create actions widget for a row."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        for action in self.actions:
            btn = QPushButton(action.text)
            if action.icon:
                # Assume icon loading from Icons
                pass  # TODO: integrate with icon system
            btn.clicked.connect(lambda checked=False, r=row_idx, a=action: a.callback(r))
            layout.addWidget(btn)

        layout.addStretch()
        return widget

    def get_selected_rows(self) -> List[int]:
        """Get list of selected row indices."""
        selected_rows = set()
        for item in self.selectedItems():
            selected_rows.add(item.row())
        return list(selected_rows)

    def get_checked_rows(self) -> List[int]:
        """Get list of checked row indices."""
        checked_rows = []
        if not self.has_checkbox:
            return checked_rows

        for row in range(self.rowCount()):
            checkbox = self.cellWidget(row, 0)
            if isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                checked_rows.append(row)
        return checked_rows

    def set_row_checked(self, row_idx: int, checked: bool):
        """Set checkbox state for a row."""
        if self.has_checkbox and 0 <= row_idx < self.rowCount():
            checkbox = self.cellWidget(row_idx, 0)
            if isinstance(checkbox, QCheckBox):
                checkbox.setChecked(checked)

    def update_row_data(self, row_idx: int, data: Dict[str, Any]):
        """Update data for a specific row."""
        if not (0 <= row_idx < self.rowCount()):
            return

        col_idx = 0
        if self.has_checkbox:
            col_idx += 1

        for col in self.columns:
            if col.key in data:
                value = data[col.key]
                item = self.item(row_idx, col_idx)
                if item:
                    item.setText(str(value))
            col_idx += 1

    def clear_data(self):
        """Clear all table data."""
        self.setRowCount(0)
