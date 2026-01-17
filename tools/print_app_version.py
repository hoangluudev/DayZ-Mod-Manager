from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    app_json = repo_root / "configs" / "app.json"

    try:
        data = json.loads(app_json.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("0.0.0")
        return 0

    version = str(data.get("version") or "0.0.0").strip()
    print(version if version else "0.0.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
