from __future__ import annotations
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from app.config import DATABASE_URL
from sqlalchemy.orm import declarative_base

Base = declarative_base()

if DATABASE_URL.startswith("sqlite"):
    # SQLite creates the .db file but not the directory holding it, and
    # reports the miss only as "unable to open database file". On a fresh
    # persistent disk that directory does not exist yet.
    if not DATABASE_URL.endswith(":memory:"):
        db_file = DATABASE_URL.split("sqlite:///", 1)[-1]
        Path(db_file).expanduser().parent.mkdir(parents=True, exist_ok=True)

    engine: Engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool if DATABASE_URL.endswith(":memory:") else None,
    )
else:
    engine: Engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_columns() -> None:
    """Add columns that were introduced after a database was first created.

    Base.metadata.create_all() creates missing TABLES but never alters an
    existing one, so a new column on a table that already exists is simply
    absent at runtime and every query touching it fails. There is no
    migration tool in this project; this covers the few additive columns.

    Additive and idempotent only — never drops or rewrites participant data.
    """
    from sqlalchemy import inspect, text

    additions = {
        # (table, column): DDL type + default
        ("reminder_assets", "is_generic"):
            "BOOLEAN NOT NULL DEFAULT FALSE",
        ("users", "study_group"):
            "VARCHAR(16)",
        # Opens the scheduled-cue clock. Distinct from sessions.started_at,
        # which is stamped when the row is created — cue slots are measured
        # from the reading window, not from session creation.
        ("sessions", "reading_started_at"):
            "TIMESTAMP",
        # Keeps published instruments and study-specific HCI items apart in
        # the export. Defaults to 0 so any pre-existing row is treated as
        # NOT-validated until proven otherwise — the safe direction, since
        # the error that matters is calling a study-authored item published.
        ("measure_responses", "validated"):
            "BOOLEAN NOT NULL DEFAULT FALSE",
        ("measure_responses", "source"):
            "TEXT",
        ("measure_responses", "phase"):
            "INTEGER",
        ("measure_responses", "scale_min"):
            "INTEGER",
        ("measure_responses", "measure_status"):
            "VARCHAR(32)",
        ("measure_responses", "battery_version"):
            "VARCHAR(48)",
        ("measure_responses", "entered_hours"):
            "INTEGER",
        ("measure_responses", "entered_minutes"):
            "INTEGER",
    }
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for (table, column), ddl in additions.items():
            if table not in existing_tables:
                continue  # create_all will build it complete
            cols = {c["name"] for c in insp.get_columns(table)}
            if column in cols:
                continue
            print(f"🗃️  adding missing column {table}.{column}")
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created successfully!")
