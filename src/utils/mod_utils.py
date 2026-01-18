"""
Mod utilities - Helper functions for mod operations.
"""

import re
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


def format_file_size(size_bytes: int | float) -> str:
    """Format file size with appropriate unit (KB/MB/GB)."""
    if not size_bytes or size_bytes <= 0:
        return "-"
    
    kb = size_bytes / 1024
    mb = size_bytes / (1024 * 1024)
    gb = size_bytes / (1024 * 1024 * 1024)
    
    if gb >= 1:
        return f"{gb:.1f} GB"
    elif mb >= 1:
        return f"{mb:.1f} MB"
    else:
        return f"{kb:.1f} KB"


def get_mod_version(mod_path: Path) -> str | None:
    """Extract version from mod's meta.cpp or mod.cpp."""
    try:
        for filename in ["meta.cpp", "mod.cpp"]:
            meta_file = mod_path / filename
            if meta_file.exists():
                content = meta_file.read_text(encoding="utf-8", errors="ignore")
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
                if match:
                    return match.group(1)
    except Exception:
        pass
    return None


def get_folder_size(folder_path: Path) -> int:
    """Calculate total size of a folder."""
    total = 0
    try:
        for f in folder_path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except Exception:
        pass
    return total


def find_mod_bikeys(mod_path: Path) -> list[str]:
    """Find bikey files inside mod folder."""
    bikeys = []
    search_paths = [
        mod_path / "keys", mod_path / "Keys",
        mod_path / "key", mod_path / "Key", mod_path
    ]
    searched = set()
    
    for path in search_paths:
        if path.exists() and path not in searched:
            searched.add(path)
            bikeys.extend(f.name for f in path.glob("*.bikey"))
    
    if not bikeys:
        bikeys = [f.name for f in mod_path.rglob("*.bikey")]
    
    return bikeys


def format_datetime(dt: Optional[datetime], format_str: str = "dd/MM/yyyy") -> str:
    """
    Format datetime according to settings format string.
    
    Args:
        dt: datetime object to format
        format_str: Format string (dd/MM/yyyy, MM/dd/yyyy, yyyy-MM-dd, etc.)
    
    Returns:
        Formatted date string or "-" if dt is None
    """
    if dt is None:
        return "-"
    
    # Convert format string to Python strftime format
    py_format = format_str
    py_format = py_format.replace("yyyy", "%Y")
    py_format = py_format.replace("MM", "%m")
    py_format = py_format.replace("dd", "%d")
    py_format = py_format.replace("HH", "%H")
    py_format = py_format.replace("mm", "%M")
    py_format = py_format.replace("ss", "%S")
    
    try:
        return dt.strftime(py_format)
    except Exception:
        return "-"


def get_mod_install_date(mod_path: Path) -> Optional[datetime]:
    """
    Get the installation/creation date of a mod folder.
    Uses the oldest .pbo file modification time as the install date.
    
    Args:
        mod_path: Path to the mod folder
    
    Returns:
        datetime of installation or None
    """
    try:
        # Look for .pbo files in addons folder
        addons_path = mod_path / "addons"
        if not addons_path.exists():
            addons_path = mod_path / "Addons"
        
        pbo_files = []
        if addons_path.exists():
            pbo_files = list(addons_path.glob("*.pbo"))
        
        if not pbo_files:
            # Fallback: any .pbo in mod folder
            pbo_files = list(mod_path.rglob("*.pbo"))
        
        if pbo_files:
            # Get the oldest modification time (most likely original install time)
            oldest_time = min(f.stat().st_mtime for f in pbo_files)
            return datetime.fromtimestamp(oldest_time)
        
        # Fallback: folder creation/modification time
        stat = mod_path.stat()
        # Use creation time on Windows, modification time otherwise
        if hasattr(stat, 'st_birthtime'):
            return datetime.fromtimestamp(stat.st_birthtime)
        return datetime.fromtimestamp(stat.st_mtime)
        
    except Exception:
        return None


