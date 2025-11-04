# db_supabase.py
import os
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
import logging

log = logging.getLogger(__name__)

def get_db_connection():
    """
    Создает подключение к базе данных Supabase
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("Переменная DATABASE_URL не задана")

    try:
        result = urlparse(database_url)
        conn = psycopg2.connect(
            host=result.hostname,
            port=result.port or 5432,
            database=result.path[1:],
            user=result.username,
            password=result.password,
            cursor_factory=RealDictCursor,
            connect_timeout=10
        )
        return conn
    except Exception as e:
        log.error(f"❌ Ошибка подключения к базе данных: {e}")
        raise

def _get_title_hash(title: str) -> str:
    """
    Создает хеш из заголовка для дедупликации
    """
    return hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()

def is_seen(link: str, title: str) -> bool:
    """
    Проверяет, была ли уже отправлена новость с таким URL или заголовком
    """
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
        log.error(f"❌ Ошибка при проверке seen_items: {e}")
        # В случае ошибки БД считаем, что новость не отправлялась
        return False

def mark_seen(link: str, title: str):
    """
    Помечает новость как отправленную в базе данных
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        title_hash = _get_title_hash(title)
        
        cur.execute(
            "INSERT INTO seen_items (link, title_hash) VALUES (%s, %s) ON CONFLICT (link) DO NOTHING",
            (link, title_hash)
        )
        conn.commit()
        
        cur.close()
        conn.close()
        
        log.debug(f"✅ Новость сохранена в БД: {link}")
    except Exception as e:
        log.error(f"❌ Ошибка при сохранении в seen_items: {e}")
