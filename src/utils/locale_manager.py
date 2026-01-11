"""
Locale Manager - Multi-language Support System
Handles loading, switching, and retrieving localized strings.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from enum import Enum


class SupportedLanguage(Enum):
    """Enumeration of supported languages."""
    ENGLISH = "en"
    VIETNAMESE = "vi"


@dataclass
class LanguageInfo:
    """Information about a supported language."""
    code: str
    name: str
    native_name: str
    flag_emoji: str


# Language metadata
LANGUAGES: Dict[str, LanguageInfo] = {
    "en": LanguageInfo("en", "English", "English", "🇬🇧"),
    "vi": LanguageInfo("vi", "Vietnamese", "Tiếng Việt", "🇻🇳"),
}


class LocaleManager:
    """
    Manages application localization/internationalization.
    
    Features:
    - Load locale files from JSON
    - Switch languages at runtime
    - Nested key access (e.g., "mods.status_installed")
    - Placeholder substitution
    - Observer pattern for language change notifications
    
    Usage:
        locale = LocaleManager()
        locale.set_language("vi")
        text = locale.get("mods.install")  # Returns "Cài đặt"
        text = locale.get("errors.file_not_found", path="/some/path")
    """
    
    _instance: Optional['LocaleManager'] = None
    
    def __new__(cls, *args, **kwargs) -> 'LocaleManager':
        """Singleton pattern to ensure one locale manager across the app."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, locales_dir: Optional[str] = None, default_language: str = "en"):
        """
        Initialize the LocaleManager.
        
        Args:
            locales_dir: Directory containing locale JSON files.
                        Defaults to 'locales' folder relative to project root.
            default_language: Default language code (e.g., 'en', 'vi')
        """
        if self._initialized:
            return
            
        self._initialized = True
        
        # Determine locales directory
        if locales_dir:
            self._locales_dir = Path(locales_dir)
        else:
            # Default: locales folder in project root
            self._locales_dir = Path(__file__).parent.parent.parent / "locales"
        
        self._current_language: str = default_language
        self._fallback_language: str = "en"
        self._translations: Dict[str, Dict[str, Any]] = {}
        self._observers: List[Callable[[str], None]] = []
        
        # Load available translations
        self._load_all_translations()
        
    def _load_all_translations(self) -> None:
        """Load all available locale files."""
        if not self._locales_dir.exists():
            print(f"Warning: Locales directory not found: {self._locales_dir}")
            return
            
        for locale_file in self._locales_dir.glob("*.json"):
            lang_code = locale_file.stem
            try:
                with open(locale_file, 'r', encoding='utf-8') as f:
                    self._translations[lang_code] = json.load(f)
                print(f"Loaded locale: {lang_code}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading locale {lang_code}: {e}")
    
    def _load_translation(self, language: str) -> bool:
        """
        Load a specific translation file.
        
        Args:
            language: Language code to load
            
        Returns:
            True if successful, False otherwise
        """
        locale_file = self._locales_dir / f"{language}.json"
        
        if not locale_file.exists():
            print(f"Locale file not found: {locale_file}")
            return False
            
        try:
            with open(locale_file, 'r', encoding='utf-8') as f:
                self._translations[language] = json.load(f)
            return True
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading locale {language}: {e}")
            return False
    
    def get_available_languages(self) -> List[LanguageInfo]:
        """
        Get list of available languages.
        
        Returns:
            List of LanguageInfo for available locales
        """
        available = []
        for code in self._translations.keys():
            if code in LANGUAGES:
                available.append(LANGUAGES[code])
            else:
                # Unknown language - create basic info
                available.append(LanguageInfo(code, code.upper(), code.upper(), "🌐"))
        return available
    
    @property
    def current_language(self) -> str:
        """Get the current language code."""
        return self._current_language
    
    @property
    def current_language_info(self) -> LanguageInfo:
        """Get information about the current language."""
        return LANGUAGES.get(
            self._current_language,
            LanguageInfo(self._current_language, self._current_language, self._current_language, "🌐")
        )
    
    def set_language(self, language: str) -> bool:
        """
        Switch to a different language.
        
        Args:
            language: Language code to switch to
            
        Returns:
            True if switch was successful, False otherwise
        """
        if language not in self._translations:
            if not self._load_translation(language):
                print(f"Failed to switch to language: {language}")
                return False
        
        old_language = self._current_language
        self._current_language = language
        
        # Notify observers of language change
        if old_language != language:
            self._notify_observers(language)
        
        return True
    
    def get(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        """
        Get a translated string by key.
        
        Args:
            key: Dot-notation key (e.g., "mods.install", "common.save")
            default: Default value if key not found
            **kwargs: Placeholder values for string formatting
            
        Returns:
            Translated string with placeholders replaced
            
        Example:
            locale.get("errors.file_not_found", path="/some/path")
            # Returns "File not found: /some/path"
        """
        # Try current language first
        value = self._get_nested_value(self._current_language, key)
        
        # Fallback to default language
        if value is None and self._current_language != self._fallback_language:
            value = self._get_nested_value(self._fallback_language, key)
        
        # Use default or key itself
        if value is None:
            value = default if default is not None else key
        
        # Replace placeholders
        if kwargs and isinstance(value, str):
            try:
                # Support both {placeholder} and %(placeholder)s formats
                value = value.format(**kwargs)
            except KeyError:
                # Try Python-style formatting
                try:
                    value = value % kwargs
                except (KeyError, TypeError):
                    pass
        
        return value
    
    def _get_nested_value(self, language: str, key: str) -> Optional[str]:
        """
        Get a value from nested dictionary using dot notation.
        
        Args:
            language: Language code
            key: Dot-notation key (e.g., "mods.install")
            
        Returns:
            Value if found, None otherwise
        """
        if language not in self._translations:
            return None
            
        keys = key.split('.')
        value = self._translations[language]
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value if isinstance(value, str) else None
    
    def add_observer(self, callback: Callable[[str], None]) -> None:
        """
        Add an observer to be notified when language changes.
        
        Args:
            callback: Function to call with new language code
        """
        if callback not in self._observers:
            self._observers.append(callback)
    
    def remove_observer(self, callback: Callable[[str], None]) -> None:
        """
        Remove a language change observer.
        
        Args:
            callback: Previously registered callback
        """
        if callback in self._observers:
            self._observers.remove(callback)
    
    def _notify_observers(self, new_language: str) -> None:
        """Notify all observers of language change."""
        for callback in self._observers:
            try:
                callback(new_language)
            except Exception as e:
                print(f"Error in language change observer: {e}")
    
    def get_section(self, section: str) -> Dict[str, str]:
        """
        Get all translations in a section.
        
        Args:
            section: Section name (e.g., "common", "mods")
            
        Returns:
            Dictionary of translations in that section
        """
        if self._current_language in self._translations:
            translations = self._translations[self._current_language]
            if section in translations and isinstance(translations[section], dict):
                return translations[section].copy()
        return {}
    
    def reload(self) -> None:
        """Reload all translation files from disk."""
        self._translations.clear()
        self._load_all_translations()
        self._notify_observers(self._current_language)


# Convenience function for quick access
def tr(key: str, default: Optional[str] = None, **kwargs) -> str:
    """
    Shorthand function for getting translations.
    
    Usage:
        from src.utils.locale_manager import tr
        text = tr("mods.install")
    """
    return LocaleManager().get(key, default, **kwargs)


# Example usage and testing
if __name__ == "__main__":
    # Initialize locale manager
    locale = LocaleManager()
    
    print("=== Locale Manager Demo ===\n")
    
    # Show available languages
    print("Available languages:")
    for lang in locale.get_available_languages():
        print(f"  {lang.flag_emoji} {lang.code}: {lang.native_name}")
    
    print(f"\nCurrent language: {locale.current_language}")
    
    # Test English translations
    print("\n--- English ---")
    print(f"App name: {locale.get('app.name')}")
    print(f"Save button: {locale.get('common.save')}")
    print(f"Install mod: {locale.get('mods.install')}")
    print(f"Error message: {locale.get('errors.file_not_found', path='/test/file.txt')}")
    
    # Switch to Vietnamese
    locale.set_language("vi")
    print(f"\n--- Vietnamese (Tiếng Việt) ---")
    print(f"App name: {locale.get('app.name')}")
    print(f"Save button: {locale.get('common.save')}")
    print(f"Install mod: {locale.get('mods.install')}")
    print(f"Error message: {locale.get('errors.file_not_found', path='/test/file.txt')}")
    
    # Test shorthand function
    print(f"\nUsing tr() shorthand: {tr('common.cancel')}")
    
    # Test missing key fallback
    print(f"\nMissing key fallback: {locale.get('nonexistent.key', default='Default Value')}")
