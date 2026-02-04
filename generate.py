#!/usr/bin/env python3
"""
Main entry point for wallpaper generation.

Usage:
    python generate.py                      # Generate for today
    python generate.py --date 2024-02-14    # Generate for specific date
    python generate.py --help               # Show all options
"""
from src.orchestrator import main

if __name__ == "__main__":
    main()
