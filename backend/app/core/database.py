import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

Base = declarative_base()

def _make_engine():
    db_url = settings.DATABASE_URL

    # Ensure the database directory exists
    if "sqlite:///" in db_url:
        db_path = db_url.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    connect_args = {"check_same_thread": False, "timeout": 30} if "sqlite" in db_url else {}

    eng = create_engine(
        db_url,
        connect_args=connect_args,
        pool_pre_ping=True
    )

    if "sqlite" in db_url:
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

    return eng

engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Columns added after the first release. create_all() only creates missing
# tables, never missing columns, so an existing database needs them added
# explicitly or every query against the model fails.
_ADDED_COLUMNS = {
    "activities": [
        ("hr_coverage", "FLOAT DEFAULT 0.0"),
        ("data_quality", "JSON"),
        ("steps", "INTEGER"),
        ("training_effect_aerobic", "FLOAT"),
        ("training_effect_anaerobic", "FLOAT"),
        ("recovery_hours", "INTEGER"),
        ("xp", "INTEGER DEFAULT 0"),
    ],
    "activity_splits": [
        ("is_partial", "BOOLEAN DEFAULT 0"),
    ],
    "users": [
        ("is_admin", "BOOLEAN DEFAULT 0"),
        ("data_source", "VARCHAR(32) DEFAULT 'health_connect'"),
        ("cycle_tracking", "BOOLEAN DEFAULT 0"),
    ],
    "user_profile": [
        ("height_cm", "FLOAT"),
        ("birth_date", "DATE"),
    ],
}


def ensure_schema(eng=None):
    """Add any columns missing from an existing database. Safe to run always."""
    from sqlalchemy import inspect, text

    eng = eng or engine
    inspector = inspect(eng)
    existing_tables = set(inspector.get_table_names())

    with eng.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name in present:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                print(f"schema: added {table}.{name}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
