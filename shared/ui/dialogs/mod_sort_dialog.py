"""
Mod sort dialog for reordering mod load order.

Features:
- Drag and drop reordering
- Move up/down/top/bottom buttons
- Auto-sort by priority (built-in framework detection)
- Custom dependency-based sorting (user-defined)
- Dependency count display with tooltip
- Improved wide UI layout
"""

from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QListWidget, QListWidgetItem, QAbstractItemView, QDialogButtonBox,
    QPushButton, QMessageBox, QGroupBox, QSplitter,
    QWidget, QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from shared.utils.locale_manager import tr
from constants.config import MOD_PRIORITY_KEYWORDS, get_mod_priority
from shared.ui.widgets import IconButton


class DependencyPickerDialog(QDialog):
    """Dialog to pick dependencies via multi-select list with search."""

    def __init__(
        self,
        mod_display_name: str,
        candidates: list[tuple[str, str]],
        selected: set[str],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("launcher.set_dependencies"))
        self.setMinimumSize(520, 480)
        self.resize(600, 520)
        self.setModal(True)

        layout = QVBoxLayout(self)

        hint = QLabel(tr("launcher.select_dependencies_hint").format(mod=mod_display_name))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(tr("launcher.search_mods_placeholder"))
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_box)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget, stretch=1)

        # Populate
        for original_name, tooltip in candidates:
            item = QListWidgetItem(original_name)
            item.setData(Qt.UserRole, original_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked if original_name in selected else Qt.Unchecked)
            if tooltip:
                item.setToolTip(tooltip)
            self.list_widget.addItem(item)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._apply_filter()

    def _apply_filter(self, _text: str = ""):
        query = (self.search_box.text() or "").strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            original = (item.data(Qt.UserRole) or "").lower()
            item.setHidden(bool(query) and query not in original)

    def selected_dependencies(self) -> list[str]:
        deps: list[str] = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                deps.append(item.data(Qt.UserRole))
        return deps


