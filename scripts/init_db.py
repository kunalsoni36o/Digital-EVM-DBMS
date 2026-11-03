"""
scripts/init_db.py – database initialization script.

Executes database/schema.sql and database/seed.sql using credentials in .env.
Handles DELIMITER directives properly for PyMySQL.
"""
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
import pymysql

# Load project root .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "evm_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DEFAULT_DB_NAME = os.environ.get("DB_NAME", "digi_evm")


def split_sql_statements(sql_text: str):
    """
    Split SQL text by delimiter, tracking DELIMITER changes.
    Strips comments and skips empty statements.
    """
    current_delimiter = ";"
    statements = []
    current_stmt_lines = []

    lines = sql_text.splitlines()
    for line in lines:
        stripped = line.strip()

        # Check for DELIMITER command
        if stripped.upper().startswith("DELIMITER"):
            parts = stripped.split()
            if len(parts) >= 2:
                # Flush any accumulated statement before switching delimiter
                stmt = "\n".join(current_stmt_lines).strip()
                if stmt:
                    statements.append(stmt)
                    current_stmt_lines = []
                current_delimiter = parts[1].strip()
                continue

        # Check if the current line ends with the active delimiter
        if current_delimiter != ";" and stripped.endswith(current_delimiter):
            # Line ends with custom delimiter (e.g. $$)
            line_without_delim = line[:line.rfind(current_delimiter)]
            current_stmt_lines.append(line_without_delim)
            stmt = "\n".join(current_stmt_lines).strip()
            if stmt:
                statements.append(stmt)
            current_stmt_lines = []
        elif current_delimiter == ";" and ";" in line:
            # Handle multiple semicolons or statements ending in semicolon
            # Notice comments might have semicolons, but standard SQL statements end with ';'
            # Simple scanner for ';'
            curr_pos = 0
            while True:
                idx = line.find(";", curr_pos)
                if idx == -1:
                    current_stmt_lines.append(line[curr_pos:])
                    break
                # Semicolon found
                current_stmt_lines.append(line[curr_pos:idx])
                stmt = "\n".join(current_stmt_lines).strip()
                if stmt:
                    statements.append(stmt)
                current_stmt_lines = []
                curr_pos = idx + 1
        else:
            current_stmt_lines.append(line)

    final_stmt = "\n".join(current_stmt_lines).strip()
    if final_stmt:
        statements.append(final_stmt)

    # Filter out empty or pure comment statements
    cleaned_statements = []
    for stmt in statements:
        # Strip comments
        lines_no_comments = []
        for l in stmt.splitlines():
            s = l.strip()
            if not s.startswith("--") and not s.startswith("#") and s:
                lines_no_comments.append(l)
        cleaned = "\n".join(lines_no_comments).strip()
        if cleaned:
            cleaned_statements.append(cleaned)

    return cleaned_statements


def execute_sql_file(conn, file_path: Path, target_db: str):
    print(f"Reading {file_path.name}...")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # If the target DB is not digi_evm (e.g. digi_evm_test), replace digi_evm in content
    if target_db != "digi_evm":
        content = content.replace("digi_evm", target_db)

    statements = split_sql_statements(content)
    print(f"Found {len(statements)} statements to execute.")

    with conn.cursor() as cursor:
        for idx, stmt in enumerate(statements, 1):
            try:
                cursor.execute(stmt)
            except Exception as e:
                print(f"\n[ERROR] Failed at statement #{idx} in {file_path.name}:")
                print("-" * 60)
                print(stmt[:300] + ("..." if len(stmt) > 300 else ""))
                print("-" * 60)
                print(f"Error: {e}\n")
                raise
    conn.commit()
    print(f"[SUCCESS] Finished executing {file_path.name}.")


def main():
    parser = argparse.ArgumentParser(description="Initialize Digi EVM MySQL Database")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--test", action="store_true", help="Initialize digi_evm_test database instead")
    parser.add_argument("--db", type=str, default=None, help="Explicit database name to initialize")
    args = parser.parse_args()

    target_db = args.db or ("digi_evm_test" if args.test else DEFAULT_DB_NAME)

    if not args.yes:
        confirm = input(f"WARNING: This will drop and recreate database '{target_db}'. Continue? [y/N]: ")
        if confirm.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    schema_file = PROJECT_ROOT / "database" / "schema.sql"
    seed_file = PROJECT_ROOT / "database" / "seed.sql"

    if not schema_file.exists():
        print(f"Error: Schema file not found at {schema_file}")
        sys.exit(1)

    print(f"Connecting to MySQL server at {DB_HOST}:{DB_PORT} as {DB_USER}...")
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            autocommit=False,
            charset="utf8mb4",
        )
    except Exception as e:
        print(f"Failed to connect to MySQL: {e}")
        sys.exit(1)

    try:
        execute_sql_file(conn, schema_file, target_db)
        if seed_file.exists():
            execute_sql_file(conn, seed_file, target_db)
        print(f"\nDatabase '{target_db}' initialized successfully!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

