#!/usr/bin/env python3
"""Quick manual test for the Conflict Resolution dialog."""

import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))

    from PySide6.QtWidgets import QApplication
    from xml.etree import ElementTree as ET

    from shared.utils.locale_manager import LocaleManager
    from features.config.core.mission_config_merger import ConfigEntry
    from shared.ui.dialogs.conflict_resolver_dialog import ConflictResolverDialog

    # Initialize localization (loads locale JSONs)
    LocaleManager()
    app = QApplication.instance() or QApplication(sys.argv)

    def _make_type(name: str, nominal: str) -> ET.Element:
        e = ET.Element("type", {"name": name})
        n = ET.SubElement(e, "nominal")
        n.text = nominal
        return e

    # Two different candidates for the same unique_key
    e1 = ConfigEntry(
        element=_make_type("TestType", "6"),
        unique_key="TestType",
        source_mod="@ModA",
        source_file=Path("types.xml"),
    )
    e2 = ConfigEntry(
        element=_make_type("TestType", "10"),
        unique_key="TestType",
        source_mod="@ModB",
        source_file=Path("types.xml"),
    )

    # Include a non-conflict key (single candidate) to ensure UI/count filtering works
    solo = ConfigEntry(
        element=_make_type("SoloType", "1"),
        unique_key="SoloType",
        source_mod="@ModC",
        source_file=Path("types.xml"),
    )

    conflict_entries = {
        "types.xml": [e1, e2, solo],
    }

    dlg = ConflictResolverDialog(conflict_entries, preview=None)
    dlg.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
