"""
Reusable Table Component with checkbox support, actions, and flexible fields.
Based on QTableWidget from mods_tab.py.
"""

from typing import List, Dict, Any, Callable, Optional
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QWidget, QHBoxLayout, QPushButton, QCheckBox, QToolTip, QComboBox
)
from PySide6.QtCore import Qt, Signal, QItemSelectionModel, QSignalBlocker, QSize, QEvent
from PySide6.QtGui import QColor

from shared.ui.theme_manager import ThemeManager


class TableColumn:
    """Represents a table column configuration."""
    def __init__(self, key: str, header: str, width_mode: QHeaderView.ResizeMode = QHeaderView.ResizeToContents,
                 fixed_width: Optional[int] = None, alignment: Qt.AlignmentFlag = Qt.AlignVCenter | Qt.AlignLeft):
        self.key = key
        self.header = header
        self.width_mode = width_mode
        self.fixed_width = fixed_width
        self.alignment = alignment


class TableAction:
    """Represents a table action button configuration."""
    def __init__(self, key: str, text: str, callback: Callable[[int, Dict[str, Any]], None],
                 icon: Optional[str] = None, tooltip: Optional[str] = None):
        self.key = key
        self.text = text
        self.callback = callback
        self.icon = icon
        self.tooltip = tooltip


class TableGroup:
    """Represents a table row group with header."""
    def __init__(self, name: str, display_name: str, rows: List[Dict[str, Any]], expanded: bool = True,
                 background_color: Optional[str] = None):
        self.name = name
        self.display_name = display_name
        self.rows = rows
        self.expanded = expanded
        self.background_color = background_color


