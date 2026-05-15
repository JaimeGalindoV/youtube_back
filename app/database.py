import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT', '5432'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
    )
    conn.cursor_factory = RealDictCursor
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id SERIAL PRIMARY KEY,
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
    cur.close()
    conn.close()