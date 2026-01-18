"""
Mod sort dialog for reordering mod load order.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QAbstractItemView, QDialogButtonBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from src.utils.locale_manager import tr
from src.constants.config import MOD_PRIORITY_KEYWORDS, get_mod_priority
from src.ui.widgets import IconButton


class ModSortDialog(QDialog):
    """
    Dialog for sorting mod load order with drag-and-drop support.
    
    Features:
    - Drag and drop reordering
    - Move up/down buttons
    - Auto-sort by priority
    - Priority mods highlighted in green
    """
    
    def __init__(
        self,
        mods_list: list,
        parent=None,
        title_key: str = "launcher.sort_mods_title",
        info_key: str = "launcher.sort_mods_info",
        auto_sort_on_open: bool = False,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr(title_key))
        self.setMinimumSize(500, 450)
        self.setModal(True)

        if auto_sort_on_open:
            mods_list = sorted(mods_list, key=lambda x: (get_mod_priority(x), x.lower()))

        self._setup_ui(mods_list, info_key)
    
    def _setup_ui(self, mods_list: list, info_key: str):
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(tr(info_key))
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(info_label)
        
        # Main content
        content_layout = QHBoxLayout()
        
        # Mods list with drag-drop
        self.mods_list = QListWidget()
        self.mods_list.setSpacing(4)
        self.mods_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.mods_list.setDefaultDropAction(Qt.MoveAction)
        self.mods_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.mods_list.setStyleSheet(
            "QListWidget { padding: 2px; }"
            "QListWidget::item { padding: 7px 10px; }"
        )
        
        self._populate_list(mods_list)
        content_layout.addWidget(self.mods_list, stretch=1)
        
        # Control buttons
        btn_layout = QVBoxLayout()
        btn_layout.addStretch()
        
        btn_up = IconButton("arrow_up", icon_only=True, size=18)
        btn_up.setFixedWidth(40)
        btn_up.setToolTip(tr("launcher.move_up"))
        btn_up.clicked.connect(self._move_up)
        btn_layout.addWidget(btn_up)
        
        btn_down = IconButton("arrow_down", icon_only=True, size=18)
        btn_down.setFixedWidth(40)
        btn_down.setToolTip(tr("launcher.move_down"))
        btn_down.clicked.connect(self._move_down)
        btn_layout.addWidget(btn_down)
        
        btn_layout.addSpacing(20)
        
        btn_auto = IconButton("sort", icon_only=True, size=18)
        btn_auto.setFixedWidth(40)
        btn_auto.setToolTip(tr("launcher.auto_sort"))
        btn_auto.clicked.connect(self._auto_sort)
        btn_layout.addWidget(btn_auto)
        
        btn_layout.addStretch()
        content_layout.addLayout(btn_layout)
        
        layout.addLayout(content_layout)
        
        # Legend
        legend = QLabel(tr('launcher.priority_legend'))
        legend.setStyleSheet("color: #4CAF50; font-size: 11px;")
        layout.addWidget(legend)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _populate_list(self, mods: list):
        """Populate the list widget with mods."""
        self.mods_list.clear()
        for mod in mods:
            item = QListWidgetItem(mod)
            priority = get_mod_priority(mod)
            if priority < len(MOD_PRIORITY_KEYWORDS):
                item.setForeground(QColor("#4CAF50"))
                item.setToolTip(tr("launcher.priority_mod"))
            self.mods_list.addItem(item)
    
    def _move_up(self):
        """Move selected item up."""
        row = self.mods_list.currentRow()
        if row > 0:
            item = self.mods_list.takeItem(row)
            self.mods_list.insertItem(row - 1, item)
            self.mods_list.setCurrentRow(row - 1)
    
    def _move_down(self):
        """Move selected item down."""
        row = self.mods_list.currentRow()
        if row < self.mods_list.count() - 1:
            item = self.mods_list.takeItem(row)
            self.mods_list.insertItem(row + 1, item)
            self.mods_list.setCurrentRow(row + 1)
    
    def _auto_sort(self):
        """Auto-sort mods by priority."""
        mods = [self.mods_list.item(i).text() for i in range(self.mods_list.count())]
        mods.sort(key=lambda x: (get_mod_priority(x), x.lower()))
        self._populate_list(mods)
    
    def get_sorted_mods(self) -> list:
        """Get the current mod order."""
        return [self.mods_list.item(i).text() for i in range(self.mods_list.count())]
