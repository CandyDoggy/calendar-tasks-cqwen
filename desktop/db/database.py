"""
Database layer for Calendar & Tasks app.
Uses SQLite for local storage.
"""

import sqlite3
import os
import json
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendar_tasks.db")


def get_db_path():
    return DB_PATH


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate_google_tokens(conn):
    """
    Migration: If google_token or microsoft_token columns exist but are TEXT,
    they can already store JSON. This migration just adds columns if missing
    and ensures compatibility.
    """
    cursor = conn.cursor()

    # Check if google_token column exists
    columns = [row['name'] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]

    if 'google_token' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN google_token TEXT")

    if 'microsoft_token' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN microsoft_token TEXT")

    # Ensure events have source and external_id columns
    event_columns = [row['name'] for row in cursor.execute("PRAGMA table_info(events)").fetchall()]
    if 'source' not in event_columns:
        cursor.execute("ALTER TABLE events ADD COLUMN source TEXT DEFAULT 'local'")
    if 'external_id' not in event_columns:
        cursor.execute("ALTER TABLE events ADD COLUMN external_id TEXT")

    # Ensure tasks have source and external_id columns
    task_columns = [row['name'] for row in cursor.execute("PRAGMA table_info(tasks)").fetchall()]
    if 'source' not in task_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN source TEXT DEFAULT 'local'")
    if 'external_id' not in task_columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN external_id TEXT")

    # Ensure notes have source and external_id columns
    note_columns = [row['name'] for row in cursor.execute("PRAGMA table_info(notes)").fetchall()]
    if 'source' not in note_columns:
        cursor.execute("ALTER TABLE notes ADD COLUMN source TEXT DEFAULT 'local'")
    if 'external_id' not in note_columns:
        cursor.execute("ALTER TABLE notes ADD COLUMN external_id TEXT")


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                display_name TEXT,
                auth_provider TEXT DEFAULT 'local',
                google_token TEXT,
                microsoft_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                location TEXT,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                is_all_day BOOLEAN DEFAULT 0,
                color TEXT DEFAULT '#60cdff',
                recurrence TEXT,
                reminder_minutes INTEGER DEFAULT 15,
                source TEXT DEFAULT 'local',
                external_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_date TIMESTAMP,
                priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                category TEXT,
                source TEXT DEFAULT 'local',
                external_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Notes table (Google Keep style)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT,
                content TEXT,
                color TEXT DEFAULT '#ffffff',
                pinned BOOLEAN DEFAULT 0,
                source TEXT DEFAULT 'local',
                external_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Mail/Sent messages log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_mail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                to_address TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                provider TEXT DEFAULT 'gmail',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                theme TEXT DEFAULT 'dark',
                default_view TEXT DEFAULT 'month',
                week_start INTEGER DEFAULT 0,
                notifications_enabled BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Run migrations for existing tables
        _migrate_google_tokens(conn)

        print("Database initialized successfully")


if __name__ == "__main__":
    init_db()
