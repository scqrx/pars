from pathlib import Path
import sqlite3
from typing import List, Tuple, Optional

DB_PATH = Path("bot.db")


def _get_connection() -> sqlite3.Connection:
    # check_same_thread=False — чтобы можно было дергать из разных обработчиков
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db() -> None:
    """Создаём таблицу, если её ещё нет."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                last_price INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def add_subscription(
    user_id: int, url: str, title: Optional[str], last_price: Optional[int]
) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO subscriptions (user_id, url, title, last_price)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, url, title, last_price),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_subscriptions(
    user_id: int,
) -> List[Tuple[int, str, Optional[str], Optional[int]]]:
    """Список подписок конкретного пользователя."""
    conn = _get_connection()
    try:
        cur = conn.execute(
            "SELECT id, url, title, last_price "
            "FROM subscriptions WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
        return list(cur.fetchall())
    finally:
        conn.close()


def get_all_subscriptions() -> List[Tuple[int, int, str, Optional[str], Optional[int]]]:
    """Все подписки (для фоновой проверки цен)."""
    conn = _get_connection()
    try:
        cur = conn.execute(
            "SELECT id, user_id, url, title, last_price "
            "FROM subscriptions ORDER BY id"
        )
        return list(cur.fetchall())
    finally:
        conn.close()


def update_subscription(
    sub_id: int, *, title: Optional[str] = None, last_price: Optional[int] = None
) -> None:
    """Обновить название и/или цену подписки."""
    if title is None and last_price is None:
        return

    conn = _get_connection()
    try:
        if title is not None and last_price is not None:
            conn.execute(
                """
                UPDATE subscriptions
                SET title = ?, last_price = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, last_price, sub_id),
            )
        elif title is not None:
            conn.execute(
                """
                UPDATE subscriptions
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, sub_id),
            )
        elif last_price is not None:
            conn.execute(
                """
                UPDATE subscriptions
                SET last_price = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (last_price, sub_id),
            )
        conn.commit()
    finally:
        conn.close()
