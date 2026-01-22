"""
Mod Integrity Checker
Verifies the installation status and integrity of DayZ mods.
"""

import os
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Set, Tuple, Callable
from dataclasses import dataclass
import logging

from ..models.mod_models import (
    ModInfo, ModStatus, BikeyInfo, 
    IntegrityReport, IntegrityIssue, IntegrityStatus
)
from features.profiles.models.profile_models import ServerProfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModIntegrityChecker:
    """
    Checks and verifies the integrity of DayZ mod installations.
    
    Features:
    - Verify mod folder existence
    - Check bikey file presence in server keys folder
    - Detect duplicate mods
    - Smart installation (only copy missing components)
    - Generate integrity reports
    
    Usage:
        checker = ModIntegrityChecker(server_path, keys_folder, workshop_path)
        report = checker.check_all_mods()
        
        # Or check specific mod
        mod_info = checker.check_mod("@CF")
        
        # Install missing components
        checker.smart_install_mod("@CF")
    """
    
    def __init__(
        self,
        server_path: str | Path,
        keys_folder: Optional[str | Path] = None,
        workshop_path: Optional[str | Path] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ):
        """
        Initialize the Mod Integrity Checker.
        
        Args:
            server_path: Path to DayZ server root directory
            keys_folder: Path to server's keys folder (default: server_path/keys)
            workshop_path: Path to Steam Workshop content folder
            progress_callback: Optional callback(message, current, total) for progress updates
        """
        self.server_path = Path(server_path)
        self.keys_folder = Path(keys_folder) if keys_folder else self.server_path / "keys"
        self.workshop_path = Path(workshop_path) if workshop_path else None
        self.progress_callback = progress_callback
        
        # Validate paths
        if not self.server_path.exists():
            raise ValueError(f"Server path does not exist: {self.server_path}")
        
        # Create keys folder if it doesn't exist
        self.keys_folder.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_profile(cls, profile: ServerProfile, workshop_path: Optional[Path] = None) -> 'ModIntegrityChecker':
        """Create checker from a ServerProfile."""
        return cls(
            server_path=profile.server_path,
            keys_folder=profile.keys_folder,
            workshop_path=workshop_path
        )
    
    def _report_progress(self, message: str, current: int, total: int) -> None:
        """Report progress to callback if available."""
        if self.progress_callback:
            self.progress_callback(message, current, total)
        logger.info(f"[{current}/{total}] {message}")
    
    def get_installed_mods(self) -> List[str]:
        """
        Get list of installed mod folders (starting with @).
        
        Returns:
            List of mod folder names
        """
        mods = []
        for item in self.server_path.iterdir():
            if item.is_dir() and item.name.startswith("@"):
                mods.append(item.name)
        return sorted(mods)
    
    def get_installed_bikeys(self) -> Dict[str, Path]:
        """
        Get all .bikey files in the keys folder.
        
        Returns:
            Dictionary mapping bikey name to path
        """
        bikeys = {}
        if self.keys_folder.exists():
            for item in self.keys_folder.iterdir():
                if item.suffix.lower() == ".bikey":
                    bikeys[item.name] = item
        return bikeys
    
    def find_bikeys_in_mod(self, mod_path: Path) -> List[BikeyInfo]:
        """
        Find all .bikey files within a mod folder.
        
        Args:
            mod_path: Path to the mod folder
            
        Returns:
            List of BikeyInfo objects
        """
        bikeys = []
        
        # Common locations for bikeys
        search_paths = [
            mod_path / "keys",
            mod_path / "Keys",
            mod_path / "key",
            mod_path / "Key",
            mod_path,  # Sometimes bikeys are in root
        ]
        
        # Also search recursively but limit depth
        searched = set()
        
        for search_path in search_paths:
            if search_path.exists() and search_path not in searched:
                searched.add(search_path)
                for bikey_file in search_path.glob("*.bikey"):
                    stat = bikey_file.stat()
                    bikeys.append(BikeyInfo(
                        name=bikey_file.name,
                        path=bikey_file,
                        size=stat.st_size,
                        modified_date=datetime.fromtimestamp(stat.st_mtime)
                    ))
        
        # Deep search if nothing found (some mods have nested structures)
        if not bikeys:
            for bikey_file in mod_path.rglob("*.bikey"):
                stat = bikey_file.stat()
                bikeys.append(BikeyInfo(
                    name=bikey_file.name,
                    path=bikey_file,
                    size=stat.st_size,
                    modified_date=datetime.fromtimestamp(stat.st_mtime)
                ))
        
        return bikeys
    
    def check_mod(self, mod_name: str, source_path: Optional[Path] = None) -> ModInfo:
        """
        Check the installation status of a specific mod.
        
        Args:
            mod_name: Name of the mod folder (e.g., "@CF")
            source_path: Optional source path for the mod (Workshop location)
            
        Returns:
            ModInfo with complete status information
        """
        mod_info = ModInfo(name=mod_name, source_path=source_path)
        
        # Normalize mod name
        if not mod_name.startswith("@"):
            mod_name = f"@{mod_name}"
        
        installed_path = self.server_path / mod_name
        mod_info.installed_path = installed_path
        
        # Check if mod folder exists
        folder_exists = installed_path.exists() and installed_path.is_dir()
        
        # Find bikeys in the mod folder (either installed or source)
        mod_bikeys: List[BikeyInfo] = []
        if folder_exists:
            mod_bikeys = self.find_bikeys_in_mod(installed_path)
        elif source_path and source_path.exists():
            mod_bikeys = self.find_bikeys_in_mod(source_path)
        
        mod_info.bikeys = mod_bikeys
        
        # Check if bikeys are installed in server keys folder
        installed_bikeys = self.get_installed_bikeys()
        bikeys_installed = False
        
        if mod_bikeys:
            bikeys_installed = any(
                bikey.name in installed_bikeys 
                for bikey in mod_bikeys
            )
        
        # Determine status
        if folder_exists and bikeys_installed:
            mod_info.status = ModStatus.FULLY_INSTALLED
        elif folder_exists and not bikeys_installed:
            mod_info.status = ModStatus.PARTIAL_FOLDER_ONLY
        elif not folder_exists and bikeys_installed:
            mod_info.status = ModStatus.PARTIAL_BIKEY_ONLY
        else:
            mod_info.status = ModStatus.NOT_INSTALLED
        
        # Get additional info if folder exists
        if folder_exists:
            mod_info.file_count = sum(1 for _ in installed_path.rglob("*") if _.is_file())
            mod_info.size_bytes = sum(f.stat().st_size for f in installed_path.rglob("*") if f.is_file())
            
            # Try to get last modified date
            try:
                mod_info.last_updated = datetime.fromtimestamp(installed_path.stat().st_mtime)
            except:
                pass
        
        return mod_info
    
    def check_all_mods(self, mod_list: Optional[List[str]] = None) -> IntegrityReport:
        """
        Check integrity of all mods (or specified list).
        
        Args:
            mod_list: Optional list of mod names to check. 
                     If None, checks all installed mods.
                     
        Returns:
            IntegrityReport with complete results
        """
        report = IntegrityReport(
            timestamp=datetime.now(),
            server_path=self.server_path
        )
        
        # Get mods to check
        if mod_list is None:
            mod_list = self.get_installed_mods()
        
        total = len(mod_list)
        report.total_mods_checked = total
        
        # Track bikeys for duplicate detection
        bikey_sources: Dict[str, List[str]] = {}  # bikey_name -> [mod_names]
        
        for idx, mod_name in enumerate(mod_list):
            self._report_progress(f"Checking {mod_name}...", idx + 1, total)
            
            mod_info = self.check_mod(mod_name)
            report.mods.append(mod_info)
            
            # Count by status
            if mod_info.status == ModStatus.FULLY_INSTALLED:
                report.fully_installed += 1
            elif mod_info.status in [ModStatus.PARTIAL_FOLDER_ONLY, ModStatus.PARTIAL_BIKEY_ONLY]:
                report.partial_installed += 1
                
                # Add issue for partial installation
                if mod_info.status == ModStatus.PARTIAL_FOLDER_ONLY:
                    report.issues.append(IntegrityIssue(
                        severity=IntegrityStatus.WARNING,
                        category="bikey",
                        message=f"Mod '{mod_name}' is missing .bikey file(s) in server keys folder",
                        mod_name=mod_name,
                        suggestion="Copy .bikey files from mod's keys folder to server keys folder"
                    ))
                else:
                    report.issues.append(IntegrityIssue(
                        severity=IntegrityStatus.FAILED,
                        category="folder",
                        message=f"Mod '{mod_name}' has bikey but mod folder is missing",
                        mod_name=mod_name,
                        suggestion="Install the mod folder from Workshop"
                    ))
            elif mod_info.status == ModStatus.NOT_INSTALLED:
                report.missing += 1
            elif mod_info.status == ModStatus.CORRUPTED:
                report.corrupted += 1
                report.issues.append(IntegrityIssue(
                    severity=IntegrityStatus.FAILED,
                    category="corruption",
                    message=f"Mod '{mod_name}' appears to be corrupted",
                    mod_name=mod_name,
                    suggestion="Reinstall the mod from Workshop"
                ))
            
            # Track bikeys for duplicate detection
            for bikey in mod_info.bikeys:
                if bikey.name not in bikey_sources:
                    bikey_sources[bikey.name] = []
                bikey_sources[bikey.name].append(mod_name)
        
        # Check for duplicate bikeys (same bikey from multiple mods)
        for bikey_name, sources in bikey_sources.items():
            if len(sources) > 1:
                report.issues.append(IntegrityIssue(
                    severity=IntegrityStatus.WARNING,
                    category="duplicate",
                    message=f"Bikey '{bikey_name}' found in multiple mods: {', '.join(sources)}",
                    suggestion="This may indicate duplicate mods or shared dependencies"
                ))
        
        return report
    
    def check_server_integrity(self) -> IntegrityReport:
        """
        Check overall server integrity including critical files.
        
        Returns:
            IntegrityReport including server file checks
        """
        report = self.check_all_mods()
        
        # Check for critical server files
        critical_files = [
            ("DayZServer_x64.exe", "Server executable"),
            ("serverDZ.cfg", "Server configuration"),
        ]
        
        for filename, description in critical_files:
            file_path = self.server_path / filename
            if not file_path.exists():
                report.issues.append(IntegrityIssue(
                    severity=IntegrityStatus.FAILED,
                    category="server",
                    message=f"Critical file missing: {description} ({filename})",
                    file_path=file_path,
                    suggestion=f"Ensure {filename} exists in the server directory"
                ))
        
        # Check keys folder
        if not self.keys_folder.exists():
            report.issues.append(IntegrityIssue(
                severity=IntegrityStatus.WARNING,
                category="server",
                message="Keys folder does not exist",
                file_path=self.keys_folder,
                suggestion="Create the keys folder in the server directory"
            ))
        
        return report
    
    def smart_install_mod(
        self, 
        mod_name: str, 
        source_path: Path,
        copy_bikeys: bool = True,
        overwrite: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Smart install - only copy missing components.
        
        Args:
            mod_name: Name of the mod (e.g., "@CF")
            source_path: Source path to copy from (Workshop location)
            copy_bikeys: Whether to copy bikey files
            overwrite: Whether to overwrite existing files
            
        Returns:
            Tuple of (success, list of actions taken)
        """
        actions = []
        
        if not mod_name.startswith("@"):
            mod_name = f"@{mod_name}"
        
        if not source_path.exists():
            return False, [f"Source path does not exist: {source_path}"]
        
        # Check current status
        mod_info = self.check_mod(mod_name, source_path)
        dest_path = self.server_path / mod_name
        
        try:
            # Copy mod folder if needed
            if mod_info.needs_folder or overwrite:
                if dest_path.exists() and overwrite:
                    shutil.rmtree(dest_path)
                    actions.append(f"Removed existing mod folder: {mod_name}")
                
                if not dest_path.exists():
                    shutil.copytree(source_path, dest_path)
                    actions.append(f"Copied mod folder: {mod_name}")
            else:
                actions.append(f"Mod folder already exists: {mod_name}")
            
            # Copy bikeys if needed
            if copy_bikeys:
                bikeys_copied = self._copy_bikeys(mod_name, source_path if mod_info.needs_folder else dest_path)
                if bikeys_copied:
                    actions.extend([f"Copied bikey: {bk}" for bk in bikeys_copied])
                else:
                    actions.append("No bikeys to copy or all bikeys already installed")
            
            return True, actions
            
        except Exception as e:
            logger.error(f"Error installing mod {mod_name}: {e}")
            return False, actions + [f"Error: {str(e)}"]
    
    def _copy_bikeys(self, mod_name: str, mod_path: Path) -> List[str]:
        """
        Copy bikey files from mod to server keys folder.
        
        Args:
            mod_name: Name of the mod
            mod_path: Path to the mod folder
            
        Returns:
            List of bikey filenames that were copied
        """
        copied = []
        bikeys = self.find_bikeys_in_mod(mod_path)
        installed_bikeys = self.get_installed_bikeys()
        
        for bikey in bikeys:
            if bikey.name not in installed_bikeys:
                dest = self.keys_folder / bikey.name
                try:
                    shutil.copy2(bikey.path, dest)
                    copied.append(bikey.name)
                    logger.info(f"Copied bikey: {bikey.name}")
                except Exception as e:
                    logger.error(f"Failed to copy bikey {bikey.name}: {e}")
        
        return copied
    
    def extract_all_bikeys(self) -> Tuple[int, List[str]]:
        """
        Extract and copy all bikeys from installed mods to keys folder.
        
        Returns:
            Tuple of (count of bikeys copied, list of bikey names)
        """
        all_copied = []
        
        for mod_name in self.get_installed_mods():
            mod_path = self.server_path / mod_name
            copied = self._copy_bikeys(mod_name, mod_path)
            all_copied.extend(copied)
        
        return len(all_copied), all_copied
    
    def find_duplicates(self) -> Dict[str, List[str]]:
        """
        Find duplicate mods (same Workshop ID or similar names).
        
        Returns:
            Dictionary mapping potential duplicate identifier to list of mod names
        """
        duplicates: Dict[str, List[str]] = {}
        mods = self.get_installed_mods()
        
        # Simple name-based duplicate detection
        # (could be enhanced with Workshop ID checking)
        normalized_names: Dict[str, List[str]] = {}
        
        for mod in mods:
            # Normalize: lowercase, remove @ and common suffixes
            normalized = mod.lower().replace("@", "").strip()
            # Remove version suffixes like _v1, -v2, etc.
            for suffix in ["_v1", "_v2", "-v1", "-v2", "_latest", "-latest"]:
                normalized = normalized.replace(suffix, "")
            
            if normalized not in normalized_names:
                normalized_names[normalized] = []
            normalized_names[normalized].append(mod)
        
        # Find actual duplicates
        for normalized, mod_list in normalized_names.items():
            if len(mod_list) > 1:
                duplicates[normalized] = mod_list
        
        return duplicates
    
    def generate_report_text(self, report: IntegrityReport) -> str:
        """
        Generate a human-readable text report.
        
        Args:
            report: IntegrityReport to format
            
        Returns:
            Formatted text report
        """
        lines = [
            "=" * 60,
            "DayZ Mod Integrity Report",
            "=" * 60,
            f"Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Server Path: {report.server_path}",
            "",
            "Summary:",
            f"  Total Mods Checked: {report.total_mods_checked}",
            f"  Fully Installed: {report.fully_installed}",
            f"  Partially Installed: {report.partial_installed}",
            f"  Missing: {report.missing}",
            f"  Corrupted: {report.corrupted}",
            f"  Overall Status: {report.status.value.upper()}",
            "",
        ]
        
        if report.issues:
            lines.append("Issues Found:")
            lines.append("-" * 40)
            for issue in report.issues:
                icon = "❌" if issue.severity == IntegrityStatus.FAILED else "⚠️"
                lines.append(f"  {icon} [{issue.category.upper()}] {issue.message}")
                if issue.suggestion:
                    lines.append(f"     💡 Suggestion: {issue.suggestion}")
            lines.append("")
        
        lines.append("Mod Details:")
        lines.append("-" * 40)
        for mod in report.mods:
            status_icon = {
                ModStatus.FULLY_INSTALLED: "✅",
                ModStatus.PARTIAL_FOLDER_ONLY: "⚠️",
                ModStatus.PARTIAL_BIKEY_ONLY: "⚠️",
                ModStatus.NOT_INSTALLED: "❌",
                ModStatus.CORRUPTED: "💔",
                ModStatus.OUTDATED: "🔄"
            }.get(mod.status, "❓")
            
            lines.append(f"  {status_icon} {mod.name}")
            lines.append(f"      Status: {mod.status.value}")
            if mod.bikeys:
                lines.append(f"      Bikeys: {', '.join(bk.name for bk in mod.bikeys)}")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Example usage and testing
if __name__ == "__main__":
    print("=== Mod Integrity Checker Demo ===\n")
    
    # This would normally use real paths
    # Example: checker = ModIntegrityChecker("C:/DayZServer", workshop_path="C:/Steam/steamapps/workshop/content/221100")
    
    print("Usage example:")
    print("""
    from features.mods.core.mod_integrity import ModIntegrityChecker
    
    # Initialize checker
    checker = ModIntegrityChecker(
        server_path="C:/DayZServer",
        workshop_path="C:/Steam/steamapps/workshop/content/221100"
    )
    
    # Check all mods
    report = checker.check_all_mods()
    
    # Print report
    print(checker.generate_report_text(report))
    
    # Check specific mod
    mod_info = checker.check_mod("@CF")
    print(f"Mod: {mod_info.name}, Status: {mod_info.status}")
    
    # Smart install (only copy missing components)
    success, actions = checker.smart_install_mod(
        "@CF",
        source_path=Path("C:/Steam/steamapps/workshop/content/221100/123456789")
    )
    
    # Extract all bikeys
    count, bikeys = checker.extract_all_bikeys()
    print(f"Extracted {count} bikeys")
    
    # Find duplicate mods
    duplicates = checker.find_duplicates()
    if duplicates:
        print("Duplicate mods found:", duplicates)
    """)
