import sqlite3
import pandas as pd
from pathlib import Path
from cleaner import load_validated_data, clean_data

DB_PATH = Path(__file__).with_name("earthquakes.db")

def init_db(conn: sqlite3.Connection) -> None:
    """Create the earthquakes table with 'id' as PRIMARY KEY to prevent duplicates."""
    query = """
    CREATE TABLE IF NOT EXISTS earthquakes (
        id TEXT PRIMARY KEY,
        magnitude REAL NOT NULL,
        place TEXT,
        time INTEGER NOT NULL,
        event_type TEXT,
        longitude REAL NOT NULL,
        latitude REAL NOT NULL,
        depth_km REAL NOT NULL,
        updated INTEGER,
        mag_type TEXT,
        status TEXT,
        url TEXT,
        event_datetime TEXT,
        updated_datetime TEXT,
        event_hour INTEGER,
        region TEXT,
        energy_joules REAL,
        mag_category TEXT,
        depth_category TEXT
    );
    """
    conn.execute(query)
    conn.commit()



def save_to_sqlite(df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    """Insert cleaned records idempotently (ignores duplicate IDs) and returns total row count."""   
    df_to_save = df.copy()
    df_to_save["event_datetime"] = df_to_save["event_datetime"].astype(str)
    df_to_save["updated_datetime"] = df_to_save["updated_datetime"].astype(str)

    columns = list(df_to_save.columns)
    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join(columns)
    insert_sql = f"INSERT OR IGNORE INTO earthquakes ({col_names}) VALUES ({placeholders})"
    with sqlite3.connect(db_path) as conn:   
        init_db(conn)
        rows = list(df_to_save.itertuples(index=False, name=None))
        conn.executemany(insert_sql, rows)
        conn.commit()

        total_rows = conn.execute("SELECT COUNT(*) FROM earthquakes").fetchone()[0]
    return total_rows

if __name__ == "__main__":
    raw_df = load_validated_data()
    df_clean = clean_data(raw_df)

    # First run: inserts all 200 records
    count_first = save_to_sqlite(df_clean)
    print(f"Rows in DB after 1st run: {count_first}")

    # Second run: tests idempotency (should still be 200, no duplicates)
    count_second = save_to_sqlite(df_clean)
    print(f"Rows in DB after 2nd run: {count_second}")