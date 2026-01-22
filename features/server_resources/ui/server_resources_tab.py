"""
Server Resources Tab - Manages server config files and mission files.
Provides a file browser for:
- config/ folder: Mod configs, log files, etc.
- mpmissions/ folder: Mission files based on selected map
"""

import json
import difflib
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QSpinBox, QCheckBox,
    QTextEdit, QMessageBox, QFileDialog, QComboBox, QScrollArea,
    QFrame, QTabWidget, QSplitter, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QAbstractItemView, QDialog,
    QDialogButtonBox, QPlainTextEdit, QMenu, QInputDialog,
    QApplication, QProgressDialog
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QKeySequence, QShortcut, QTextDocument, QTextCursor

from shared.utils.locale_manager import tr
from shared.core.process_utils import is_dayz_server_running
from shared.ui.icons import Icons
from shared.ui.theme_manager import ThemeManager
from shared.ui.widgets import IconButton


# Only show/edit these file types in Resources tab
EDITABLE_EXTENSIONS = {'.cfg', '.xml', '.json'}

# File type categories for icons and handling
FILE_CATEGORIES = {
    'json': {'extensions': ['.json'], 'icon': 'cog', 'editable': True, 'syntax': 'json'},
    'xml': {'extensions': ['.xml'], 'icon': 'cog', 'editable': True, 'syntax': 'xml'},
    'cfg': {'extensions': ['.cfg'], 'icon': 'settings', 'editable': True, 'syntax': 'cfg'},
}

# Map templates to mission folders
MAP_MISSION_FOLDERS = {
    'dayzOffline.chernarusplus': 'Chernarus',
    'dayzOffline.enoch': 'Livonia', 
    'dayzOffline.sakhal': 'Sakhal',
}


class JsonSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for JSON files."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_formats()
    
    def _setup_formats(self):
        # Key format (blue)
        self.key_format = QTextCharFormat()
        self.key_format.setForeground(QColor("#569cd6"))
        
        # String format (orange)
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#ce9178"))
        
        # Number format (green)
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#b5cea8"))
        
        # Boolean/null format (purple)
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#c586c0"))
        
        # Bracket format
        self.bracket_format = QTextCharFormat()
        self.bracket_format.setForeground(QColor("#d4d4d4"))
    
    def highlightBlock(self, text):
        # Keys
        key_pattern = r'"([^"\\]|\\.)*"\s*:'
        for match in re.finditer(key_pattern, text):
            self.setFormat(match.start(), match.end() - match.start() - 1, self.key_format)
        
        # String values
        string_pattern = r':\s*"([^"\\]|\\.)*"'
        for match in re.finditer(string_pattern, text):
            start = text.find('"', match.start())
            self.setFormat(start, match.end() - start, self.string_format)
        
        # Numbers
        number_pattern = r':\s*-?\d+\.?\d*'
        for match in re.finditer(number_pattern, text):
            start = text.find(match.group().split(':')[1].strip(), match.start())
            self.setFormat(start, len(match.group().split(':')[1].strip()), self.number_format)
        
        # Keywords (true, false, null)
        for keyword in ['true', 'false', 'null']:
            pattern = rf'\b{keyword}\b'
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), self.keyword_format)


class XmlSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for XML files."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_formats()
    
    def _setup_formats(self):
        # Tag format (blue)
        self.tag_format = QTextCharFormat()
        self.tag_format.setForeground(QColor("#569cd6"))
        
        # Attribute name format (cyan)
        self.attr_name_format = QTextCharFormat()
        self.attr_name_format.setForeground(QColor("#9cdcfe"))
        
        # Attribute value format (orange)
        self.attr_value_format = QTextCharFormat()
        self.attr_value_format.setForeground(QColor("#ce9178"))
        
        # Comment format (green)
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#6a9955"))
    
    def highlightBlock(self, text):
        # Tags
        tag_pattern = r'</?[a-zA-Z_][\w\-\.]*'
        for match in re.finditer(tag_pattern, text):
            self.setFormat(match.start(), match.end() - match.start(), self.tag_format)
        
        # Closing brackets
        for match in re.finditer(r'/?>', text):
            self.setFormat(match.start(), match.end() - match.start(), self.tag_format)
        
        # Attribute names
        attr_name_pattern = r'\s([a-zA-Z_][\w\-\.]*)='
        for match in re.finditer(attr_name_pattern, text):
            self.setFormat(match.start() + 1, match.end() - match.start() - 2, self.attr_name_format)
        
        # Attribute values
        attr_value_pattern = r'="([^"]*)"'
        for match in re.finditer(attr_value_pattern, text):
            self.setFormat(match.start() + 1, match.end() - match.start() - 1, self.attr_value_format)
        
        # Comments
        comment_pattern = r'<!--.*?-->'
        for match in re.finditer(comment_pattern, text):
            self.setFormat(match.start(), match.end() - match.start(), self.comment_format)


