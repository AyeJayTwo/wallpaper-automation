#!/usr/bin/env python3
"""
Delivery script for iOS Shortcuts integration.

This script copies the latest wallpaper to a location accessible by iOS Shortcuts.
Options:
1. iCloud Drive (syncs to iPhone automatically)
2. Local folder that Shortcuts can access via "Get File" action
"""
import argparse
import shutil
import sys
from pathlib import Path

# Default paths
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
LATEST_WALLPAPER = OUTPUT_DIR / "latest.png"

# iCloud Drive path on macOS (adjust if needed)
ICLOUD_SHORTCUTS_DIR = Path.home() / "Library/Mobile Documents/iCloud~is~workflow~my~workflows/Documents/Wallpapers"


def deliver_to_icloud(source: Path, dest_dir: Path = ICLOUD_SHORTCUTS_DIR) -> Path:
    """Copy wallpaper to iCloud Drive for Shortcuts access."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "calendar_wallpaper.png"

    shutil.copy2(source, dest_path)
    print(f"Delivered to iCloud: {dest_path}")
    return dest_path


def deliver_to_local(source: Path, dest_dir: Path) -> Path:
    """Copy wallpaper to a local directory."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "calendar_wallpaper.png"

    shutil.copy2(source, dest_path)
    print(f"Delivered to: {dest_path}")
    return dest_path


def main():
    parser = argparse.ArgumentParser(
        description="Deliver wallpaper for iOS Shortcuts"
    )
    parser.add_argument(
        '--source',
        type=str,
        default=str(LATEST_WALLPAPER),
        help='Source wallpaper path (default: output/latest.png)'
    )
    parser.add_argument(
        '--dest',
        type=str,
        help='Destination directory (default: iCloud Shortcuts folder)'
    )
    parser.add_argument(
        '--icloud',
        action='store_true',
        help='Deliver to iCloud Drive Shortcuts folder'
    )

    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"Error: Source file not found: {source}", file=sys.stderr)
        print("Run 'python generate.py' first to create a wallpaper.", file=sys.stderr)
        sys.exit(1)

    if args.dest:
        deliver_to_local(source, Path(args.dest))
    elif args.icloud:
        deliver_to_icloud(source)
    else:
        # Default: try iCloud, fall back to local
        try:
            deliver_to_icloud(source)
        except Exception as e:
            print(f"iCloud delivery failed: {e}", file=sys.stderr)
            # Fall back to Documents folder
            fallback = Path.home() / "Documents/Wallpapers"
            deliver_to_local(source, fallback)


if __name__ == "__main__":
    main()
