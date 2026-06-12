"""Connectivity check for the configured database (PostgreSQL / AWS RDS).

Run from backend/:  ../.venv/Scripts/python.exe test_db.py
Reuses app.database (same URL normalization + driver selection as the app).
"""
import sys
from sqlalchemy import text, inspect

try:
    # Importing app.database loads .env, normalizes the URL, and builds engine.
    from app.database import engine, Base, SQLALCHEMY_DATABASE_URL
    from app.models import models  # noqa: F401  (registers tables on Base)
except Exception as e:
    print(f"IMPORT ERROR: {type(e).__name__}: {e}")
    sys.exit(1)


def main():
    print(f"Effective DATABASE_URL: {engine.url}")
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar()
            dbname = conn.execute(text("SELECT current_database()")).scalar()
            user = conn.execute(text("SELECT current_user")).scalar()
            print(f"PostgreSQL version : {version}")
            print(f"Database name      : {dbname}")
            print(f"Current user       : {user}")

        # Ensure schema exists (idempotent), then list + count.
        Base.metadata.create_all(bind=engine)
        insp = inspect(engine)
        tables = insp.get_table_names()
        print(f"Tables ({len(tables)}): {tables}")
        with engine.connect() as conn:
            for t in tables:
                count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
                print(f"  {t:18s}: {count} rows")
        print("\nOK: database connection successful.")
    except Exception as e:
        print(f"\nDB ERROR: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
