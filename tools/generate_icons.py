"""Generate Windows .ico from the app logo PNG.

This is a small build helper used by build.ps1/build.bat.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def generate_ico(input_png: Path, output_ico: Path) -> None:
    try:
        from PIL import Image
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Pillow is required to generate .ico files. Install with: pip install Pillow"
        ) from e

    output_ico.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(input_png).convert("RGBA")

    sizes = [16, 24, 32, 48, 64, 128, 256]
    img.save(output_ico, format="ICO", sizes=[(s, s) for s in sizes])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input PNG (e.g. assets/icons/new_logo.png)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output ICO (e.g. assets/icons/app_icon.ico)",
    )

    args = parser.parse_args()
    input_png = Path(args.input).resolve()
    output_ico = Path(args.output).resolve()

    if not input_png.exists():
        raise FileNotFoundError(f"Input PNG not found: {input_png}")

    generate_ico(input_png, output_ico)
    print(f"[OK] Wrote: {output_ico}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
