#!/usr/bin/env python3
"""
Version Update Script
Demonstrates how to update application version centrally.
"""

from shared.core.app_config import AppConfigManager

def main():
    """Update application version."""
    config = AppConfigManager()

    print("Current version:", config.version)
    print("Current name:", config.name)
    print("Current author:", config.author)

    # Example: Update version
    new_version = input("Enter new version (current: {}): ".format(config.version))
    if new_version and new_version != config.version:
        print(f"To update version to {new_version}, manually edit configs/app.json")
    else:
        print("Version not changed")

    # Example: Update author
    new_author = input("Enter new author (current: {}): ".format(config.author))
    if new_author and new_author != config.author:
        print(f"To update author to {new_author}, manually edit configs/app.json")
    else:
        print("Author not changed")

    print("\nApp config is read-only. Edit configs/app.json manually to make changes.")

if __name__ == "__main__":
    main()
