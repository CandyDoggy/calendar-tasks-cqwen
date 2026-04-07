#!/usr/bin/env python3
"""
Calendar & Tasks - Desktop Application

Starts both the Flask API server and the CustomTkinter UI.
"""

import sys
import os
import subprocess
import time
import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_dependencies():
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


def start_api_server():
    """Start Flask API server as a subprocess."""
    api_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api", "server.py")
    proc = subprocess.Popen(
        [sys.executable, api_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for server to be ready
    import requests
    for _ in range(30):
        try:
            r = requests.get("http://localhost:5000/", timeout=1)
            if r.status_code < 500:
                return proc
        except Exception:
            pass
        time.sleep(0.5)
    print("Warning: API server may not have started properly")
    return proc


def cleanup(api_proc, ui_proc):
    """Clean up subprocesses on exit."""
    for proc in [api_proc, ui_proc]:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                proc.kill()


def main():
    if not check_dependencies():
        sys.exit(1)

    print("Starting Calendar & Tasks...")

    # Initialize database
    from db.database import init_db
    init_db()

    # Start API server
    print("Starting API server on http://localhost:5000 ...")
    api_proc = start_api_server()
    print("API server ready.")

    # Start UI
    from ui.main_ui import run_calendar_tasks
    try:
        run_calendar_tasks()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        cleanup(api_proc, None)
        sys.exit(0)


if __name__ == "__main__":
    main()
