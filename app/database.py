import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "videos.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            channel TEXT DEFAULT 'Usuario',
            duration TEXT DEFAULT '0:00',
            views INTEGER DEFAULT 0,
            video_filename TEXT NOT NULL,
            thumbnail_filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
