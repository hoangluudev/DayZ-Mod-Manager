"""Table presets for Mods tab.

This module exists to keep ModsTab lean.
It configures ReusableTable instances (columns, actions, options) while leaving
all domain logic (scanning mods, applying operations) in ModsTab.

Do not import heavy domain modules here.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QHeaderView

from shared.ui.components.table import ReusableTable, TableAction, TableColumn, TableOptions


def create_workshop_table(*, tr: Callable[[str], str], on_checkbox_toggled) -> ReusableTable:
    columns = [
        TableColumn("name", tr("mods.mod_name"), QHeaderView.Stretch),
        TableColumn("version", tr("mods.mod_version"), QHeaderView.ResizeToContents),
        TableColumn("size", tr("mods.mod_size"), QHeaderView.ResizeToContents),
        TableColumn("date", tr("mods.mod_date"), QHeaderView.ResizeToContents),
        TableColumn("status", tr("mods.mod_status"), QHeaderView.ResizeToContents),
    ]

    table = ReusableTable(
        columns,
        has_checkbox=True,
        options=TableOptions(row_click_toggles_checkbox=True),
    )
    table.checkbox_toggled.connect(on_checkbox_toggled)
    return table


def create_installed_table(
    *,
    tr: Callable[[str], str],
    on_checkbox_toggled,
    on_remove_clicked,
) -> ReusableTable:
    columns = [
        TableColumn("name", tr("mods.mod_name"), QHeaderView.Stretch),
        TableColumn("version", tr("mods.mod_version"), QHeaderView.ResizeToContents),
        TableColumn("size", tr("mods.mod_size"), QHeaderView.ResizeToContents),
        TableColumn("date", tr("mods.mod_date"), QHeaderView.ResizeToContents),
        TableColumn("bikey", tr("mods.bikey_status"), QHeaderView.ResizeToContents),
    ]

    actions = [
        TableAction(
            "remove",
            "",
            lambda _row_idx, row_data: on_remove_clicked(row_data) if row_data else None,
            icon="trash",
        )
    ]

    table = ReusableTable(
        columns,
        actions,
        has_checkbox=True,
        options=TableOptions(row_click_toggles_checkbox=True),
    )
    table.checkbox_toggled.connect(on_checkbox_toggled)
    return table


def update_workshop_table_headers(table: ReusableTable, *, tr: Callable[[str], str]):
    table.update_headers(
        columns={
            "name": tr("mods.mod_name"),
            "version": tr("mods.mod_version"),
            "size": tr("mods.mod_size"),
            "date": tr("mods.mod_date"),
            "status": tr("mods.mod_status"),
        }
    )


def update_installed_table_headers(table: ReusableTable, *, tr: Callable[[str], str]):
    table.update_headers(
        columns={
            "name": tr("mods.mod_name"),
            "version": tr("mods.mod_version"),
            "size": tr("mods.mod_size"),
            "date": tr("mods.mod_date"),
            "bikey": tr("mods.bikey_status"),
        }
    )
