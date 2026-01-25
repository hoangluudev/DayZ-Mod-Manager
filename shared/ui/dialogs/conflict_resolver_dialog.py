from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from xml.etree import ElementTree as ET

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QProgressDialog,
    QAbstractItemView,
    QHeaderView,
)

from shared.ui.components.table import ReusableTable, TableColumn
from shared.utils.locale_manager import tr


@dataclass
class _ResolvedSelection:
    entry: object
    action: str  # "replace" | "merge"


class ConflictResolverDialog(QDialog):
    """Dialog for resolving XML entry conflicts across multiple files.

    The dialog groups conflicts per file, then per unique entry key. Users can:
    - Pick ONE entry to replace (non-mergeable files)
    - Pick MULTIPLE entries to merge (mergeable files)
    - Auto-pick using bulk strategies per file
    """

    def __init__(self, conflict_entries: dict, preview, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.conflict_entries = conflict_entries or {}
        self.preview = preview

        self._name_mgr = getattr(parent, "_name_mgr", None)

        self.setWindowTitle(tr("mission_merge.conflict_resolver_title"))
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        self._setup_ui()
        self._populate_conflicts()

    def _display_mod_name(self, mod_name: str) -> str:
        try:
            if getattr(self, "_name_mgr", None) and mod_name:
                return self._name_mgr.get_original_name(str(mod_name))
        except Exception:
            pass
        return str(mod_name or "")

    def _entry_key(self, entry) -> str:
        """Return a stable per-candidate key for a conflict entry.

        IMPORTANT: `entry.unique_key` is the *conflict group* identifier (e.g. the
        type name), so it is NOT unique across the candidate rows. Using it breaks
        UI sync (manual pick/merge + auto-pick won't mark which row is selected).

        We instead key on (source_mod, source_file, deep XML signature).
        """
        try:
            src_mod = str(getattr(entry, "source_mod", "") or "")
        except Exception:
            src_mod = ""

        try:
            src_file_obj = getattr(entry, "source_file", None)
            src_file = str(src_file_obj) if src_file_obj is not None else ""
        except Exception:
            src_file = ""

        try:
            el = getattr(entry, "element", None)
            if el is not None:
                sig = self._deep_signature(el)
                return f"{src_mod}|{src_file}|{repr(sig)}"
        except Exception:
            pass

        # Fallback: keep it stable within the dialog session.
        return f"{src_mod}|{src_file}|id:{id(entry)}"

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel(f"<h2>{tr('mission_merge.conflict_resolver_title')}</h2>")
        layout.addWidget(header)

        info_label = QLabel(tr("mission_merge.conflict_resolver_info"))
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.tabs = QTabWidget()
        self.tabs.setMovable(False)
        try:
            self.tabs.setUsesScrollButtons(True)
        except Exception:
            pass
        self.tabs.currentChanged.connect(self._update_status)
        layout.addWidget(self.tabs, stretch=1)

        self.status_bar = QLabel()
        self.status_bar.setStyleSheet(
            """
            QLabel {
                color: #ffffff;
                font-weight: bold;
                padding: 12px;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2d2d2d, stop:1 #1e1e1e);
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin: 4px;
            }
            """
        )
        layout.addWidget(self.status_bar)

        self.chk_force_apply = QCheckBox(tr("mission_merge.force_apply"))
        self.chk_force_apply.setToolTip(tr("mission_merge.force_apply_tooltip"))
        self.chk_force_apply.stateChanged.connect(self._update_status)
        layout.addWidget(self.chk_force_apply)

        buttons = QHBoxLayout()
        buttons.addStretch()

        self.btn_preview = QPushButton(tr("mission_merge.preview_merge_result"))
        self.btn_preview.clicked.connect(self._show_merge_preview)
        buttons.addWidget(self.btn_preview)

        self.btn_apply = QPushButton(tr("common.apply"))
        self.btn_apply.clicked.connect(self._apply_resolution)
        buttons.addWidget(self.btn_apply)

        self.btn_cancel = QPushButton(tr("common.cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_cancel)

        layout.addLayout(buttons)

    def _populate_conflicts(self) -> None:
        for filename, entries in (self.conflict_entries or {}).items():
            tab = self._create_conflict_tab(filename, list(entries or []))
            self.tabs.addTab(tab, f"{filename} ({len(entries or [])})")
        self._update_status()

    def _get_tab_data(self, tab: QWidget) -> Optional[dict]:
        td = getattr(tab, "_tab_data", None)
        if isinstance(td, dict):
            return td
        td = tab.property("tab_data")
        return td if isinstance(td, dict) else None

    def _create_conflict_tab(self, filename: str, entries: list) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # Determine merge capability (safe heuristic)
        is_mergeable = False
        try:
            from features.config.core.mission_config_merger import ConfigFileType

            file_type = ConfigFileType.from_filename(filename)
            is_mergeable = file_type.name.lower() in {"randompresets", "eventspawns"}
        except Exception:
            is_mergeable = False

        info_text = tr("mission_merge.conflict_replace_info") if not is_mergeable else tr("mission_merge.conflict_merge_info")
        info = QLabel(info_text)
        info.setStyleSheet("color: #ff9800; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        conflicts_by_key: dict[str, list] = {}
        for entry in entries:
            key = getattr(entry, "unique_key", None)
            if not key:
                key = f"unknown:{id(entry)}"
            conflicts_by_key.setdefault(str(key), []).append(entry)

        # Only keys with multiple candidates are actionable conflicts.
        conflict_keys = [k for k, v in conflicts_by_key.items() if len(v or []) > 1]

        main_splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_label = QLabel(tr("mission_merge.conflicting_entries"))
        left_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(left_label)

        conflict_list = QListWidget()
        conflict_list.setAlternatingRowColors(False)
        conflict_list.setStyleSheet(
            """
            QListWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2d2d2d;
            }
            QListWidget::item:selected {
                background-color: #404040;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #333333;
            }
            """
        )

        for key in conflict_keys:
            entries_for_key = conflicts_by_key.get(key, [])
            base_label = key.split(":", 1)[-1] if ":" in key else key
            entry_count = len(entries_for_key)
            item = QListWidgetItem(f"{base_label} ({tr('mission_merge.conflict_entry_count', count=entry_count)})")
            item.setData(Qt.UserRole, key)
            item.setData(Qt.UserRole + 1, base_label)
            conflict_list.addItem(item)
        # Make the left list more stable in size and rendering
        conflict_list.setUniformItemSizes(True)
        conflict_list.setMinimumWidth(240)
        left_layout.addWidget(conflict_list)
        main_splitter.addWidget(left_widget)

        right_tabs = QTabWidget()
        right_tabs.setMinimumWidth(620)
        try:
            right_tabs.tabBar().setExpanding(False)
        except Exception:
            pass

        # Options tab
        options_tab = QWidget()
        options_layout = QVBoxLayout(options_tab)
        options_layout.setContentsMargins(4, 4, 4, 4)

        state_row = QHBoxLayout()
        state_label = QLabel(tr("mission_merge.conflict_current_state", state=tr("mission_merge.conflict_state_none")))
        state_label.setStyleSheet("color: #ff9800; font-weight: bold; padding: 4px; background-color: rgba(255, 152, 0, 0.1);")
        state_row.addWidget(state_label, stretch=1)
        
        remaining_label = QLabel("")
        remaining_label.setStyleSheet("color: gray; font-size: 11px; margin-left: 8px;")
        state_row.addWidget(remaining_label)
        
        options_layout.addLayout(state_row)

        options_columns = [
            TableColumn("source_mod", tr("mission_merge.source_mod"), QHeaderView.ResizeToContents),
            TableColumn("entry_preview", tr("mission_merge.entry_preview"), QHeaderView.Stretch),
        ]
        options_table = ReusableTable(options_columns, has_checkbox=True)
        options_table.set_row_click_toggles_checkbox(True)
        options_table.setAlternatingRowColors(False)
        options_table.setSelectionMode(QAbstractItemView.NoSelection)
        options_table.verticalHeader().setVisible(False)
        # Ensure predictable header behavior: first column fits content, second stretches
        try:
            header = options_table.horizontalHeader()
            col_count = options_table.columnCount()
            # If table has checkbox column, adjust indexes accordingly
            if col_count >= 3:
                # 0: checkbox, 1: source_mod, 2: preview
                header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
                header.setSectionResizeMode(2, QHeaderView.Stretch)
                options_table.setColumnWidth(0, 36)
            elif col_count == 2:
                header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                header.setSectionResizeMode(1, QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setStretchLastSection(True)
        except Exception:
            pass
        options_layout.addWidget(options_table)

        preview_label = QLabel(tr("mission_merge.xml_preview"))
        preview_label.setStyleSheet("font-weight: bold;")
        options_layout.addWidget(preview_label)

        preview_text = QTextEdit()
        preview_text.setReadOnly(True)
        preview_text.setFont(QFont("Consolas", 10))
        preview_text.setMaximumHeight(180)
        preview_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
            """
        )
        options_layout.addWidget(preview_text)

        right_tabs.addTab(options_tab, tr("mission_merge.resolution_options"))

        # Result preview tab
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        result_layout.setContentsMargins(4, 4, 4, 4)

        result_info = QLabel(tr("mission_merge.result_preview_info"))
        result_info.setStyleSheet("color: gray; font-size: 11px;")
        result_info.setWordWrap(True)
        result_layout.addWidget(result_info)

        result_preview = QTextEdit()
        result_preview.setReadOnly(True)
        result_preview.setFont(QFont("Consolas", 10))
        result_preview.setStyleSheet(
            """
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
            """
        )
        result_layout.addWidget(result_preview)
        right_tabs.addTab(result_tab, tr("mission_merge.result_preview"))

        main_splitter.addWidget(right_tabs)
        try:
            main_splitter.setHandleWidth(6)
        except Exception:
            pass
        main_splitter.setSizes([280, 720])
        layout.addWidget(main_splitter)

        tab_data = {
            "filename": filename,
            "conflicts_by_key": conflicts_by_key,
            "conflict_keys": conflict_keys,
            "is_mergeable": is_mergeable,
            "conflict_list": conflict_list,
            "options_table": options_table,
            "preview_text": preview_text,
            "state_label": state_label,
            "remaining_label": remaining_label,
            "result_preview": result_preview,
            "resolved_by_key": {},
            "current_key": None,
        }
        widget._tab_data = tab_data  # type: ignore[attr-defined]
        widget.setProperty("tab_data", tab_data)

        # Auto pick menu (description area will be added to the options layout)
        self._create_auto_pick_menu(options_layout, tab_data)

        conflict_list.currentItemChanged.connect(lambda curr, _prev, td=tab_data: self._on_conflict_selected(td, curr))
        options_table.checkbox_toggled.connect(lambda row, checked, td=tab_data: self._on_option_checkbox_toggled(td, row, checked))

        # Select first conflict if available
        if conflict_list.count() > 0:
            conflict_list.setCurrentRow(0)

        self._update_remaining_label(tab_data)
        return widget

    def _create_auto_pick_menu(self, parent_layout: QHBoxLayout, tab_data: dict) -> None:
        btn_auto_pick = QPushButton(tr("mission_merge.auto_pick"))
        btn_auto_pick.setToolTip(tr("mission_merge.auto_pick_tooltip"))
        btn_auto_pick.setStyleSheet(
            """
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976d2; }
            QPushButton:pressed { background-color: #0d47a1; }
            """
        )

        menu = QMenu(btn_auto_pick)

        # Create a simple monochrome icon for menu items (12x12 gray square outline)
        try:
            from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor

            def _mono_icon():
                pix = QPixmap(12, 12)
                pix.fill(QColor(0, 0, 0, 0))
                p = QPainter(pix)
                p.setPen(QColor(180, 180, 180))
                p.drawRect(1, 1, 10, 10)
                p.end()
                return QIcon(pix)

            icon_mono = _mono_icon()
        except Exception:
            icon_mono = None

        action_identical = menu.addAction(icon_mono, tr("mission_merge.auto_pick_identical"), lambda: self._auto_pick_file_conflicts(tab_data, "identical"))
        action_identical.setToolTip(tr("mission_merge.auto_pick_identical_tooltip"))
        
        action_first_mod = menu.addAction(icon_mono, tr("mission_merge.auto_pick_first_entry"), lambda: self._auto_pick_file_conflicts(tab_data, "first_entry"))
        action_first_mod.setToolTip(tr("mission_merge.auto_pick_first_entry_tooltip"))
        
        action_last = menu.addAction(icon_mono, tr("mission_merge.auto_pick_last_entry"), lambda: self._auto_pick_file_conflicts(tab_data, "last_entry"))
        action_last.setToolTip(tr("mission_merge.auto_pick_last_entry_tooltip"))
        
        menu.addSeparator()
        
        action_clear = menu.addAction(tr("mission_merge.auto_pick_clear_all"), lambda: self._auto_pick_file_conflicts(tab_data, "clear_all"))
        action_clear.setToolTip(tr("mission_merge.auto_pick_clear_all_tooltip"))

        # Description area: full-width, wrapping label added to the options layout
        desc_label = QLabel("")
        desc_label.setStyleSheet("color: #bbbbbb; font-size: 11px; margin: 6px 8px;")
        desc_label.setWordWrap(True)
        desc_label.setMaximumHeight(80)
        parent_layout.addWidget(desc_label)

        # Update description on hover
        try:
            action_identical.hovered.connect(lambda: desc_label.setText(tr("mission_merge.auto_pick_desc_identical")))
            action_first_mod.hovered.connect(lambda: desc_label.setText(tr("mission_merge.auto_pick_desc_first_mod")))
            action_last.hovered.connect(lambda: desc_label.setText(tr("mission_merge.auto_pick_desc_last_entry")))
            action_clear.hovered.connect(lambda: desc_label.setText(tr("mission_merge.auto_pick_desc_clear_all")))
            menu.aboutToHide.connect(lambda: desc_label.setText(""))
        except Exception:
            # Older Qt/PySide versions may not expose hovered on QAction; ignore safely
            pass

        btn_auto_pick.clicked.connect(lambda: menu.exec(btn_auto_pick.mapToGlobal(btn_auto_pick.rect().bottomLeft())))
        parent_layout.addWidget(btn_auto_pick)

        tab_data["btn_auto_pick"] = btn_auto_pick
        tab_data["auto_pick_menu"] = menu

    @staticmethod
    def _deep_signature(elem: ET.Element):
        try:
            tag = str(elem.tag)
        except Exception:
            tag = ""
        try:
            attrib = tuple(sorted((elem.attrib or {}).items()))
        except Exception:
            attrib = ()
        try:
            text = (elem.text or "").strip()
        except Exception:
            text = ""
        children = []
        try:
            for ch in list(elem):
                children.append(ConflictResolverDialog._deep_signature(ch))
        except Exception:
            children = []
        return (tag, attrib, text, tuple(children))

    def _auto_pick_file_conflicts(self, tab_data: dict, strategy: str) -> None:
        conflicts_by_key = tab_data.get("conflicts_by_key") or {}
        conflict_keys = list(tab_data.get("conflict_keys") or [])
        if not conflicts_by_key or not conflict_keys:
            return

        resolved_by_key = tab_data.setdefault("resolved_by_key", {})

        picked = 0
        cleared = 0

        show_progress = len(conflict_keys) > 10
        progress: Optional[QProgressDialog] = None
        if show_progress:
            progress = QProgressDialog(
                tr("mission_merge.auto_pick_progress"),
                tr("common.cancel"),
                0,
                len(conflict_keys),
                self,
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setAutoClose(False)
            progress.setAutoReset(False)
            progress.show()

        def _tick(i: int, label: str) -> bool:
            if not progress:
                return True
            progress.setValue(i)
            progress.setLabelText(label)
            QApplication.processEvents()
            return not progress.wasCanceled()

        try:
            if strategy == "clear_all":
                for i, conflict_key in enumerate(list(conflict_keys)):
                    if show_progress and not _tick(i, f"{tr('mission_merge.auto_pick_clearing')} {i+1}/{len(conflict_keys)}"):
                        break
                    if resolved_by_key.pop(conflict_key, None) is not None:
                        cleared += 1

            elif strategy == "identical":
                for i, conflict_key in enumerate(list(conflict_keys)):
                    if show_progress and not _tick(i, f"{tr('mission_merge.auto_pick_analyzing')} {i+1}/{len(conflict_keys)}"):
                        break
                    entries = list((conflicts_by_key.get(conflict_key) or []))
                    if resolved_by_key.get(conflict_key):
                        continue
                    if not entries:
                        continue
                    sigs = []
                    for e in entries:
                        el = getattr(e, "element", None)
                        if el is not None:
                            sigs.append(self._deep_signature(el))
                    if not (sigs and all(s == sigs[0] for s in sigs[1:])):
                        continue
                    resolved_by_key[conflict_key] = [{"entry": entries[0], "action": "replace"}]
                    picked += 1

            elif strategy == "first_mod":
                mod_priority: dict[str, int] = {}
                for i, conflict_key in enumerate(list(conflict_keys)):
                    if show_progress and not _tick(i, f"{tr('mission_merge.auto_pick_analyzing')} {i+1}/{len(conflict_keys)}"):
                        break
                    entries = list((conflicts_by_key.get(conflict_key) or []))
                    if resolved_by_key.get(conflict_key):
                        continue

                    by_mod: dict[str, list] = {}
                    for entry in list(entries or []):
                        mod = str(getattr(entry, "source_mod", ""))
                        by_mod.setdefault(mod, []).append(entry)
                    if not by_mod:
                        continue

                    if not mod_priority:
                        for mod in by_mod.keys():
                            mod_priority[mod] = len(mod_priority)

                    sorted_mods = sorted(by_mod.keys(), key=lambda m: mod_priority.get(m, 999))
                    first_entry = by_mod[sorted_mods[0]][0]
                    resolved_by_key[conflict_key] = [{"entry": first_entry, "action": "replace"}]
                    picked += 1

            elif strategy == "last_entry":
                # Pick the last entry in the candidate list for each conflict (simple deterministic rule)
                for i, conflict_key in enumerate(list(conflict_keys)):
                    if show_progress and not _tick(i, f"{tr('mission_merge.auto_pick_analyzing')} {i+1}/{len(conflict_keys)}"):
                        break
                    entries = list((conflicts_by_key.get(conflict_key) or []))
                    if resolved_by_key.get(conflict_key):
                        continue
                    if not entries:
                        continue
                    last_entry = entries[-1]
                    resolved_by_key[conflict_key] = [{"entry": last_entry, "action": "replace"}]
                    picked += 1

            if progress:
                progress.setValue(len(conflict_keys))
                QApplication.processEvents()
                progress.close()

        except Exception as e:
            if progress:
                progress.close()
            QMessageBox.critical(self, tr("common.error"), str(e))
            return

        # Refresh all markers
        for conflict_key in list(conflict_keys):
            self._update_conflict_key_marker(tab_data, conflict_key)

        # Refresh current conflict display to show new selections
        conflict_list = tab_data.get("conflict_list")
        current_item = conflict_list.currentItem() if conflict_list else None
        if current_item:
            # Force refresh by re-selecting
            self._on_conflict_selected(tab_data, current_item)

        self._update_remaining_label(tab_data)
        self._update_status()

        QApplication.processEvents()

        if strategy == "clear_all":
            if cleared > 0:
                QMessageBox.information(self, tr("common.success"), tr("mission_merge.auto_pick_cleared", count=cleared))
            else:
                QMessageBox.information(self, tr("common.info"), tr("mission_merge.auto_pick_nothing_to_clear"))
        else:
            if picked > 0:
                QMessageBox.information(self, tr("common.success"), tr("mission_merge.auto_pick_applied", count=picked))
            else:
                QMessageBox.information(self, tr("common.info"), tr("mission_merge.auto_pick_not_applicable"))

    def _on_conflict_selected(self, tab_data: dict, item: Optional[QListWidgetItem]):
        if not item:
            return

        key = str(item.data(Qt.UserRole))
        entries = (tab_data.get("conflicts_by_key") or {}).get(key, [])
        options_table: ReusableTable = tab_data["options_table"]
        preview_text: QTextEdit = tab_data["preview_text"]

        tab_data["current_key"] = key

        resolved = tab_data.setdefault("resolved_by_key", {}).get(key, [])
        selected_keys = set()
        for sel in list(resolved or []):
            try:
                selected_keys.add(self._entry_key(sel.get("entry")))
            except Exception:
                pass

        table_data = []
        for entry in list(entries or []):
            entry_key = self._entry_key(entry)
            selected = entry_key in selected_keys
            display_mod = self._display_mod_name(str(getattr(entry, "source_mod", "")))
            xml_str = entry.to_xml_string()
            preview = (xml_str[:100] + "...") if len(xml_str) > 100 else xml_str

            table_data.append(
                {
                    "checked": selected,
                    "source_mod": {"text": display_mod, "tooltip": display_mod},
                    "entry_preview": {"text": preview.replace("\n", " "), "tooltip": xml_str},
                    "_entry": entry,
                    "_entry_key": entry_key,
                    "_key": key,
                }
            )

        options_table.set_data(table_data)

        if entries:
            try:
                head = entries[0]
                head_src = self._display_mod_name(str(getattr(head, "source_mod", "")))
                xml_preview = f"<!-- {tr('mission_merge.source')}: {head_src} -->\n"
                xml_preview += f"<!-- {tr('mission_merge.file')}: {getattr(getattr(head, 'source_file', None), 'name', '')} -->\n\n"
                xml_preview += head.to_xml_string()
                preview_text.setText(xml_preview)
            except Exception:
                pass

        self._update_state_label(tab_data)
        self._update_result_preview(tab_data)
        self._update_remaining_label(tab_data)
        self._update_status()
        self._update_conflict_key_marker(tab_data, key)

    def _on_option_checkbox_toggled(self, tab_data: dict, row: int, checked: bool):
        conflict_key = tab_data.get("current_key")
        if not conflict_key:
            return

        options_table: ReusableTable = tab_data["options_table"]
        row_data = options_table.get_row_data(row)
        if not row_data:
            return
        entry = row_data.get("_entry")
        if not entry:
            return

        # Preview always follows clicked row
        self._update_entry_preview_from_row(tab_data, entry)

        resolved_by_key = tab_data.setdefault("resolved_by_key", {})
        entry_k = self._entry_key(entry)

        is_mergeable = bool(tab_data.get("is_mergeable"))
        
        if checked:
            if not is_mergeable:
                # Radio behavior: uncheck all others, check this one
                for r, rd in enumerate(options_table._data):
                    if rd.get("_is_group_header"):
                        continue
                    should_check = (r == row)
                    rd["checked"] = should_check
                    options_table.set_row_checked(r, should_check)
                    

                # Update resolved_by_key
                resolved_by_key[conflict_key] = [{"entry": entry, "action": "replace"}]
                tab_data["resolved_by_key"] = resolved_by_key
            else:
                # Mergeable: can select multiple
                selections = list(resolved_by_key.get(conflict_key, []))
                selections = [s for s in selections if self._entry_key(s.get("entry")) != entry_k]
                selections.append({"entry": entry, "action": "merge"})
                resolved_by_key[conflict_key] = selections
                tab_data["resolved_by_key"] = resolved_by_key

                # Update this row
                row_data["checked"] = True
        else:
            # Uncheck: remove from selections
            selections = list(resolved_by_key.get(conflict_key, []))
            selections = [s for s in selections if self._entry_key(s.get("entry")) != entry_k]
            if selections:
                resolved_by_key[conflict_key] = selections
                tab_data["resolved_by_key"] = resolved_by_key
            else:
                resolved_by_key.pop(conflict_key, None)
                tab_data["resolved_by_key"] = resolved_by_key

                # Update this row
                row_data["checked"] = False

        # Update all UI elements
        self._update_selection_actions(tab_data, conflict_key)
        self._update_conflict_key_marker(tab_data, conflict_key)
        self._update_state_label(tab_data)
        self._update_result_preview(tab_data)
        self._update_remaining_label(tab_data)
        self._update_status()

    def _update_entry_preview_from_row(self, tab_data: dict, entry) -> None:
        preview_text: QTextEdit = tab_data["preview_text"]
        try:
            xml_preview = f"<!-- {tr('mission_merge.source')}: {self._display_mod_name(getattr(entry, 'source_mod', ''))} -->\n"
            xml_preview += f"<!-- {tr('mission_merge.file')}: {getattr(getattr(entry, 'source_file', None), 'name', '')} -->\n\n"
            xml_preview += entry.to_xml_string()
            preview_text.setText(xml_preview)
        except Exception:
            pass

    def _update_selection_actions(self, tab_data: dict, conflict_key: str) -> None:
        selections = tab_data.setdefault("resolved_by_key", {}).get(conflict_key, [])
        if not selections:
            return
        is_mergeable = bool(tab_data.get("is_mergeable"))
        if len(selections) == 1:
            selections[0]["action"] = "replace"
        elif is_mergeable:
            for sel in selections:
                sel["action"] = "merge"
        else:
            selections[0]["action"] = "replace"
            tab_data["resolved_by_key"][conflict_key] = [selections[0]]

    def _update_state_label(self, tab_data: dict) -> None:
        lbl: QLabel = tab_data.get("state_label")
        if not lbl:
            return

        conflict_key = tab_data.get("current_key")
        if not conflict_key:
            lbl.setText(tr("mission_merge.conflict_current_state", state=tr("mission_merge.conflict_state_none")))
            lbl.setStyleSheet("color: #ff9800; font-weight: bold; padding: 4px; background-color: rgba(255, 152, 0, 0.1);")
            return

        selections = tab_data.setdefault("resolved_by_key", {}).get(conflict_key, [])
        if not selections:
            state_text = tr("mission_merge.conflict_state_none")
            lbl.setStyleSheet("color: #ff9800; font-weight: bold; padding: 4px; background-color: rgba(255, 152, 0, 0.1);")
        elif len(selections) == 1:
            entry = selections[0]["entry"]
            name = self._display_mod_name(getattr(entry, "source_mod", ""))
            try:
                el = getattr(entry, "element", None)
                if el is not None:
                    name = el.get("name") or name
            except Exception:
                pass
            state_text = tr("mission_merge.conflict_state_replace", name=name)
            lbl.setStyleSheet("color: #4caf50; font-weight: bold; padding: 4px; background-color: rgba(76, 175, 80, 0.1);")
        else:
            state_text = tr("mission_merge.conflict_state_merge", count=len(selections))
            lbl.setStyleSheet("color: #2196f3; font-weight: bold; padding: 4px; background-color: rgba(33, 150, 243, 0.1);")

        lbl.setText(tr("mission_merge.conflict_current_state", state=state_text))
        try:
            lbl.update()
            lbl.repaint()
        except Exception:
            pass

    def _update_remaining_label(self, tab_data: dict) -> None:
        lbl: QLabel = tab_data.get("remaining_label")
        if not lbl:
            return
        conflict_keys = list(tab_data.get("conflict_keys") or [])
        resolved_by_key = tab_data.get("resolved_by_key") or {}
        total = len(conflict_keys)
        resolved = sum(1 for k in conflict_keys if resolved_by_key.get(k))
        remaining = max(0, total - resolved)
        lbl.setText(tr("mission_merge.remaining_count", remaining=remaining, total=total))
        try:
            lbl.update()
            lbl.repaint()
        except Exception:
            pass

    def _update_conflict_key_marker(self, tab_data: dict, conflict_key: str) -> None:
        conflict_list: QListWidget = tab_data.get("conflict_list")
        if not conflict_list or not conflict_key:
            return
        resolved_by_key = tab_data.get("resolved_by_key") or {}
        is_resolved = bool(resolved_by_key.get(conflict_key))
        entry_count = len((tab_data.get("conflicts_by_key") or {}).get(conflict_key, []))

        for i in range(conflict_list.count()):
            it = conflict_list.item(i)
            if not it or str(it.data(Qt.UserRole)) != str(conflict_key):
                continue

            base_label = it.data(Qt.UserRole + 1) or it.text().lstrip("✓ ").split(" (")[0]
            label_text = f"{base_label} ({tr('mission_merge.conflict_entry_count', count=entry_count)})"
            it.setText(("✓ " if is_resolved else "") + label_text)
            it.setForeground(QColor("#4caf50") if is_resolved else QColor("#d4d4d4"))
            break

    def _update_result_preview(self, tab_data: dict) -> None:
        result_preview: QTextEdit = tab_data.get("result_preview")
        if not result_preview:
            return
        conflict_key = tab_data.get("current_key")
        if not conflict_key:
            result_preview.setText("")
            return

        selections = tab_data.setdefault("resolved_by_key", {}).get(conflict_key, [])
        if not selections:
            result_preview.setText(f"<!-- {tr('mission_merge.conflict_state_none')} -->")
            return

        try:
            if len(selections) == 1:
                entry = selections[0]["entry"]
                xml_preview = f"<!-- {tr('mission_merge.conflict_state_replace', name=self._display_mod_name(getattr(entry, 'source_mod', '')))} -->\n\n"
                xml_preview += entry.to_xml_string()
                result_preview.setText(xml_preview)
                return

            # Merge view
            xml_preview = f"<!-- {tr('mission_merge.conflict_state_merge', count=len(selections))} -->\n"
            sources = ", ".join([self._display_mod_name(getattr(sel["entry"], "source_mod", "")) for sel in selections])
            xml_preview += f"<!-- Sources: {sources} -->\n\n"

            first_entry = selections[0]["entry"]
            first_el = getattr(first_entry, "element", None)
            if first_el is None:
                result_preview.setText(xml_preview)
                return

            parent_tag = first_el.tag
            parent_attrs = dict(first_el.attrib)

            all_children = []
            seen = set()
            for sel in selections:
                entry = sel["entry"]
                el = getattr(entry, "element", None)
                if el is None:
                    continue
                for child in el:
                    try:
                        sig = child.tag + ":" + ";".join([f"{k}={v}" for k, v in sorted((child.attrib or {}).items())])
                    except Exception:
                        sig = ET.tostring(child, encoding="unicode")
                    if sig in seen:
                        continue
                    cloned = ET.Element(child.tag, child.attrib)
                    cloned.text = child.text
                    cloned.tail = child.tail
                    for subchild in child:
                        cloned.append(subchild)
                    all_children.append(cloned)
                    seen.add(sig)

            attrs_str = " ".join([f'{k}="{v}"' for k, v in parent_attrs.items()])
            xml_preview += f"<{parent_tag} {attrs_str}>\n"
            for child in all_children:
                child_str = ET.tostring(child, encoding="unicode").strip()
                xml_preview += f"    {child_str}\n"
            xml_preview += f"</{parent_tag}>"
            result_preview.setText(xml_preview)

        except Exception as e:
            result_preview.setText(f"<!-- Error building preview: {str(e)} -->")

    def _compute_conflict_counts(self) -> tuple[int, int]:
        total = 0
        resolved = 0
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            tab_data = self._get_tab_data(tab)
            if not tab_data:
                continue
            conflict_keys = list(tab_data.get("conflict_keys") or [])
            resolved_by_key = tab_data.get("resolved_by_key") or {}
            total += len(conflict_keys)
            resolved += sum(1 for k in conflict_keys if resolved_by_key.get(k))
        return total, resolved

    def _update_status(self) -> None:
        total_conflicts, resolved_count = self._compute_conflict_counts()
        unresolved = max(0, total_conflicts - resolved_count)
        progress_pct = int((resolved_count / total_conflicts) * 100) if total_conflicts else 0

        force = bool(getattr(self, "chk_force_apply", None) and self.chk_force_apply.isChecked())
        if unresolved > 0:
            status_text = f"{unresolved} {tr('mission_merge.unresolved_conflicts_text')} | {progress_pct}% {tr('mission_merge.completed')}"
            if force:
                status_text += f" | {tr('mission_merge.force_mode_enabled')}"
            self.status_bar.setText(status_text)
            self.btn_apply.setEnabled(force)
        else:
            self.status_bar.setText(f"{tr('mission_merge.all_conflicts_resolved')} | 100% {tr('mission_merge.completed')}")
            self.btn_apply.setEnabled(True)

    def get_resolved_conflicts(self) -> dict:
        resolved: dict[str, list] = {}
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            tab_data = self._get_tab_data(tab)
            if not tab_data:
                continue
            filename = tab_data.get("filename")
            for _key, selections in (tab_data.get("resolved_by_key") or {}).items():
                if not selections:
                    continue
                resolved.setdefault(filename, []).extend(selections)
        return resolved

    def _apply_resolution(self) -> None:
        total, resolved_count = self._compute_conflict_counts()
        unresolved = max(0, total - resolved_count)
        force = bool(getattr(self, "chk_force_apply", None) and self.chk_force_apply.isChecked())
        if unresolved > 0 and not force:
            QMessageBox.warning(self, tr("common.warning"), tr("mission_merge.unresolved_conflicts"))
            return
        self.accept()

    def _show_merge_preview(self) -> None:
        resolved = self.get_resolved_conflicts()
        if not resolved:
            QMessageBox.information(self, tr("common.info"), tr("mission_merge.no_resolutions"))
            return

        preview_dialog = QDialog(self)
        preview_dialog.setWindowTitle(tr("mission_merge.merge_preview_title"))
        preview_dialog.resize(900, 650)

        layout = QVBoxLayout(preview_dialog)
        tabs = QTabWidget()

        for filename, resolutions in resolved.items():
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont("Consolas", 10))

            xml_content = ""
            for sel in resolutions:
                entry = sel.get("entry")
                action = sel.get("action")
                if not entry:
                    continue
                xml_content += f"<!-- Entry: {self._display_mod_name(getattr(entry, 'source_mod', ''))} ({action}) -->\n"
                try:
                    xml_content += entry.to_xml_string() + "\n\n"
                except Exception:
                    xml_content += "\n\n"

            text_edit.setText(xml_content)
            tabs.addTab(text_edit, f"{filename} ({len(resolutions)})")

        layout.addWidget(tabs)

        close_btn = QPushButton(tr("common.close"))
        close_btn.clicked.connect(preview_dialog.close)
        layout.addWidget(close_btn)

        preview_dialog.exec()
