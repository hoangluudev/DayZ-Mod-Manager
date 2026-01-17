#!/usr/bin/env python3
"""Embed configs/app.json into a Python module.

Goal:
- Keep configs/app.json as the single source of truth in the repo.
- For PyInstaller builds (especially -onedir), do NOT ship app.json as a plain file.
- Instead, bake its content into a Python module that ends up inside the exe.

This is not meant as strong DRM; it simply prevents casual viewing/editing.
"""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    src_json = project_root / "configs" / "app.json"
    out_py = project_root / "src" / "constants" / "app_embedded.py"

    if not src_json.exists():
        raise FileNotFoundError(f"Missing source app config: {src_json}")

    data = json.loads(src_json.read_text(encoding="utf-8"))

    out_py.parent.mkdir(parents=True, exist_ok=True)

    content = (
        '"""Auto-generated. Do not edit by hand.\n\n'
        'Generated from configs/app.json by tools/embed_app_config.py\n'
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "from typing import Any, Dict\n\n"
        f"APP_CONFIG: Dict[str, Any] = {repr(data)}\n"
    )

    out_py.write_text(content + "\n", encoding="utf-8")
    print(f"[OK] Embedded app config -> {out_py}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
