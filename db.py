import sqlite3

# Подключение к базе данных (файл будет создан автоматически)
conn = sqlite3.connect("bot_data.db")
cursor = conn.cursor()

# Таблица для премиум-пользователей
cursor.execute("""
CREATE TABLE IF NOT EXISTS premium_users (
    user_id INTEGER PRIMARY KEY
)
""")

# Таблица для подсчёта использования
cursor.execute("""
CREATE TABLE IF NOT EXISTS usage_count (
    user_id INTEGER PRIMARY KEY,
    count INTEGER DEFAULT 0
)
""")

conn.commit()