def get_folder_install_date(folder_path: Path) -> Optional[datetime]:
    """
    Get the installation date of a folder based on its files.
    Uses the folder's creation time or oldest file time.
    
    Args:
        folder_path: Path to the folder
    
    Returns:
        datetime of installation or None
    """
    try:
        stat = folder_path.stat()
        # On Windows, st_ctime is creation time; on Unix it's metadata change time
        # st_mtime is last modification time
        # We prefer creation time if available
        if os.name == 'nt':  # Windows
            return datetime.fromtimestamp(stat.st_ctime)
        else:
            return datetime.fromtimestamp(stat.st_mtime)
    except Exception:
        return None


def format_mods_txt(mods: list[str]) -> str:
    """Format mod list for mods.txt file."""
    if not mods:
        return ""
    cleaned = [m.strip().strip('"').strip() for m in mods if m and m.strip()]
    return ";".join(cleaned) + ";" if cleaned else ""


def scan_workshop_mods(
    workshop_path: Path,
    server_path: Path | None = None
) -> list[tuple[str, str, str, int, bool, Optional[datetime]]]:
    """
    Scan workshop folder for mods.
    
    Returns: list of (workshop_id, mod_folder, version, size, is_installed, install_date)
    """
    items = []
    
    if not workshop_path.exists():
        return items
    
    # Get installed mods for status check
    installed_mods = {}
    if server_path and server_path.exists():
        for item in server_path.iterdir():
            if item.is_dir() and item.name.startswith("@"):
                version = get_mod_version(item)
                installed_mods[item.name.lower()] = version
    
    # Scan workshop structure (workshop_id/mod_folder pattern)
    found_any = False
    for id_dir in sorted([p for p in workshop_path.iterdir() if p.is_dir()]):
        workshop_id = id_dir.name
        mod_dirs = [p for p in id_dir.iterdir() if p.is_dir() and p.name.startswith("@")]
        if not mod_dirs:
            continue
        found_any = True
        for mod_dir in sorted(mod_dirs):
            version = get_mod_version(mod_dir)
            size = get_folder_size(mod_dir)
            is_installed = mod_dir.name.lower() in installed_mods
            install_date = get_mod_install_date(mod_dir)
            items.append((workshop_id, mod_dir.name, version, size, is_installed, install_date))
    
    # Fallback: direct @mod folders in workshop path
    if not found_any:
        for mod_dir in sorted([p for p in workshop_path.iterdir() if p.is_dir() and p.name.startswith("@")]):
            version = get_mod_version(mod_dir)
            size = get_folder_size(mod_dir)
            is_installed = mod_dir.name.lower() in installed_mods
            install_date = get_mod_install_date(mod_dir)
            items.append(("local", mod_dir.name, version, size, is_installed, install_date))
    
    return items


def scan_installed_mods(server_path: Path) -> list[tuple[str, str, int, bool, list[str], Optional[datetime]]]:
    """
    Scan server folder for installed mods.
    
    Returns: list of (mod_folder, version, size, has_bikey, bikey_names, install_date)
    """
    items = []
    
    if not server_path.exists():
        return items
    
    keys_folder = server_path / "keys"
    installed_bikeys = set()
    if keys_folder.exists():
        installed_bikeys = {f.name.lower() for f in keys_folder.glob("*.bikey")}
    
    for mod_dir in sorted([p for p in server_path.iterdir() if p.is_dir() and p.name.startswith("@")]):
        version = get_mod_version(mod_dir)
        size = get_folder_size(mod_dir)
        mod_bikeys = find_mod_bikeys(mod_dir)
        has_bikey = any(bk.lower() in installed_bikeys for bk in mod_bikeys) if mod_bikeys else False
        install_date = get_folder_install_date(mod_dir)
        items.append((mod_dir.name, version, size, has_bikey, mod_bikeys, install_date))
    
    return items
