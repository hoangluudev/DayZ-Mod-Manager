"""Asset helpers for resolving app asset paths and branding.

This module centralizes logic for resolving the app logo so swapping
the image is a single change (settings or filename).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from shared.utils.resources import asset_path


def get_app_logo_filename(settings: Optional[object] = None) -> str:
    """Return the configured app logo filename (under assets/icons).

    Args:
        settings: optional SettingsManager.settings object (for testing).
    """
    if settings is not None:
        return getattr(settings, "app_logo", "new_logo.png")

    try:
        from features.settings.core.settings_manager import SettingsManager
        sm = SettingsManager()
        return getattr(sm.settings, "app_logo", "new_logo.png")
    except Exception:
        return "new_logo.png"


def get_app_logo_path() -> Path:
    """Return a Path to the app logo under `assets/icons`.
    """
    filename = get_app_logo_filename()
    return asset_path("icons", filename)
