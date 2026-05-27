import sqlite3
import os

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "db", "sample.db"))


def get_schema() -> str:
    """Read all table names and column definitions from the DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view');")
    tables = [row[0] for row in cursor.fetchall()]

    schema_parts = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()
        col_defs = ", ".join(f"{col[1]} {col[2]}" for col in columns)
        schema_parts.append(f"Table: {table}\nColumns: {col_defs}")

    conn.close()
    return "\n\n".join(schema_parts)


def run_sql(query: str) -> tuple[bool, str]:
    """
    Execute a SQL query safely.
    Returns (success: bool, result_or_error: str).
    Only SELECT statements are allowed.
    """
    query_stripped = query.strip().upper()
    if not query_stripped.startswith("SELECT"):
        return False, "Only SELECT queries are allowed for safety."

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        conn.close()

        if not rows:
            return True, "Query returned no results."

        # Format as a readable table string
        header = " | ".join(col_names)
        separator = "-" * len(header)
        row_lines = [" | ".join(str(v) for v in row) for row in rows]
        result = "\n".join([header, separator] + row_lines)
        return True, result

    except Exception as e:
        return False, f"SQL Error: {str(e)}"
