import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "copperleaf.db"


def execute_query(query: str, params: tuple = ()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    cursor.execute(query, params)

    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]


def execute_update(query: str, params: tuple = ()):
    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()
    cursor.execute(query, params)

    conn.commit()

    affected = cursor.rowcount

    conn.close()

    return affected