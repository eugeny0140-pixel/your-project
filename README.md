# Telegram News Bot с Supabase

Бот для мониторинга RSS и HTML-источников, фильтрации по ключевым словам и отправки новостей в Telegram канал.

## Настройка

1. Создайте проект в [Supabase](https://supabase.com)
2. Создайте таблицу `seen_items`:
   ```sql
   CREATE TABLE seen_items (
       id SERIAL PRIMARY KEY,
       link TEXT UNIQUE NOT NULL,
       title_hash TEXT UNIQUE,
       created_at TIMESTAMP DEFAULT NOW()
   );
   CREATE INDEX idx_seen_link ON seen_items(link);
   CREATE INDEX idx_seen_title_hash ON seen_items(title_hash);
