#!/usr/bin/env python3
"""
Version Update Script
Demonstrates how to update application version centrally.
"""

from src.core.app_config import AppConfigManager

def main():
    """Update application version."""
    config = AppConfigManager()

    print("Current version:", config.version)
    print("Current name:", config.name)
    print("Current author:", config.author)

    # Example: Update version
    new_version = input("Enter new version (current: {}): ".format(config.version))
    if new_version and new_version != config.version:
        config.set_version(new_version)
        print(f"Version updated to: {new_version}")
    else:
        print("Version not changed")

    # Example: Update author
    new_author = input("Enter new author (current: {}): ".format(config.author))
    if new_author and new_author != config.author:
        config.set_author(new_author)
        print(f"Author updated to: {new_author}")
    else:
        print("Author not changed")

    print("\nAll changes saved to configs/app.json")

if __name__ == "__main__":
    main()