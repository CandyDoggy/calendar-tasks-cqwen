#!/usr/bin/env python3
"""
Calendar & Tasks - Desktop Application

Usage:
  python main.py              # Run UI only
  python api/server.py        # Run API server separately
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []
    try:
        import customtkinter
    except ImportError:
        missing.append("customtkinter")
    try:
        import flask
    except ImportError:
        missing.append("flask")

    if missing:
        print("=" * 50)
        print("Missing dependencies:")
        for pkg in missing:
            print(f"  - {pkg}")
        print("=" * 50)
        print("\nTo install, run:")
        print("  pip install -r requirements.txt")
        return False
    return True


def main():
    """Main entry point."""
    if not check_dependencies():
        sys.exit(1)

    print("Starting Calendar & Tasks...")

    # Initialize database
    from db.database import init_db
    init_db()

    # Start UI
    from ui.main_ui import run_calendar_tasks
    run_calendar_tasks()


if __name__ == "__main__":
    main()