class ReusableTable(QTableWidget):
    """
    Reusable table component with:
    - Checkbox column for selection
    - Flexible columns via props
    - Action buttons column
    - Single/multi selection support
    - Alternating row colors
    - Row grouping support
    """

    # Signals
    item_selected = Signal(list)  # Emits list of selected row indices
    checkbox_toggled = Signal(int, bool)  # Row index, checked state
    group_toggled = Signal(str, bool)  # Group title, expanded state
    row_double_clicked = Signal(int)  # Row index

    def __init__(self, columns: List[TableColumn], actions: Optional[List[TableAction]] = None,
                 has_checkbox: bool = True, selection_mode: QAbstractItemView.SelectionMode = QAbstractItemView.SelectRows,
                 parent=None):
        super().__init__(parent)

        self.columns = columns
        self.actions = actions or []
        self.has_checkbox = has_checkbox
        self.selection_mode = selection_mode
        self._data = []  # Store row data
        self._groups = []  # Store groups
        self._syncing_selection = False
        self._actions_col = None
        self._row_click_toggles_checkbox = False

        self._setup_table()
        self._connect_signals()

    def set_row_click_toggles_checkbox(self, enabled: bool, *, disable_selection_highlight: bool = True):
        """When enabled, left-clicking a row toggles the checkbox.

        This is useful for tables where checkbox state is the primary selection
        mechanism and visual selection highlight is undesired.
        """
        self._row_click_toggles_checkbox = bool(enabled)
        if disable_selection_highlight:
            # Only disable selection highlight when the table actually uses a checkbox column.
            # For tables without checkboxes (e.g. targets/invalid lists), disabling selection makes
            # the UI feel unclickable.
            if self.has_checkbox and self._row_click_toggles_checkbox:
                self.setSelectionMode(QAbstractItemView.NoSelection)
                self.setFocusPolicy(Qt.NoFocus)
            elif self.has_checkbox:
                self.setSelectionMode(QAbstractItemView.MultiSelection)

    def _setup_table(self):
        """Setup table structure and appearance."""
        # Calculate column count
        col_count = len(self.columns)
        if self.has_checkbox:
            col_count += 1
        if self.actions:
            col_count += 1

        self.setColumnCount(col_count)
        # NOTE: selection_mode here is historically used as SelectionBehavior (e.g. SelectRows)
        self.setSelectionBehavior(self.selection_mode)
        # Allow multiple selected rows; we also override click behavior below to avoid Ctrl.
        self.setSelectionMode(QAbstractItemView.MultiSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)  # Enable column sorting
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)  # Prevent editing

        # Subtle row hover highlight (without requiring selection).
        try:
            accent = QColor(ThemeManager.get_accent_color())
            # Slightly stronger in dark themes.
            alpha = 0.10 if ThemeManager.is_dark_theme() else 0.07
            accent.setAlphaF(alpha)
            hover_rgba = f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, {accent.alphaF()})"
            self.setStyleSheet(
                (self.styleSheet() or "")
                + f"\nQTableWidget::item:hover {{ background-color: {hover_rgba}; }}\n"
            )
        except Exception:
            pass

        # Important: ensure hover events are delivered so tooltips work.
        # (cellEntered requires mouse tracking; tooltip events are also more reliable with it.)
        self.setMouseTracking(True)
        try:
            self.viewport().setMouseTracking(True)
        except Exception:
            pass

        # Determine column indices
        self._actions_col = col_count - 1 if self.actions else None

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
            self.setColumnWidth(col_idx, 64)  # Fixed width for actions

        # Set row height
        try:
            self.verticalHeader().setDefaultSectionSize(36)
        except Exception:
            pass

    def _connect_signals(self):
        """Connect table signals."""
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemChanged.connect(self._on_item_changed)
        try:
            self.cellDoubleClicked.connect(lambda r, _c: self.row_double_clicked.emit(r))
        except Exception:
            pass

    def mousePressEvent(self, event):
        if (
            self._row_click_toggles_checkbox
            and self.has_checkbox
            and event.button() == Qt.LeftButton
        ):
            idx = self.indexAt(event.pos())
            if idx.isValid():
                row = idx.row()
                col = idx.column()

                # Don't interfere with interactive cell widgets (actions buttons, checkbox itself, etc.)
                cell_widget = self.cellWidget(row, col)
                if cell_widget is not None:
                    return super().mousePressEvent(event)

                # Check if this is a group header
                row_data = self._data[row] if 0 <= row < len(self._data) else None
                if row_data and row_data.get("_is_group_header"):
                    # Only toggle if not clicking on checkbox column
                    if (not self.has_checkbox or col > 0):
                        group_title = row_data.get("_group_title")
                        if group_title:
                            self.toggle_group(group_title)
                    event.accept()
                    return

                checkbox = self.cellWidget(row, 0)
                if isinstance(checkbox, QCheckBox):
                    checkbox.setChecked(not checkbox.isChecked())
                    event.accept()
                    return

        return super().mousePressEvent(event)

    def viewportEvent(self, event):
        """Handle tooltip display for hovered cells.

        We do this at the viewport level so it works for both:
        - tables populated via `set_data()` (using self._data)
        - tables populated manually with `setItem(...)` (like ModsTab)
        """
        if event.type() == QEvent.ToolTip:
            try:
                pos = event.pos()
                global_pos = event.globalPos()
            except Exception:
                return super().viewportEvent(event)

            row = self.rowAt(pos.y())
            col = self.columnAt(pos.x())

            if row >= 0 and col >= 0:
                item = self.item(row, col)
                if item and item.toolTip():
                    QToolTip.showText(global_pos, item.toolTip(), self.viewport())
                    return True

                # Fallback: if data exists (set_data), show a generic row tooltip.
                if self._data:
                    row_data = self.get_row_data(row)
                    if row_data:
                        # Prefer an explicit pre-formatted tooltip when provided.
                        explicit = row_data.get("_row_tooltip") or row_data.get("tooltip")
                        if isinstance(explicit, str) and explicit.strip():
                            QToolTip.showText(global_pos, explicit, self.viewport())
                            return True

                        tooltip_parts = []
                        name_value = row_data.get("name")
                        folder_value = row_data.get("mod_folder")

                        # Prefer a user-provided tooltip for the hovered column (e.g. name_tooltip)
                        # but fall back to a generic row tooltip.
                        for key, value in row_data.items():
                            if key.startswith("_") or key in (
                                "checked",
                                "status_color",
                                "status_icon",
                                "bikey_color",
                                "bikey_icon",
                                "workshop_id",
                                "install_date",
                                "has_update",
                            ):
                                continue

                            # Avoid showing raw dict/widget descriptors (previously looked like JSON).
                            if isinstance(value, dict):
                                if value.get("widget_type"):
                                    continue
                                value = value.get("text", "")
                                if value in (None, ""):
                                    continue

                            # Avoid noisy non-scalar values.
                            if isinstance(value, (list, tuple, set)):
                                continue
                            if isinstance(value, dict):
                                continue
                            display_key = key.replace("_", " ").title()
                            tooltip_parts.append(f"{display_key}: {value}")

                        # Always show the underlying folder name when it differs from display name.
                        if folder_value and name_value and str(folder_value) != str(name_value):
                            tooltip_parts.insert(0, f"Folder: {folder_value}")

                        tooltip_text = "\n".join(tooltip_parts) if tooltip_parts else ""
                        if tooltip_text:
                            QToolTip.showText(global_pos, tooltip_text, self.viewport())
                            return True

            QToolTip.hideText()
            event.ignore()
            return True

        return super().viewportEvent(event)

    def _on_selection_changed(self):
        """Handle row selection changes."""
        if self._syncing_selection:
            return

        selected_rows = set()
        for item in self.selectedItems():
            selected_rows.add(item.row())
        
        self.item_selected.emit(list(selected_rows))

    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle item changes (checkboxes)."""
        # Legacy support: if a QTableWidgetItem checkbox is used (not our default), handle it.
        if item.column() == 0 and self.has_checkbox:  # Checkbox column
            checkbox = self.cellWidget(item.row(), 0)
            if isinstance(checkbox, QCheckBox):
                # If using widget-based checkboxes we handle in _checkbox_changed instead.
                return
            # Fallback: handle QTableWidgetItem-based checkbox
            try:
                checked = (item.checkState() == Qt.Checked)
            except Exception:
                return
            self.checkbox_toggled.emit(item.row(), checked)

    def _checkbox_changed(self, row_idx: int, state: int):
        """Handle stateChanged from widget-based QCheckBox in the checkbox column.

        Emits `checkbox_toggled` signal. Checkbox is the source of truth for selection.
        """
        checked = (state == Qt.Checked)
        self.checkbox_toggled.emit(row_idx, checked)

    def _on_cell_entered(self, row: int, col: int):
        """Handle cell enter to display tooltip with row data."""
        # Check if the cell item has its own tooltip
        item = self.item(row, col)
        if item and item.toolTip():
            # If item has tooltip, show it using QToolTip
            rect = self.visualItemRect(item)
            global_pos = self.mapToGlobal(rect.topLeft())
            QToolTip.showText(global_pos, item.toolTip(), self)
            return
        
        # Only show row data tooltip if we have data
        if not self._data:
            QToolTip.hideText()
            return
        
        row_data = self.get_row_data(row)
        if not row_data:
            QToolTip.hideText()
            return
        
        # Build tooltip text from row data
        tooltip_parts = []
        for key, value in row_data.items():
            # Skip internal/hidden keys
            if key.startswith("_") or key in ("checked", "status_color", "status_icon", "workshop_id", "install_date", "has_update"):
                continue
            if isinstance(value, dict):
                value = value.get("text", "")
            # Format key nicely
            display_key = key.replace("_", " ").title()
            tooltip_parts.append(f"{display_key}: {value}")

        name_value = row_data.get("name")
        folder_value = row_data.get("mod_folder")
        if folder_value and name_value and str(folder_value) != str(name_value):
            tooltip_parts.insert(0, f"Folder: {folder_value}")
        
        tooltip_text = "\n".join(tooltip_parts) if tooltip_parts else ""
        if tooltip_text:
            rect = self.visualItemRect(self.item(row, col) or self.item(row, 0))
            if rect:
                global_pos = self.mapToGlobal(rect.topLeft())
                QToolTip.showText(global_pos, tooltip_text, self)
        else:
            QToolTip.hideText()

        self._data = []  # Store row data
        self._groups = []  # Store groups
        self._syncing_selection = False
        self._actions_col = None
        self._row_click_toggles_checkbox = False

        self._setup_table()
        self._connect_signals()

    def set_data_with_groups(self, groups: List[TableGroup]):
        """Set table data organized in groups."""
        self._groups = groups
        self._data = []
        
        # Flatten groups into rows, inserting group headers
        for group in groups:
            # Add group header row
            group_header = {
                "_is_group_header": True,
                "_group_title": group.display_name,
                "_group_name": group.name,
                "_group_collapsed": not group.expanded,
                "_group_expandable": True,
                "_group_background": group.background_color,
            }
            # Add empty values for all columns
            for col in self.columns:
                group_header[col.key] = ""
            self._data.append(group_header)
            
            # Add group rows if expanded
            if group.expanded:
                self._data.extend(group.rows)
        
        self._render_data()

    def set_data(self, data: List[Dict[str, Any]]):
        """Set table data without groups."""
        self._groups = []
        self._data = data
        self._render_data()

    def _render_data(self):
        """Render the current data to the table."""
        self.setRowCount(len(self._data))

        for row_idx, row_data in enumerate(self._data):
            col_idx = 0

            # Checkbox column
            if self.has_checkbox:
                if not row_data.get("_is_group_header"):
                    checkbox = QCheckBox()
                    checkbox.setChecked(row_data.get('checked', False))
                    # Connect state change to handler with row index captured
                    checkbox.stateChanged.connect(lambda state, r=row_idx: self._checkbox_changed(r, state))
                    self.setCellWidget(row_idx, col_idx, checkbox)
                col_idx += 1

            # Data columns
            for col in self.columns:
                value = row_data.get(col.key, "")

                # Special handling for group headers
                if row_data.get("_is_group_header"):
                    item = QTableWidgetItem(row_data.get("_group_title", ""))
                    item.setTextAlignment(col.alignment)
                    item.setBackground(QColor(row_data.get("_group_background", "#e0e0e0")))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    # For group headers, start from column 0 to span across checkbox column too
                    span_start_col = 0 if self.has_checkbox else col_idx
                    self.setItem(row_idx, span_start_col, item)
                    # Span across all columns
                    self.setSpan(row_idx, span_start_col, 1, self.columnCount() - span_start_col)
                    break

                # New-style dict cell descriptors
                if isinstance(value, dict):
                    if value.get("widget_type"):
                        widget = self._create_widget_for_data(value, row_idx, row_data)
                        if widget:
                            self.setCellWidget(row_idx, col_idx, widget)
                        col_idx += 1
                        continue

                    item = QTableWidgetItem(str(value.get("text", "")))
                    item.setTextAlignment(col.alignment)

                    if value.get("bold"):
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)

                    if value.get("color") is not None:
                        item.setForeground(value["color"])

                    if value.get("tooltip"):
                        item.setToolTip(value["tooltip"])

                    if value.get("data") is not None:
                        item.setData(Qt.UserRole, value["data"])

                    if value.get("icon") is not None:
                        icon_val = value.get("icon")
                        try:
                            # QIcon / QPixmap-like
                            if hasattr(icon_val, "pixmap"):
                                item.setIcon(icon_val)
                            elif isinstance(icon_val, str):
                                from shared.ui.icons import Icons
                                icon_color = value.get("icon_color") or ThemeManager.get_text_color()
                                item.setIcon(Icons.get_icon(icon_val, color=icon_color, size=16))
                        except Exception:
                            pass

                    self.setItem(row_idx, col_idx, item)
                    col_idx += 1
                    continue

                # Legacy plain-value rendering
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(col.alignment)
                
                # Set custom properties for regular rows
                if col.key == "status" and "status_color" in row_data:
                    item.setForeground(QColor(row_data["status_color"]))
                if col.key == "status" and "status_icon" in row_data:
                    try:
                        from shared.ui.icons import Icons
                        icon_color = row_data.get("status_color") or ThemeManager.get_text_color()
                        item.setIcon(Icons.get_icon(row_data["status_icon"], color=icon_color, size=16))
                    except Exception:
                        pass
                if col.key == "bikey" and "bikey_color" in row_data:
                    item.setForeground(QColor(row_data["bikey_color"]))
                if col.key == "bikey" and "bikey_icon" in row_data:
                    try:
                        from shared.ui.icons import Icons
                        icon_color = row_data.get("bikey_color") or ThemeManager.get_text_color()
                        item.setIcon(Icons.get_icon(row_data["bikey_icon"], color=icon_color, size=16))
                    except Exception:
                        pass
                
                # Set tooltip if provided
                tooltip_key = f"{col.key}_tooltip"
                if tooltip_key in row_data:
                    item.setToolTip(row_data[tooltip_key])
                
                self.setItem(row_idx, col_idx, item)
                col_idx += 1

            # Actions column
            if self.actions and not row_data.get("_is_group_header"):
                actions_widget = self._create_actions_widget(row_idx)
                self.setCellWidget(row_idx, col_idx, actions_widget)

        # Ensure rows expand to fit taller widgets like combo boxes.
        try:
            self.resizeRowsToContents()
        except Exception:
            pass

    def get_row_data(self, row_idx: int) -> Optional[Dict[str, Any]]:
        """Get data for a specific row."""
        if 0 <= row_idx < len(self._data):
            row_data = self._data[row_idx]
            # Skip group headers
            if row_data.get("_is_group_header"):
                return None
            return row_data
        return None

    def is_group_header(self, row_idx: int) -> bool:
        """Check if a row is a group header."""
        if 0 <= row_idx < len(self._data):
            return self._data[row_idx].get("_is_group_header", False)
        return False

    def get_cell_widget(self, row_idx: int, column_key: str) -> Optional[QWidget]:
        """Get widget for a specific cell by column key."""
        # Find column index by key
        for i, col in enumerate(self.columns):
            if col.key == column_key:
                # Adjust for checkbox column
                col_idx = i
                if self.has_checkbox:
                    col_idx += 1
                return self.cellWidget(row_idx, col_idx)
        return None

    def set_cell_data(self, row_idx: int, column_key: str, data: Dict[str, Any]):
        """Update data for a specific cell and refresh display."""
        if 0 <= row_idx < len(self._data):
            row_data = self._data[row_idx]
            if not row_data.get("_is_group_header"):
                # Update the data
                row_data[column_key] = data
                # Re-render the specific cell
                self._render_cell(row_idx, column_key)

    def _render_cell(self, row_idx: int, column_key: str):
        """Re-render a specific cell."""
        row_data = self._data[row_idx]
        
        # Find column index by key
        for i, col in enumerate(self.columns):
            if col.key == column_key:
                # Adjust for checkbox column
                col_idx = i
                if self.has_checkbox:
                    col_idx += 1
                
                data = row_data.get(column_key, {})
                
                # Handle widget cells (combos, etc.)
                if "widget_type" in data:
                    widget = self._create_widget_for_data(data, row_idx, row_data)
                    if widget:
                        self.setCellWidget(row_idx, col_idx, widget)
                else:
                    # Handle text/icon cells
                    item = self.item(row_idx, col_idx)
                    if not item:
                        item = QTableWidgetItem()
                        self.setItem(row_idx, col_idx, item)
                    
                    # Update text
                    if "text" in data:
                        item.setText(str(data["text"]))
                    
                    # Update color
                    if "color" in data:
                        item.setForeground(data["color"])
                    
                    # Update tooltip
                    if "tooltip" in data:
                        item.setToolTip(data["tooltip"])
                    
                    # Update icon
                    if "icon" in data:
                        try:
                            from shared.ui.icons import Icons
                            icon_color = data.get("icon_color") or ThemeManager.get_text_color()
                            item.setIcon(Icons.get_icon(data["icon"], color=icon_color, size=16))
                        except Exception:
                            pass
                break

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

    def get_checked_row_indices(self) -> List[int]:
        """Get row indices for all checked rows (skips group headers)."""
        indices: List[int] = []
        if not self.has_checkbox:
            return indices

        for row_idx in range(self.rowCount()):
            if self.is_group_header(row_idx):
                continue
            checkbox_widget = self.cellWidget(row_idx, 0)
            if isinstance(checkbox_widget, QCheckBox) and checkbox_widget.isChecked():
                indices.append(row_idx)
        return indices

    def toggle_group(self, group_title: str):
        """Toggle a group's collapsed/expanded state."""
        for group in self._groups:
            if group.display_name == group_title:
                group.expanded = not group.expanded
                self.set_data_with_groups(self._groups)
                self.group_toggled.emit(group_title, group.expanded)
                break

    def _create_widget_for_data(self, data: Dict[str, Any], row_idx: int, row_data: Dict[str, Any]) -> Optional[QWidget]:
        """Create a widget based on data configuration."""
        widget_type = data.get("widget_type")
        
        if widget_type == "combo":
            combo = QComboBox()
            combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            combo.setMinimumHeight(32)  # Ensure sufficient height for text display
            
            items = data.get("items", [])
            for item in items:
                if isinstance(item, tuple) and len(item) == 2:
                    combo.addItem(item[0], item[1])
                else:
                    combo.addItem(str(item))
            
            current_data = data.get("current_data")
            if current_data is not None:
                idx = combo.findData(current_data)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            
            # Connect change signal if callback provided
            callback = data.get("callback")
            if callback:
                combo.currentIndexChanged.connect(lambda: callback(row_idx, row_data))
            
            return combo
        
        return None

    def _create_actions_widget(self, row_idx: int) -> QWidget:
        """Create actions widget for a row."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        row_data = self.get_row_data(row_idx)

        for action in self.actions:
            btn = QPushButton(action.text or "")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)

            # Old-style action buttons: centered icon, rounded corners, auto-size.
            if not action.text:
                btn.setFixedSize(28, 28)
                btn.setStyleSheet(
                    "QPushButton{"
                    "background:rgba(255,255,255,0.06);"
                    "border:1px solid rgba(255,255,255,0.12);"
                    "border-radius:6px;"
                    "padding:0px;"
                    "}"
                    "QPushButton:hover{background:rgba(255,255,255,0.10);}"
                    "QPushButton:pressed{background:rgba(255,255,255,0.14);}" 
                )
            else:
                btn.setStyleSheet(
                    "QPushButton{padding:6px 10px;border-radius:6px;}"
                )

            if action.icon:
                try:
                    from shared.ui.icons import Icons
                    btn.setIcon(Icons.get_icon(action.icon, ThemeManager.get_text_color(), 16))
                    btn.setIconSize(QSize(16, 16))
                except Exception:
                    pass

            if action.tooltip:
                btn.setToolTip(action.tooltip)

            btn.clicked.connect(lambda checked=False, r=row_idx, rd=row_data, a=action: a.callback(r, rd))
            layout.addWidget(btn)
        return widget

    def get_selected_rows(self) -> List[int]:
        """Get list of selected row indices."""
        selected_rows = set()
        for item in self.selectedItems():
            selected_rows.add(item.row())
        return list(selected_rows)

    def selected_rows(self) -> List[int]:
        """Alias for get_selected_rows."""
        return self.get_selected_rows()

    # NOTE: get_checked_row_indices is defined above (skipping group headers). Keep only one implementation.

    def set_row_checked(self, row_idx: int, checked: bool):
        """Set checkbox state for a row."""
        if self.has_checkbox and 0 <= row_idx < self.rowCount():
            checkbox = self.cellWidget(row_idx, 0)
            if isinstance(checkbox, QCheckBox):
                blocker = QSignalBlocker(checkbox)
                checkbox.setChecked(checked)
                del blocker

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