class FileEditorDialog(QDialog):
    """Dialog for editing config files with syntax highlighting."""
    
    def __init__(self, file_path: Path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.original_content = ""
        self.highlighter = None
        
        self.setWindowTitle(f"{tr('resources.edit_file')}: {file_path.name}")
        self.setMinimumSize(800, 600)
        self.setModal(True)
        
        self._setup_ui()
        self._load_file()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # File info header
        header = QHBoxLayout()
        
        self.lbl_path = QLabel()
        self.lbl_path.setStyleSheet(
            f"color: {ThemeManager.get_accent_color()}; font-size: 12px;"
        )
        header.addWidget(self.lbl_path)
        
        header.addStretch()
        
        self.lbl_size = QLabel()
        self.lbl_size.setStyleSheet("color: gray; font-size: 11px;")
        header.addWidget(self.lbl_size)

        # Fullscreen toggle
        self.btn_fullscreen = IconButton("fullscreen", "", size=16, icon_only=True)
        self.btn_fullscreen.setToolTip(tr("resources.fullscreen"))
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen)
        header.addWidget(self.btn_fullscreen)
        
        layout.addLayout(header)
        
        # Find bar (hidden by default)
        self.find_bar = QFrame()
        self.find_bar.setObjectName("findBar")
        self.find_bar.setStyleSheet(
            "QFrame#findBar { background: rgba(0,0,0,0.06); border: 1px solid rgba(0,0,0,0.12); border-radius: 4px; }"
        )
        find_layout = QHBoxLayout(self.find_bar)
        find_layout.setContentsMargins(8, 6, 8, 6)

        find_layout.addWidget(QLabel(tr("resources.find")))
        self.txt_find = QLineEdit()
        self.txt_find.setPlaceholderText(tr("resources.find_placeholder"))
        self.txt_find.textChanged.connect(lambda _t: self._update_search_highlights())
        self.txt_find.returnPressed.connect(self._find_next)
        find_layout.addWidget(self.txt_find, stretch=1)

        self.chk_case = QCheckBox(tr("resources.case_toggle"))
        self.chk_case.setToolTip(tr("resources.case_sensitive"))
        self.chk_case.stateChanged.connect(lambda _s: self._update_search_highlights())
        find_layout.addWidget(self.chk_case)

        self.btn_find_prev = QPushButton(tr("resources.find_prev"))
        self.btn_find_prev.clicked.connect(self._find_prev)
        find_layout.addWidget(self.btn_find_prev)

        self.btn_find_next = QPushButton(tr("resources.find_next"))
        self.btn_find_next.clicked.connect(self._find_next)
        find_layout.addWidget(self.btn_find_next)

        self.lbl_find_status = QLabel("")
        self.lbl_find_status.setStyleSheet("color: gray;")
        find_layout.addWidget(self.lbl_find_status)

        self.btn_find_close = QPushButton("✕")
        self.btn_find_close.setFixedWidth(32)
        self.btn_find_close.clicked.connect(self._hide_find)
        find_layout.addWidget(self.btn_find_close)

        self.find_bar.setVisible(False)
        layout.addWidget(self.find_bar)

        # Editor
        self.editor = QPlainTextEdit()
        font = QFont("Consolas", 10)
        self.editor.setFont(font)
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.setTabStopDistance(40)
        layout.addWidget(self.editor)
        
        # Status bar
        status_layout = QHBoxLayout()
        self.lbl_status = QLabel()
        status_layout.addWidget(self.lbl_status)
        status_layout.addStretch()
        
        # Line/column indicator
        self.lbl_position = QLabel(tr("resources.position").format(line=1, col=1))
        self.lbl_position.setStyleSheet("color: gray;")
        status_layout.addWidget(self.lbl_position)
        
        layout.addLayout(status_layout)
        
        # Connect cursor position
        self.editor.cursorPositionChanged.connect(self._update_position)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.textChanged.connect(lambda: self._update_search_highlights() if self.find_bar.isVisible() else None)

        # Search highlight state
        self._search_highlight_format = QTextCharFormat()
        self._search_highlight_format.setBackground(QColor(255, 235, 59, 100))

        # Shortcuts
        self.shortcut_find = QShortcut(QKeySequence.Find, self)
        self.shortcut_find.activated.connect(self._show_find)
        self.shortcut_find_next = QShortcut(QKeySequence.FindNext, self)
        self.shortcut_find_next.activated.connect(self._find_next)
        self.shortcut_find_prev = QShortcut(QKeySequence.FindPrevious, self)
        self.shortcut_find_prev.activated.connect(self._find_prev)
        self.shortcut_goto = QShortcut(QKeySequence("Ctrl+G"), self)
        self.shortcut_goto.activated.connect(self._goto_line)
        self.shortcut_fullscreen = QShortcut(QKeySequence("F11"), self)
        self.shortcut_fullscreen.activated.connect(self._toggle_fullscreen)
        self.shortcut_escape = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.shortcut_escape.activated.connect(self._hide_find)
        
        # Buttons
        button_box = QDialogButtonBox()
        
        btn_format = QPushButton(tr("resources.format"))
        btn_format.clicked.connect(self._format_content)
        button_box.addButton(btn_format, QDialogButtonBox.ActionRole)
        
        button_box.addButton(QDialogButtonBox.Save)
        button_box.addButton(QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._save_and_close)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
    
    def _load_file(self):
        """Load file content."""
        try:
            self.original_content = self.file_path.read_text(encoding='utf-8')
            self.editor.setPlainText(self.original_content)
            
            self.lbl_path.setText(str(self.file_path))
            size = self.file_path.stat().st_size
            self.lbl_size.setText(self._format_size(size))
            
            # Apply syntax highlighting based on extension
            ext = self.file_path.suffix.lower()
            if ext == '.json':
                self.highlighter = JsonSyntaxHighlighter(self.editor.document())
            elif ext == '.xml':
                self.highlighter = XmlSyntaxHighlighter(self.editor.document())
            
            self.lbl_status.setText(tr("resources.file_loaded"))
            
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))
            self.reject()
    
    def _format_size(self, size: int) -> str:
        """Format file size."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.2f} MB"
    
    def _update_position(self):
        """Update line/column indicator."""
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self.lbl_position.setText(tr("resources.position").format(line=line, col=col))
    
    def _on_text_changed(self):
        """Handle text changes."""
        if self.editor.toPlainText() != self.original_content:
            self.lbl_status.setText(f"* {tr('resources.modified')}")
        else:
            self.lbl_status.setText(tr("resources.file_loaded"))
    
    def _format_content(self):
        """Format JSON/XML content."""
        ext = self.file_path.suffix.lower()
        content = self.editor.toPlainText()
        
        try:
            if ext == '.json':
                data = json.loads(content)
                formatted = json.dumps(data, indent=4, ensure_ascii=False)
                self.editor.setPlainText(formatted)
                self.lbl_status.setText(tr("resources.formatted"))
            elif ext == '.xml':
                # Basic XML formatting
                import xml.dom.minidom as minidom
                dom = minidom.parseString(content.encode('utf-8'))
                formatted = dom.toprettyxml(indent="    ")
                # Remove extra blank lines
                formatted = '\n'.join(line for line in formatted.split('\n') if line.strip())
                self.editor.setPlainText(formatted)
                self.lbl_status.setText(tr("resources.formatted"))
            else:
                self.lbl_status.setText(tr("resources.format_not_supported"))
        except Exception as e:
            QMessageBox.warning(self, tr("common.warning"), f"{tr('resources.format_error')}: {e}")
    
    def _save_and_close(self):
        """Save file and close dialog."""
        try:
            if self.file_path.name.lower() == "serverdz.cfg" and is_dayz_server_running():
                QMessageBox.warning(self, tr("common.warning"), tr("dialogs.server_running_save_blocked"))
                return
            content = self.editor.toPlainText()

            if content == self.original_content:
                self.accept()
                return
            
            # Validate JSON if applicable
            if self.file_path.suffix.lower() == '.json':
                json.loads(content)  # Validate

            preview = TextDiffPreviewDialog(
                original_text=self.original_content,
                updated_text=content,
                title=f"{tr('resources.preview_changes')}: {self.file_path.name}",
                parent=self,
            )
            if preview.exec() != QDialog.Accepted:
                return

            # Create backup
            backup_path = self.file_path.with_suffix(self.file_path.suffix + '.bak')
            if self.file_path.exists():
                backup_path.write_text(self.original_content, encoding='utf-8')

            # Save file
            self.file_path.write_text(content, encoding='utf-8')
            self.accept()
            
        except json.JSONDecodeError as e:
            QMessageBox.warning(
                self, 
                tr("common.warning"), 
                f"{tr('resources.invalid_json')}: {e}"
            )
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))

    def _show_find(self):
        """Show find bar and focus the search box."""
        self.find_bar.setVisible(True)
        selected = self.editor.textCursor().selectedText()
        if selected:
            self.txt_find.setText(selected)
        self.txt_find.selectAll()
        self.txt_find.setFocus()
        self.lbl_find_status.setText("")
        self._update_search_highlights()

    def _hide_find(self):
        if self.find_bar.isVisible():
            self.find_bar.setVisible(False)
            self._clear_search_highlights()
            self.editor.setFocus()

    def _clear_search_highlights(self):
        self.editor.setExtraSelections([])

    def _update_search_highlights(self):
        """Highlight all matches of the current search text."""
        text = self.txt_find.text()
        if not self.find_bar.isVisible() or not text:
            self._clear_search_highlights()
            return

        flags = QTextDocument.FindFlags()
        if self.chk_case.isChecked():
            flags |= QTextDocument.FindCaseSensitively

        doc = self.editor.document()
        cursor = QTextCursor(doc)
        selections = []

        # Collect all matches
        while True:
            cursor = doc.find(text, cursor, flags)
            if cursor.isNull():
                break
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = self._search_highlight_format
            selections.append(sel)

        self.editor.setExtraSelections(selections)

    def _find_flags(self, backwards: bool = False) -> QTextDocument.FindFlags:
        flags = QTextDocument.FindFlags()
        if backwards:
            flags |= QTextDocument.FindBackward
        if self.chk_case.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        return flags

    def _find_next(self):
        text = self.txt_find.text()
        if not text:
            self.lbl_find_status.setText("")
            return

        found = self.editor.find(text, self._find_flags(backwards=False))
        if not found:
            # Wrap-around
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.editor.setTextCursor(cursor)
            found = self.editor.find(text, self._find_flags(backwards=False))

        self.lbl_find_status.setText("" if found else "Not found")
        self._update_search_highlights()

    def _find_prev(self):
        text = self.txt_find.text()
        if not text:
            self.lbl_find_status.setText("")
            return

        found = self.editor.find(text, self._find_flags(backwards=True))
        if not found:
            # Wrap-around
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.editor.setTextCursor(cursor)
            found = self.editor.find(text, self._find_flags(backwards=True))

        self.lbl_find_status.setText("" if found else "Not found")
        self._update_search_highlights()

    def _toggle_fullscreen(self):
        """Toggle fullscreen/maximized for focus (F11)."""
        try:
            if self.isFullScreen() or self.isMaximized():
                self.showNormal()
                self.btn_fullscreen.set_icon("fullscreen")
                self.btn_fullscreen.setToolTip(tr("resources.fullscreen"))
            else:
                self.showFullScreen()
                self.btn_fullscreen.set_icon("fullscreen_exit")
                self.btn_fullscreen.setToolTip(tr("resources.exit_fullscreen"))
        except Exception:
            return

    def _goto_line(self):
        """Go to line number (Ctrl+G)."""
        try:
            total_lines = self.editor.blockCount()
            line, ok = QInputDialog.getInt(
                self,
                tr("resources.goto_line"),
                tr("resources.goto_line_prompt"),
                1,
                1,
                max(1, total_lines),
                1,
            )
            if not ok:
                return

            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.MoveAnchor, line - 1)
            self.editor.setTextCursor(cursor)
            self.editor.setFocus()
        except Exception:
            return


class TextDiffPreviewDialog(QDialog):
    """Preview text changes as a unified diff before saving."""

    def __init__(self, original_text: str, updated_text: str, title: str, parent=None):
        super().__init__(parent)
        self._original = original_text
        self._updated = updated_text

        self.setWindowTitle(title)
        self.setMinimumSize(900, 650)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(f"<h3>{tr('resources.preview_changes')}</h3>")
        layout.addWidget(header)

        tabs = QTabWidget()

        diff_text = "\n".join(
            difflib.unified_diff(
                self._original.splitlines(),
                self._updated.splitlines(),
                fromfile=tr('resources.original'),
                tofile=tr('resources.updated'),
                lineterm="",
            )
        ).strip()
        if not diff_text:
            diff_text = tr("resources.no_changes")

        diff_view = QPlainTextEdit()
        diff_view.setReadOnly(True)
        diff_view.setFont(QFont("Consolas", 10))
        diff_view.setPlainText(diff_text)
        tabs.addTab(diff_view, tr("resources.diff"))

        original_view = QPlainTextEdit()
        original_view.setReadOnly(True)
        original_view.setFont(QFont("Consolas", 10))
        original_view.setPlainText(self._original)
        tabs.addTab(original_view, tr("resources.original"))

        updated_view = QPlainTextEdit()
        updated_view.setReadOnly(True)
        updated_view.setFont(QFont("Consolas", 10))
        updated_view.setPlainText(self._updated)
        tabs.addTab(updated_view, tr("resources.updated"))

        layout.addWidget(tabs)

        button_box = QDialogButtonBox()
        btn_save = QPushButton(tr("common.save"))
        btn_save.setObjectName("primary")
        button_box.addButton(btn_save, QDialogButtonBox.AcceptRole)

        btn_cancel = QPushButton(tr("common.cancel"))
        button_box.addButton(btn_cancel, QDialogButtonBox.RejectRole)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class ResourcesBrowserWidget(QWidget):
    """Reusable file browser+preview+editor for a single root folder."""

    resources_changed = Signal()

    def __init__(self, parent=None, preset_scope: str = "mods"):
        super().__init__(parent)
        self._root_path: Optional[Path] = None
        self._profile_data: Optional[Dict] = None
        self._preset_manager = None
        self._preset_scope = preset_scope

        self._setup_ui()
    
    def set_profile(self, profile_data: dict):
        """Set the current profile for preset management."""
        self._profile_data = profile_data
        if profile_data:
            from features.config.core.config_preset_manager import ConfigPresetManager
            self._preset_manager = ConfigPresetManager(profile_data, scope=self._preset_scope)
        else:
            self._preset_manager = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Root path indicator
        header = QHBoxLayout()
        self.lbl_root = QLabel("")
        self.lbl_root.setStyleSheet(
            f"color: {ThemeManager.get_accent_color()}; font-size: 12px;"
        )
        header.addWidget(self.lbl_root)
        header.addStretch()
        
        # === Config Presets buttons (for all configs) ===
        self.btn_save_all_default = IconButton("save", tr("presets.save_as_default"), size=14)
        self.btn_save_all_default.setToolTip(tr("presets.save_all_as_default_tooltip"))
        self.btn_save_all_default.clicked.connect(self._save_all_as_default)
        header.addWidget(self.btn_save_all_default)
        
        self.btn_save_all_preset = IconButton("bookmark", tr("presets.save_config_presets"), size=14)
        self.btn_save_all_preset.setToolTip(tr("presets.save_all_preset_tooltip"))
        self.btn_save_all_preset.clicked.connect(self._save_all_preset)
        header.addWidget(self.btn_save_all_preset)
        
        self.btn_load_all_preset = IconButton("download", tr("presets.load_config_presets"), size=14)
        self.btn_load_all_preset.setToolTip(tr("presets.load_all_preset_tooltip"))
        self.btn_load_all_preset.clicked.connect(self._load_all_preset)
        header.addWidget(self.btn_load_all_preset)
        
        self.btn_restore_all_default = IconButton("undo", tr("presets.restore_default"), size=14)
        self.btn_restore_all_default.setToolTip(tr("presets.restore_all_default_tooltip"))
        self.btn_restore_all_default.clicked.connect(self._restore_all_default)
        header.addWidget(self.btn_restore_all_default)

        self.btn_refresh = IconButton("refresh", tr("common.refresh"), size=14)
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)

        # Left panel: search/filter + tree
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        search_layout = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(tr("common.search"))
        self.txt_search.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self.txt_search)

        self.cmb_filter = QComboBox()
        self.cmb_filter.addItem(tr("resources.filter_all"), "all")
        self.cmb_filter.addItem(tr("resources.filter_json"), "json")
        self.cmb_filter.addItem(tr("resources.filter_xml"), "xml")
        self.cmb_filter.addItem(tr("resources.filter_cfg"), "cfg")
        self.cmb_filter.currentIndexChanged.connect(self._apply_filter)
        search_layout.addWidget(self.cmb_filter)
        left_layout.addLayout(search_layout)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("resources.name"), tr("resources.size"), tr("resources.modified")])
        self.tree.setColumnWidth(0, 250)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 150)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.tree)

        splitter.addWidget(left_panel)

        # Right panel: preview
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        preview_header = QHBoxLayout()
        self.lbl_preview = QLabel(tr("resources.preview"))
        self.lbl_preview.setStyleSheet("font-weight: bold;")
        preview_header.addWidget(self.lbl_preview)
        
        # Preset indicator for selected file
        self.lbl_preset_indicator = QLabel()
        self.lbl_preset_indicator.setStyleSheet("color: #4caf50; font-size: 11px;")
        preview_header.addWidget(self.lbl_preset_indicator)
        
        preview_header.addStretch()
        
        # === File-specific preset buttons ===
        self.btn_file_save_default = IconButton("save", "", size=14, icon_only=True)
        self.btn_file_save_default.setToolTip(tr("presets.save_as_default"))
        self.btn_file_save_default.clicked.connect(self._save_file_as_default)
        self.btn_file_save_default.setEnabled(False)
        preview_header.addWidget(self.btn_file_save_default)
        
        self.btn_file_save_preset = IconButton("bookmark", "", size=14, icon_only=True)
        self.btn_file_save_preset.setToolTip(tr("presets.save_preset"))
        self.btn_file_save_preset.clicked.connect(self._save_file_preset)
        self.btn_file_save_preset.setEnabled(False)
        preview_header.addWidget(self.btn_file_save_preset)
        
        self.btn_file_load_preset = IconButton("download", "", size=14, icon_only=True)
        self.btn_file_load_preset.setToolTip(tr("presets.load_preset"))
        self.btn_file_load_preset.clicked.connect(self._load_file_preset)
        self.btn_file_load_preset.setEnabled(False)
        preview_header.addWidget(self.btn_file_load_preset)
        
        self.btn_file_restore_default = IconButton("undo", "", size=14, icon_only=True)
        self.btn_file_restore_default.setToolTip(tr("presets.restore_default"))
        self.btn_file_restore_default.clicked.connect(self._restore_file_default)
        self.btn_file_restore_default.setEnabled(False)
        preview_header.addWidget(self.btn_file_restore_default)

        self.btn_edit = IconButton("edit", tr("common.edit"), size=14)
        self.btn_edit.clicked.connect(self._edit_selected)
        self.btn_edit.setEnabled(False)
        preview_header.addWidget(self.btn_edit)
        right_layout.addLayout(preview_header)

        self.txt_preview = QPlainTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setFont(QFont("Consolas", 10))
        right_layout.addWidget(self.txt_preview)

        splitter.addWidget(right_panel)
        splitter.setSizes([400, 400])

        layout.addWidget(splitter)

        self._set_enabled(False)

    def update_texts(self):
        self.btn_refresh.setText(tr("common.refresh"))
        self.txt_search.setPlaceholderText(tr("common.search"))
        self.cmb_filter.setItemText(0, tr("resources.filter_all"))
        self.cmb_filter.setItemText(1, tr("resources.filter_json"))
        self.cmb_filter.setItemText(2, tr("resources.filter_xml"))
        self.cmb_filter.setItemText(3, tr("resources.filter_cfg"))
        self.tree.setHeaderLabels([tr("resources.name"), tr("resources.size"), tr("resources.modified")])
        self.lbl_preview.setText(tr("resources.preview"))
        self.btn_edit.setText(tr("common.edit"))
        
        # Update preset button texts and tooltips
        self.btn_save_all_default.setText(tr("presets.save_as_default"))
        self.btn_save_all_default.setToolTip(tr("presets.save_all_as_default_tooltip"))
        self.btn_save_all_preset.setText(tr("presets.save_config_presets"))
        self.btn_save_all_preset.setToolTip(tr("presets.save_all_preset_tooltip"))
        self.btn_load_all_preset.setText(tr("presets.load_config_presets"))
        self.btn_load_all_preset.setToolTip(tr("presets.load_all_preset_tooltip"))
        self.btn_restore_all_default.setText(tr("presets.restore_default"))
        self.btn_restore_all_default.setToolTip(tr("presets.restore_all_default_tooltip"))
        
        self.btn_file_save_default.setToolTip(tr("presets.save_as_default"))
        self.btn_file_save_preset.setToolTip(tr("presets.save_preset"))
        self.btn_file_load_preset.setToolTip(tr("presets.load_preset"))
        self.btn_file_restore_default.setToolTip(tr("presets.restore_default"))

    def set_root_path(self, root_path: Optional[Path]):
        self._root_path = root_path
        self.lbl_root.setText(str(root_path) if root_path else "")
        self.refresh()

    def refresh(self):
        self.tree.clear()
        self.txt_preview.clear()
        self.btn_edit.setEnabled(False)
        self._set_file_preset_buttons_enabled(False)
        self.lbl_preset_indicator.clear()

        if not self._root_path or not self._root_path.exists():
            self._set_enabled(False)
            return

        self._set_enabled(True)
        self._populate_tree(self.tree, self._root_path)
        self.tree.expandToDepth(0)
        self._apply_filter()
        
        # Update preset indicators in tree
        self._update_tree_preset_indicators()

    def _set_enabled(self, enabled: bool):
        self.txt_search.setEnabled(enabled)
        self.cmb_filter.setEnabled(enabled)
        self.tree.setEnabled(enabled)
        self.btn_refresh.setEnabled(enabled)

    def _get_file_category(self, extension: str) -> str:
        for category, info in FILE_CATEGORIES.items():
            if extension in info["extensions"]:
                return category
        return ""

    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.2f} MB"

    def _populate_tree(self, tree: QTreeWidget, current_path: Path, parent_item: Optional[QTreeWidgetItem] = None) -> bool:
        try:
            items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return False
        except Exception:
            return False

        has_visible = False

        for item in items:
            if item.name.startswith(".") or not item.is_dir():
                continue

            folder_item = QTreeWidgetItem()
            folder_item.setText(0, item.name)
            folder_item.setData(0, Qt.UserRole, str(item))
            folder_item.setIcon(0, Icons.get_icon("folder"))
            folder_item.setText(1, "")
            folder_item.setText(2, "")

            child_has_visible = self._populate_tree(tree, item, folder_item)
            if not child_has_visible:
                continue

            if parent_item is not None:
                parent_item.addChild(folder_item)
            else:
                tree.addTopLevelItem(folder_item)
            has_visible = True

        for item in items:
            if item.name.startswith(".") or not item.is_file():
                continue
            if item.suffix.lower() not in EDITABLE_EXTENSIONS:
                continue

            file_item = QTreeWidgetItem()
            file_item.setText(0, item.name)
            file_item.setData(0, Qt.UserRole, str(item))

            category = self._get_file_category(item.suffix.lower())
            icon_name = FILE_CATEGORIES.get(category, {}).get("icon", "edit")
            file_item.setIcon(0, Icons.get_icon(icon_name))

            try:
                size = item.stat().st_size
                file_item.setText(1, self._format_size(size))
            except Exception:
                file_item.setText(1, "")

            try:
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                file_item.setText(2, mtime.strftime("%Y-%m-%d %H:%M"))
            except Exception:
                file_item.setText(2, "")

            if parent_item is not None:
                parent_item.addChild(file_item)
            else:
                tree.addTopLevelItem(file_item)
            has_visible = True

        return has_visible

    def _apply_filter(self):
        search_text = self.txt_search.text().lower()
        filter_type = self.cmb_filter.currentData()

        def filter_item(item: QTreeWidgetItem) -> bool:
            node_path = Path(item.data(0, Qt.UserRole))
            name = item.text(0).lower()

            if node_path.is_dir():
                any_child_visible = False
                for i in range(item.childCount()):
                    if filter_item(item.child(i)):
                        any_child_visible = True

                visible = any_child_visible
                if search_text:
                    visible = (search_text in name) or any_child_visible
                item.setHidden(not visible)
                return visible

            matches_search = (not search_text) or (search_text in name)
            category = self._get_file_category(node_path.suffix.lower())
            matches_type = (filter_type == "all") or (category == filter_type)
            visible = matches_search and matches_type
            item.setHidden(not visible)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            filter_item(self.tree.topLevelItem(i))

    def _on_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            self.txt_preview.clear()
            self.btn_edit.setEnabled(False)
            self._set_file_preset_buttons_enabled(False)
            self.lbl_preset_indicator.clear()
            return

        item = items[0]
        file_path = Path(item.data(0, Qt.UserRole))
        if file_path.is_file():
            self._preview_file(file_path)
            is_editable = file_path.suffix.lower() in EDITABLE_EXTENSIONS
            self.btn_edit.setEnabled(is_editable)
            self._set_file_preset_buttons_enabled(is_editable and self._preset_manager is not None)
            self._update_preset_indicator(file_path)
            return

        self.txt_preview.clear()
        self.btn_edit.setEnabled(False)
        self._set_file_preset_buttons_enabled(False)
        self.lbl_preset_indicator.clear()
    
    def _set_file_preset_buttons_enabled(self, enabled: bool):
        """Enable/disable file-specific preset buttons."""
        self.btn_file_save_default.setEnabled(enabled)
        self.btn_file_save_preset.setEnabled(enabled)
        self.btn_file_load_preset.setEnabled(enabled)
        self.btn_file_restore_default.setEnabled(enabled)
    
    def _update_preset_indicator(self, file_path: Path):
        """Update the preset indicator for the selected file."""
        if not self._preset_manager:
            self.lbl_preset_indicator.clear()
            return
        
        has_default = self._preset_manager.has_default(file_path)
        preset_count = self._preset_manager.get_preset_count_all_profiles(file_path)
        
        indicators = []
        if has_default:
            indicators.append(f"✓ {tr('presets.has_default')}")
        if preset_count > 0:
            indicators.append(f"📑 {preset_count} {tr('presets.presets')}")
        
        if indicators:
            self.lbl_preset_indicator.setText(" | ".join(indicators))
        else:
            self.lbl_preset_indicator.clear()

    def _preview_file(self, file_path: Path):
        try:
            max_size = 500 * 1024
            size = file_path.stat().st_size
            if size > max_size:
                self.txt_preview.setPlainText(
                    f"[{tr('resources.file_too_large')}]\n\n{tr('resources.size')}: {self._format_size(size)}"
                )
                return

            content = file_path.read_text(encoding="utf-8", errors="replace")

            max_lines = 1000
            lines = content.split("\n")
            if len(lines) > max_lines:
                content = "\n".join(lines[:max_lines])
                content += f"\n\n... [{tr('resources.truncated')} {len(lines) - max_lines} {tr('resources.lines')}]"

            self.txt_preview.setPlainText(content)
        except Exception as e:
            self.txt_preview.setPlainText(f"[{tr('common.error')}]\n{e}")

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        file_path = Path(item.data(0, Qt.UserRole))
        if file_path.is_file() and file_path.suffix.lower() in EDITABLE_EXTENSIONS:
            self._edit_file(file_path)

    def _edit_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return
        file_path = Path(items[0].data(0, Qt.UserRole))
        if file_path.is_file() and file_path.suffix.lower() in EDITABLE_EXTENSIONS:
            self._edit_file(file_path)

    def _edit_file(self, file_path: Path):
        dialog = FileEditorDialog(file_path, self)
        if dialog.exec() == QDialog.Accepted:
            self._on_selection_changed()
            self.resources_changed.emit()

    def _show_context_menu(self, position):
        item = self.tree.itemAt(position)
        if not item:
            return

        file_path = Path(item.data(0, Qt.UserRole))
        menu = QMenu(self)

        if file_path.is_file():
            if file_path.suffix.lower() in EDITABLE_EXTENSIONS:
                action_edit = menu.addAction(Icons.get_icon("edit"), tr("common.edit"))
                action_edit.triggered.connect(lambda: self._edit_file(file_path))

            action_view = menu.addAction(Icons.get_icon("browse"), tr("resources.open_folder"))
            action_view.triggered.connect(lambda: self._open_containing_folder(file_path))

            menu.addSeparator()

            action_copy_path = menu.addAction(Icons.get_icon("copy"), tr("resources.copy_path"))
            action_copy_path.triggered.connect(lambda: self._copy_path_to_clipboard(file_path))

            action_backup = menu.addAction(Icons.get_icon("save"), tr("resources.create_backup"))
            action_backup.triggered.connect(lambda: self._create_backup(file_path))
            
            # Preset actions for editable files
            if file_path.suffix.lower() in EDITABLE_EXTENSIONS and self._preset_manager:
                menu.addSeparator()
                
                # Save as default
                action_save_default = menu.addAction(Icons.get_icon("save"), tr("presets.save_as_default"))
                action_save_default.triggered.connect(self._save_file_as_default)
                
                # Save preset
                action_save_preset = menu.addAction(Icons.get_icon("bookmark"), tr("presets.save_preset"))
                action_save_preset.triggered.connect(self._save_file_preset)
                
                # Load preset (if presets exist)
                presets = self._preset_manager.get_presets(file_path)
                if presets:
                    action_load_preset = menu.addAction(Icons.get_icon("download"), tr("presets.load_preset"))
                    action_load_preset.triggered.connect(self._load_file_preset)
                
                # Restore default (if default exists)
                if self._preset_manager.has_default(file_path):
                    action_restore = menu.addAction(Icons.get_icon("undo"), tr("presets.restore_default"))
                    action_restore.triggered.connect(self._restore_file_default)
        else:
            action_open = menu.addAction(Icons.get_icon("folder"), tr("resources.open_folder"))
            action_open.triggered.connect(lambda: self._open_folder(file_path))

            action_copy_path = menu.addAction(Icons.get_icon("copy"), tr("resources.copy_path"))
            action_copy_path.triggered.connect(lambda: self._copy_path_to_clipboard(file_path))

        menu.exec(self.tree.viewport().mapToGlobal(position))

    def _open_containing_folder(self, file_path: Path):
        import subprocess
        subprocess.run(["explorer", "/select,", str(file_path)])

    def _open_folder(self, folder_path: Path):
        import subprocess
        subprocess.run(["explorer", str(folder_path)])

    def _copy_path_to_clipboard(self, path: Path):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(str(path))

    def _create_backup(self, file_path: Path):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.stem}_backup_{timestamp}{file_path.suffix}"
            backup_path = file_path.parent / backup_name

            import shutil
            shutil.copy2(file_path, backup_path)

            QMessageBox.information(
                self,
                tr("common.success"),
                f"{tr('resources.backup_created')}: {backup_name}",
            )
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))

    # ==================== Preset Operations ====================
    
    def _get_all_config_files(self) -> List[Path]:
        """Get all editable config files in the tree."""
        files = []
        
        def collect_files(item: QTreeWidgetItem):
            path = Path(item.data(0, Qt.UserRole))
            if path.is_file() and path.suffix.lower() in EDITABLE_EXTENSIONS:
                files.append(path)
            for i in range(item.childCount()):
                collect_files(item.child(i))
        
        for i in range(self.tree.topLevelItemCount()):
            collect_files(self.tree.topLevelItem(i))
        
        return files
    
    def _get_selected_file(self) -> Optional[Path]:
        """Get the currently selected file."""
        items = self.tree.selectedItems()
        if not items:
            return None
        file_path = Path(items[0].data(0, Qt.UserRole))
        if file_path.is_file():
            return file_path
        return None
    
    # --- File-specific preset operations ---
    
    def _save_file_as_default(self):
        """Save current file as default."""
        file_path = self._get_selected_file()
        if not file_path or not self._preset_manager:
            return
        
        if self._preset_manager.save_as_default(file_path):
            QMessageBox.information(
                self, tr("common.success"),
                tr("presets.saved_as_default").format(file=file_path.name)
            )
            self._update_preset_indicator(file_path)
            self._update_tree_preset_indicators()
        else:
            QMessageBox.warning(self, tr("common.error"), tr("presets.save_failed"))
    
    def _save_file_preset(self):
        """Save current file as named preset."""
        file_path = self._get_selected_file()
        if not file_path or not self._preset_manager:
            return
        
        existing_names = [p.name for p in self._preset_manager.get_presets(file_path)]
        
        from shared.ui.dialogs.config_preset_dialog import SavePresetDialog
        dialog = SavePresetDialog(existing_names, self)
        if dialog.exec() == QDialog.Accepted:
            if self._preset_manager.save_preset(file_path, dialog.preset_name, dialog.description):
                QMessageBox.information(
                    self, tr("common.success"),
                    tr("presets.preset_saved").format(name=dialog.preset_name)
                )
                self._update_preset_indicator(file_path)
                self._update_tree_preset_indicators()
            else:
                QMessageBox.warning(self, tr("common.error"), tr("presets.save_failed"))
    
    def _load_file_preset(self):
        """Load a preset for current file."""
        file_path = self._get_selected_file()
        if not file_path or not self._preset_manager:
            return

        preset_options = self._preset_manager.get_preset_options(file_path, include_other_profiles=True)
        if not preset_options:
            QMessageBox.information(
                self, tr("common.info"),
                tr("presets.no_presets_available")
            )
            return

        from shared.ui.dialogs.config_preset_dialog import LoadPresetDialog

        def content_loader(profile_name: str, preset_name: str) -> Optional[str]:
            return self._preset_manager.read_preset_content(file_path, preset_name, source_profile=profile_name)

        dialog = LoadPresetDialog(
            preset_options=preset_options,
            content_loader=content_loader,
            current_profile_name=self._preset_manager.profile_name,
            parent=self,
        )
        
        # Handle delete signal
        def on_preset_action(action: str):
            if action.startswith("DELETE:"):
                preset_name = action[7:]
                self._preset_manager.delete_preset(file_path, preset_name)
        
        dialog.preset_selected.connect(on_preset_action)
        
        if dialog.exec() == QDialog.Accepted and dialog.selected_preset_name:
            if self._preset_manager.load_preset(
                file_path,
                dialog.selected_preset_name,
                source_profile=dialog.selected_profile_name,
            ):
                QMessageBox.information(
                    self, tr("common.success"),
                    tr("presets.preset_loaded").format(name=dialog.selected_preset_name)
                )
                self._on_selection_changed()  # Refresh preview
                self.resources_changed.emit()
            else:
                QMessageBox.warning(self, tr("common.error"), tr("presets.load_failed"))
    
    def _restore_file_default(self):
        """Restore current file from default."""
        file_path = self._get_selected_file()
        if not file_path or not self._preset_manager:
            return
        
        if not self._preset_manager.has_default(file_path):
            QMessageBox.information(
                self, tr("common.info"),
                tr("presets.no_default_saved")
            )
            return
        
        reply = QMessageBox.question(
            self, tr("common.confirm"),
            tr("presets.confirm_restore").format(file=file_path.name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self._preset_manager.restore_default(file_path):
                QMessageBox.information(
                    self, tr("common.success"),
                    tr("presets.restored_from_default").format(file=file_path.name)
                )
                self._on_selection_changed()  # Refresh preview
                self.resources_changed.emit()
            else:
                QMessageBox.warning(self, tr("common.error"), tr("presets.restore_failed"))
    
    # --- Bulk preset operations ---
    
    def _save_all_as_default(self):
        """Save all config files as defaults."""
        if not self._preset_manager:
            QMessageBox.warning(self, tr("common.warning"), tr("presets.no_profile_selected"))
            return
        
        files = self._get_all_config_files()
        if not files:
            QMessageBox.information(self, tr("common.info"), tr("presets.no_config_files"))
            return
        
        reply = QMessageBox.question(
            self, tr("common.confirm"),
            tr("presets.confirm_save_all_default").format(count=len(files)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            progress = QProgressDialog(tr("common.loading"), tr("common.cancel"), 0, len(files), self)
            progress.setWindowTitle(tr("presets.save_as_default"))
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(200)

            count = 0
            for i, f in enumerate(files, start=1):
                if progress.wasCanceled():
                    break
                progress.setLabelText(f"{tr('presets.save_as_default')}: {f.name} ({i}/{len(files)})")
                progress.setValue(i - 1)
                QApplication.processEvents()
                if self._preset_manager.save_as_default(f):
                    count += 1
            progress.setValue(len(files))
            QMessageBox.information(
                self, tr("common.success"),
                tr("presets.saved_all_as_default").format(count=count)
            )
            self._update_tree_preset_indicators()
    
    def _save_all_preset(self):
        """Save all config files as named preset."""
        if not self._preset_manager:
            QMessageBox.warning(self, tr("common.warning"), tr("presets.no_profile_selected"))
            return
        
        files = self._get_all_config_files()
        if not files:
            QMessageBox.information(self, tr("common.info"), tr("presets.no_config_files"))
            return
        
        existing_names = self._preset_manager.get_all_preset_names()
        
        from shared.ui.dialogs.config_preset_dialog import BulkSavePresetDialog
        dialog = BulkSavePresetDialog(files, existing_names, self)
        
        if dialog.exec() == QDialog.Accepted:
            progress = QProgressDialog(tr("common.loading"), tr("common.cancel"), 0, len(files), self)
            progress.setWindowTitle(tr("presets.save_preset"))
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(200)

            count = 0
            for i, f in enumerate(files, start=1):
                if progress.wasCanceled():
                    break
                progress.setLabelText(f"{tr('presets.save_preset')}: {f.name} ({i}/{len(files)})")
                progress.setValue(i - 1)
                QApplication.processEvents()
                if self._preset_manager.save_preset(f, dialog.preset_name, dialog.description):
                    count += 1
            progress.setValue(len(files))
            QMessageBox.information(
                self, tr("common.success"),
                tr("presets.saved_all_preset").format(name=dialog.preset_name, count=count)
            )
            self._update_tree_preset_indicators()
    
    def _load_all_preset(self):
        """Load preset for all config files."""
        if not self._preset_manager:
            QMessageBox.warning(self, tr("common.warning"), tr("presets.no_profile_selected"))
            return
        
        files = self._get_all_config_files()
        if not files:
            QMessageBox.information(self, tr("common.info"), tr("presets.no_config_files"))
            return

        profiles = [self._preset_manager.profile_name]
        for p in self._preset_manager.list_profiles_with_presets():
            if p and p not in profiles:
                profiles.append(p)

        def data_provider(profile_name: str):
            preset_names = self._preset_manager.get_all_preset_names_for_profile(profile_name)
            files_with_presets = self._preset_manager.build_files_with_presets_for_profile(files, profile_name)
            return preset_names, files_with_presets

        from shared.ui.dialogs.config_preset_dialog import BulkLoadPresetDialog
        dialog = BulkLoadPresetDialog(profiles, data_provider, self)
        
        if dialog.exec() == QDialog.Accepted and dialog.selected_preset:
            progress = QProgressDialog(tr("common.loading"), tr("common.cancel"), 0, len(files), self)
            progress.setWindowTitle(tr("presets.load_preset"))
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(200)

            count = 0
            for i, f in enumerate(files, start=1):
                if progress.wasCanceled():
                    break
                progress.setLabelText(f"{tr('presets.load_preset')}: {f.name} ({i}/{len(files)})")
                progress.setValue(i - 1)
                QApplication.processEvents()
                if self._preset_manager.load_preset(f, dialog.selected_preset, source_profile=dialog.selected_profile):
                    count += 1
            progress.setValue(len(files))
            QMessageBox.information(
                self, tr("common.success"),
                tr("presets.loaded_all_preset").format(name=dialog.selected_preset, count=count)
            )
            self._on_selection_changed()  # Refresh preview
            self.resources_changed.emit()
    
    def _restore_all_default(self):
        """Restore all config files from defaults."""
        if not self._preset_manager:
            QMessageBox.warning(self, tr("common.warning"), tr("presets.no_profile_selected"))
            return
        
        files = self._get_all_config_files()
        files_with_defaults = [f for f in files if self._preset_manager.has_default(f)]
        
        if not files_with_defaults:
            QMessageBox.information(self, tr("common.info"), tr("presets.no_defaults_saved"))
            return
        
        reply = QMessageBox.question(
            self, tr("common.confirm"),
            tr("presets.confirm_restore_all").format(count=len(files_with_defaults)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            progress = QProgressDialog(tr("common.loading"), tr("common.cancel"), 0, len(files_with_defaults), self)
            progress.setWindowTitle(tr("presets.restore_default"))
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(200)

            count = 0
            for i, f in enumerate(files_with_defaults, start=1):
                if progress.wasCanceled():
                    break
                progress.setLabelText(f"{tr('presets.restore_default')}: {f.name} ({i}/{len(files_with_defaults)})")
                progress.setValue(i - 1)
                QApplication.processEvents()
                if self._preset_manager.restore_default(f):
                    count += 1
            progress.setValue(len(files_with_defaults))
            QMessageBox.information(
                self, tr("common.success"),
                tr("presets.restored_all_from_default").format(count=count)
            )
            self._on_selection_changed()  # Refresh preview
            self.resources_changed.emit()
    
    def _update_tree_preset_indicators(self):
        """Update visual indicators in tree for files with presets."""
        if not self._preset_manager:
            return
        
        def update_item(item: QTreeWidgetItem):
            path = Path(item.data(0, Qt.UserRole))
            if path.is_file() and path.suffix.lower() in EDITABLE_EXTENSIONS:
                has_default = self._preset_manager.has_default(path)
                preset_count = self._preset_manager.get_preset_count_all_profiles(path)
                
                # Update item appearance
                name = path.name
                if has_default or preset_count > 0:
                    indicators = []
                    if has_default:
                        indicators.append("✓")
                    if preset_count > 0:
                        indicators.append(f"📑{preset_count}")
                    item.setText(0, f"{name} [{' '.join(indicators)}]")
                    item.setForeground(0, QColor("#4caf50"))
                else:
                    item.setText(0, name)
                    item.setForeground(0, QColor(ThemeManager.get_text_color()))
            
            for i in range(item.childCount()):
                update_item(item.child(i))
        
        for i in range(self.tree.topLevelItemCount()):
            update_item(self.tree.topLevelItem(i))
