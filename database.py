import sqlite3
from datetime import datetime

DB_FILE = "expenses.db"   # the filing cabinet, saved next to your code


def connect():
    return sqlite3.connect(DB_FILE)


def setup_database():
    """Creates the expenses table (the list) if it doesn't exist yet."""
    db = connect()
    db.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            merchant TEXT NOT NULL,
            category TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    db.commit()
    db.close()


def add_expense(user_id, amount, merchant, category):
    """Saves one expense. user_id keeps each person's data separate."""
    db = connect()
    db.execute(
        "INSERT INTO expenses (user_id, amount, merchant, category, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, merchant, category,
         datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    db.close()


def get_last_expense(user_id):
    """Returns (amount, merchant, category, created_at) or None."""
    db = connect()
    row = db.execute(
        "SELECT amount, merchant, category, created_at FROM expenses "
        "WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    db.close()
    return row


def delete_last_expense(user_id):
    """Deletes the newest expense and returns (amount, merchant), or None."""
    db = connect()
    row = db.execute(
        "SELECT id, amount, merchant FROM expenses "
        "WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row is not None:
        db.execute("DELETE FROM expenses WHERE id = ?", (row[0],))
        db.commit()
    db.close()
    return None if row is None else (row[1], row[2])