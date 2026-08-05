import sqlite3
from pathlib import Path

# Path to the db folder
DB_FOLDER = Path(__file__).parent

# Files
SCHEMA_FILE = DB_FOLDER / "schema.sql"
SEED_FILE = DB_FOLDER / "seed.sql"
DATABASE_FILE = DB_FOLDER / "copperleaf.db"


def initialize_database():
    # Create (or open) the SQLite database
    connection = sqlite3.connect(DATABASE_FILE)
    cursor = connection.cursor()

    # Execute schema.sql
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        cursor.executescript(f.read())

    # Execute seed.sql
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        cursor.executescript(f.read())

    connection.commit()
    connection.close()

    print("✅ Copperleaf database created successfully!")
    print(f"Database location: {DATABASE_FILE}")


if __name__ == "__main__":
    initialize_database()