# db_supabase.py
import os
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("Переменная DATABASE_URL не задана")

    result = urlparse(database_url)
    conn = psycopg2.connect(
        host=result.hostname,
        port=result.port or 5432,
        database=result.path[1:],
        user=result.username,
        password=result.password,
        cursor_factory=RealDictCursor
    )
    return conn

def _get_title_hash(title: str) -> str:
    return hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()

def is_seen(link: str, title: str) -> bool:
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        title_hash = _get_title_hash(title)
        cur.execute(
            "SELECT 1 FROM seen_items WHERE link = %s OR title_hash = %s",
            (link, title_hash)
        )
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"Ошибка при проверке seen: {e}")
        return False

def mark_seen(link: str, title: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        title_hash = _get_title_hash(title)
        cur.execute(
            "INSERT INTO seen_items (link, title_hash) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (link, title_hash)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при сохранении seen: {e}")