class ModSortDialog(QDialog):
    """
    Dialog for sorting mod load order with drag-and-drop support.
    
    Features:
    - Drag and drop reordering
    - Move up/down/top/bottom buttons
    - Auto-sort by priority (framework first)
    - Custom dependency-based sorting
    - Dependency indicators
    """
    
    def __init__(
        self,
        mods_list: list,
        parent=None,
        title_key: str = "launcher.sort_mods_title",
        info_key: str = "launcher.sort_mods_info",
        auto_sort_on_open: bool = False,
        server_path: Optional[Path] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr(title_key))
        self.setMinimumSize(750, 550)
        self.resize(900, 600)
        self.setModal(True)
        
        self._server_path = Path(server_path) if server_path else None
        self._dependency_manager = None
        self._name_manager = None
        self._init_managers()

        if auto_sort_on_open:
            mods_list = sorted(mods_list, key=lambda x: (get_mod_priority(x), x.lower()))

        self._setup_ui(mods_list, info_key)
    
    def _init_managers(self):
        """Initialize dependency and name managers."""
        try:
            from features.mods.core.mod_dependency_manager import ModDependencyManager
            self._dependency_manager = ModDependencyManager(self._server_path)
        except Exception:
            self._dependency_manager = None

        if self._server_path:
            try:
                from features.mods.core.mod_name_manager import ModNameManager
                self._name_manager = ModNameManager(self._server_path)
            except Exception:
                self._name_manager = None
    
    def _setup_ui(self, mods_list: list, info_key: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header with info
        header = QHBoxLayout()
        info_label = QLabel(tr(info_key))
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; padding: 5px;")
        header.addWidget(info_label, stretch=1)
        
        # Mod count
        self.lbl_count = QLabel()
        self.lbl_count.setStyleSheet("color: #4caf50; font-weight: bold;")
        header.addWidget(self.lbl_count)
        layout.addLayout(header)
        
        # Main content with splitter
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left: Mods list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Search/filter
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(tr("launcher.search_mods_placeholder"))
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._apply_filter)
        left_layout.addWidget(self.search_box)
        
        # Mods list with drag-drop
        self.mods_list = QListWidget()
        self.mods_list.setSpacing(2)
        self.mods_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.mods_list.setDefaultDropAction(Qt.MoveAction)
        self.mods_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.mods_list.setStyleSheet("""
            QListWidget { 
                padding: 4px; 
                font-size: 12px;
            }
            QListWidget::item { 
                padding: 8px 12px; 
                border-bottom: 1px solid #333;
            }
            QListWidget::item:selected {
                background-color: #2d5a2d;
            }
        """)
        self.mods_list.itemSelectionChanged.connect(self._on_selection_changed)
        
        self._populate_list(mods_list)
        left_layout.addWidget(self.mods_list)
        main_splitter.addWidget(left_widget)
        
        # Right: Controls
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # Movement buttons
        move_group = QGroupBox(tr("launcher.sort_move_group"))
        move_layout = QVBoxLayout(move_group)
        
        btn_row1 = QHBoxLayout()
        self.btn_top = IconButton("arrow_up", text=tr("launcher.move_to_top"), size=16)
        self.btn_top.clicked.connect(self._move_to_top)
        btn_row1.addWidget(self.btn_top)
        
        self.btn_up = IconButton("arrow_up", text=tr("launcher.move_up"), size=16)
        self.btn_up.clicked.connect(self._move_up)
        btn_row1.addWidget(self.btn_up)
        move_layout.addLayout(btn_row1)
        
        btn_row2 = QHBoxLayout()
        self.btn_down = IconButton("arrow_down", text=tr("launcher.move_down"), size=16)
        self.btn_down.clicked.connect(self._move_down)
        btn_row2.addWidget(self.btn_down)
        
        self.btn_bottom = IconButton("arrow_down", text=tr("launcher.move_to_bottom"), size=16)
        self.btn_bottom.clicked.connect(self._move_to_bottom)
        btn_row2.addWidget(self.btn_bottom)
        move_layout.addLayout(btn_row2)
        
        right_layout.addWidget(move_group)
        
        # Sorting buttons
        sort_group = QGroupBox(tr("launcher.sort_methods"))
        sort_layout = QVBoxLayout(sort_group)
        
        self.btn_auto_sort = QPushButton(tr("launcher.auto_sort"))
        self.btn_auto_sort.setToolTip(tr("launcher.auto_sort_tooltip"))
        self.btn_auto_sort.clicked.connect(self._auto_sort)
        sort_layout.addWidget(self.btn_auto_sort)
        
        self.btn_dep_sort = QPushButton(tr("launcher.sort_by_dependencies"))
        self.btn_dep_sort.setToolTip(tr("launcher.sort_by_dependencies_tooltip"))
        self.btn_dep_sort.clicked.connect(self._sort_by_dependencies)
        self.btn_dep_sort.setEnabled(self._dependency_manager is not None)
        sort_layout.addWidget(self.btn_dep_sort)
        
        right_layout.addWidget(sort_group)
        
        # Dependency management
        dep_group = QGroupBox(tr("launcher.dependencies"))
        dep_layout = QVBoxLayout(dep_group)
        
        self.lbl_dep_info = QLabel(tr("launcher.select_mod_for_deps"))
        self.lbl_dep_info.setWordWrap(True)
        self.lbl_dep_info.setStyleSheet("color: gray; font-size: 11px;")
        dep_layout.addWidget(self.lbl_dep_info)
        
        self.btn_set_deps = QPushButton(tr("launcher.set_dependencies"))
        self.btn_set_deps.setToolTip(tr("launcher.set_dependencies_tooltip"))
        self.btn_set_deps.clicked.connect(self._set_dependencies)
        self.btn_set_deps.setEnabled(False)
        dep_layout.addWidget(self.btn_set_deps)
        
        self.btn_clear_deps = QPushButton(tr("launcher.clear_dependencies"))
        self.btn_clear_deps.clicked.connect(self._clear_dependencies)
        self.btn_clear_deps.setEnabled(False)
        dep_layout.addWidget(self.btn_clear_deps)
        
        right_layout.addWidget(dep_group)
        
        right_layout.addStretch()
        
        # Legend
        legend_frame = QFrame()
        legend_frame.setStyleSheet("QFrame { background-color: rgba(0,0,0,0.1); padding: 8px; }")
        legend_layout = QVBoxLayout(legend_frame)
        legend_layout.setSpacing(4)
        
        legend_title = QLabel(tr("launcher.legend"))
        legend_title.setStyleSheet("font-weight: bold; font-size: 11px;")
        legend_layout.addWidget(legend_title)
        
        legend1 = QLabel(f"🟢 {tr('launcher.priority_legend')}")
        legend1.setStyleSheet("color: #4CAF50; font-size: 10px;")
        legend_layout.addWidget(legend1)
        
        legend2 = QLabel(f"🔗 {tr('launcher.has_dependencies')}")
        legend2.setStyleSheet("color: #2196F3; font-size: 10px;")
        legend_layout.addWidget(legend2)
        
        right_layout.addWidget(legend_frame)
        
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([550, 250])
        
        layout.addWidget(main_splitter, stretch=1)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self._update_count()
    
    def _populate_list(self, mods: list):
        """Populate the list widget with mods."""
        self.mods_list.clear()
        for mod in mods:
            item = self._create_mod_item(mod)
            self.mods_list.addItem(item)
        self._update_count()
    
    def _create_mod_item(self, mod: str) -> QListWidgetItem:
        """Create a list item for a mod with proper styling and tooltip."""
        # Resolve original name if shortened; UI should primarily show original
        original_name = mod
        if self._name_manager:
            original = self._name_manager.get_original_name(mod)
            if original:
                original_name = original
        display_name = original_name
        
        # Get dependency info
        dep_count = 0
        dep_tooltip = ""
        if self._dependency_manager:
            deps = self._dependency_manager.get_dependencies(original_name)
            dep_count = len(deps)
            if deps:
                dep_tooltip = f"\n{tr('launcher.depends_on')}: " + ", ".join(deps)
        
        # Format display text
        if dep_count > 0:
            item_text = f"🔗 {display_name} [{dep_count}]"
        else:
            item_text = display_name
        
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, mod)  # Store actual mod name
        item.setData(Qt.UserRole + 1, original_name)  # Store original name
        item.setData(Qt.UserRole + 2, dep_count)  # Store dep count
        
        # Priority coloring
        priority = get_mod_priority(original_name)
        if priority < len(MOD_PRIORITY_KEYWORDS):
            item.setForeground(QColor("#4CAF50"))
            tooltip = tr("launcher.priority_mod")
        elif dep_count > 0:
            item.setForeground(QColor("#2196F3"))
            tooltip = tr("launcher.has_dependencies_tooltip")
        else:
            tooltip = ""
        
        # Build full tooltip (include underlying folder name if different)
        folder_hint = ""
        if mod != original_name:
            folder_hint = f"\n{tr('launcher.folder_name')}: {mod}"

        full_tooltip = tooltip + dep_tooltip + folder_hint
        if full_tooltip:
            item.setToolTip(full_tooltip.strip())
        
        return item
    
    def _update_count(self):
        """Update mod count label."""
        total = self.mods_list.count()
        visible = 0
        for i in range(total):
            if not self.mods_list.item(i).isHidden():
                visible += 1
        if visible == total:
            self.lbl_count.setText(f"{total} mods")
        else:
            self.lbl_count.setText(f"{visible}/{total} mods")

    def _apply_filter(self, _text: str = ""):
        """Filter list items by original name (case-insensitive)."""
        query = (self.search_box.text() or "").strip().lower()
        for i in range(self.mods_list.count()):
            item = self.mods_list.item(i)
            original = item.data(Qt.UserRole + 1) or item.data(Qt.UserRole) or ""
            text = str(original).lower()
            item.setHidden(bool(query) and query not in text)
        self._update_count()
    
    def _on_selection_changed(self):
        """Handle selection change."""
        selected = self.mods_list.selectedItems()
        single_selection = len(selected) == 1
        
        self.btn_set_deps.setEnabled(single_selection and self._dependency_manager is not None)
        self.btn_clear_deps.setEnabled(single_selection and self._dependency_manager is not None)
        
        if single_selection:
            item = selected[0]
            original_name = item.data(Qt.UserRole + 1) or item.data(Qt.UserRole)
            
            if self._dependency_manager:
                deps = self._dependency_manager.get_dependencies(original_name)
                if deps:
                    self.lbl_dep_info.setText(
                        f"{tr('launcher.current_dependencies')}: {', '.join(deps)}"
                    )
                else:
                    self.lbl_dep_info.setText(tr("launcher.no_dependencies"))
            else:
                self.lbl_dep_info.setText(tr("launcher.deps_not_available"))
        else:
            self.lbl_dep_info.setText(tr("launcher.select_mod_for_deps"))
    
    def _move_up(self):
        """Move selected items up."""
        rows = sorted([self.mods_list.row(item) for item in self.mods_list.selectedItems()])
        if not rows or rows[0] == 0:
            return
        
        for row in rows:
            item = self.mods_list.takeItem(row)
            self.mods_list.insertItem(row - 1, item)
            item.setSelected(True)
    
    def _move_down(self):
        """Move selected items down."""
        rows = sorted([self.mods_list.row(item) for item in self.mods_list.selectedItems()], reverse=True)
        if not rows or rows[-1] == self.mods_list.count() - 1:
            return
        
        for row in rows:
            item = self.mods_list.takeItem(row)
            self.mods_list.insertItem(row + 1, item)
            item.setSelected(True)
    
    def _move_to_top(self):
        """Move selected items to top."""
        selected = self.mods_list.selectedItems()
        if not selected:
            return
        
        rows = sorted([self.mods_list.row(item) for item in selected])
        items = [self.mods_list.takeItem(rows[0]) for _ in rows]
        
        for i, item in enumerate(items):
            self.mods_list.insertItem(i, item)
            item.setSelected(True)
    
    def _move_to_bottom(self):
        """Move selected items to bottom."""
        selected = self.mods_list.selectedItems()
        if not selected:
            return
        
        items_data = [(item.data(Qt.UserRole), item.data(Qt.UserRole + 1)) for item in selected]
        
        for item in selected:
            row = self.mods_list.row(item)
            self.mods_list.takeItem(row)
        
        for mod, original in items_data:
            new_item = self._create_mod_item(mod)
            self.mods_list.addItem(new_item)
            new_item.setSelected(True)
    
    def _auto_sort(self):
        """Auto-sort mods by priority (framework mods first)."""
        mods = [self.mods_list.item(i).data(Qt.UserRole) for i in range(self.mods_list.count())]
        
        def sort_key(mod):
            original = mod
            if self._name_manager:
                orig = self._name_manager.get_original_name(mod)
                if orig:
                    original = orig
            return (get_mod_priority(original), original.lower())
        
        mods.sort(key=sort_key)
        self._populate_list(mods)
    
    def _sort_by_dependencies(self):
        """Sort mods based on user-defined dependencies."""
        if not self._dependency_manager:
            QMessageBox.warning(self, tr("common.warning"), tr("launcher.deps_not_available"))
            return
        
        mods = [self.mods_list.item(i).data(Qt.UserRole) for i in range(self.mods_list.count())]
        
        original_mods = []
        mod_map = {}
        for mod in mods:
            original = mod
            if self._name_manager:
                orig = self._name_manager.get_original_name(mod)
                if orig:
                    original = orig
            original_mods.append(original)
            mod_map[original] = mod
        
        sorted_originals = self._dependency_manager.sort_by_dependencies(original_mods)
        sorted_mods = [mod_map.get(orig, orig) for orig in sorted_originals]
        
        self._populate_list(sorted_mods)
        QMessageBox.information(self, tr("common.info"), tr("launcher.sorted_by_dependencies"))
    
    def _set_dependencies(self):
        """Open dialog to set dependencies for selected mod."""
        selected = self.mods_list.selectedItems()
        if not selected or not self._dependency_manager:
            return
        
        item = selected[0]
        mod_name = item.data(Qt.UserRole)
        original_name = item.data(Qt.UserRole + 1) or mod_name

        # Build candidate list from current list items so we keep original display names.
        candidates: list[tuple[str, str]] = []  # (original_name, tooltip)
        for i in range(self.mods_list.count()):
            other_item = self.mods_list.item(i)
            other_actual = other_item.data(Qt.UserRole)
            other_original = other_item.data(Qt.UserRole + 1) or other_actual

            if other_original == original_name:
                continue

            tooltip = ""
            if other_actual != other_original:
                tooltip = f"{tr('launcher.folder_name')}: {other_actual}"
            candidates.append((other_original, tooltip))

        candidates.sort(key=lambda x: (x[0] or "").lower())

        current_deps = set(self._dependency_manager.get_dependencies(original_name) or [])
        dlg = DependencyPickerDialog(
            mod_display_name=original_name,
            candidates=candidates,
            selected=current_deps,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            deps = dlg.selected_dependencies()
            deps = [d for d in deps if d and d != original_name]
            self._dependency_manager.set_dependencies(original_name, deps)
            self._refresh_item(item)
            self._on_selection_changed()
    
    def _clear_dependencies(self):
        """Clear dependencies for selected mod."""
        selected = self.mods_list.selectedItems()
        if not selected or not self._dependency_manager:
            return
        
        item = selected[0]
        original_name = item.data(Qt.UserRole + 1) or item.data(Qt.UserRole)
        
        self._dependency_manager.set_dependencies(original_name, [])
        self._refresh_item(item)
        self._on_selection_changed()
    
    def _refresh_item(self, item: QListWidgetItem):
        """Refresh a list item with updated data."""
        mod = item.data(Qt.UserRole)
        row = self.mods_list.row(item)
        self.mods_list.takeItem(row)
        new_item = self._create_mod_item(mod)
        self.mods_list.insertItem(row, new_item)
        new_item.setSelected(True)
    
    def get_sorted_mods(self) -> list:
        """Get the current mod order."""
        return [self.mods_list.item(i).data(Qt.UserRole) for i in range(self.mods_list.count())]
