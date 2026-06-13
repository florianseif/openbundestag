"""Persist speakers and speeches DataFrames into a local DuckDB file."""

from pathlib import Path

import duckdb
import pandas as pd

# ---------------------------------------------------------------------------
# Canonical faction normalisation (single source of truth)
# ---------------------------------------------------------------------------
# Resolves the party/faction for every speech.  For speeches that carry no
# faction tag in the XML (≈55% of rows, mostly ministers and legacy terms) it
# falls back to the ministers table and to other speeches by the same person.
#
# Each LIMIT-1 subquery carries an explicit ORDER BY so the result is
# DETERMINISTIC and reproducible — without it DuckDB's parallel scan order can
# attribute the same speaker to different parties on different runs.
#
# This expression is materialised once into speeches.faction_normalized by
# finalize_db(); the Streamlit app reads that column directly instead of
# recomputing this on every query.
FACTION_NORMALIZE_SQL = """
    CASE
        WHEN faction IS NULL OR trim(faction) = ''
            THEN COALESCE(
                -- 1. name match in ministers table — exact or first-token match
                (SELECT m.party FROM ministers m
                 WHERE LOWER(m.full_name) = LOWER(trim(s.first_name) || ' ' || s.last_name)
                    OR (LOWER(m.last_name) = LOWER(s.last_name)
                        AND LOWER(trim(s.first_name)) LIKE LOWER(m.first_name) || '%')
                 ORDER BY m.full_name
                 LIMIT 1),
                -- 2. cross-reference by politician_id (modern terms, stable IDs)
                (SELECT s2.faction FROM speeches s2
                 WHERE s2.politician_id = s.politician_id
                   AND s2.politician_id != -1
                   AND s2.faction IS NOT NULL AND trim(s2.faction) != ''
                 ORDER BY s2.date, s2.id
                 LIMIT 1),
                -- 3. name-based lookup in speeches — catches Staatssekretäre
                (SELECT s3.faction FROM speeches s3
                 WHERE LOWER(s3.last_name) = LOWER(s.last_name)
                   AND LOWER(trim(s3.first_name)) LIKE LOWER(split_part(trim(s.first_name), ' ', 1)) || '%'
                   AND s3.faction IS NOT NULL AND trim(s3.faction) != ''
                 ORDER BY s3.date, s3.id
                 LIMIT 1),
                'Unknown'
            )
        WHEN regexp_matches(faction, 'LINKE|Linke')           THEN 'Die Linke'
        WHEN regexp_matches(faction, 'GRÜNEN|GRUENEN|GRÜNEN') THEN 'Bündnis 90/Die Grünen'
        ELSE trim(regexp_replace(faction, '\\s+', ' '))
    END
"""

DDL = """
CREATE TABLE IF NOT EXISTS speakers (
    id           INTEGER PRIMARY KEY,
    first_name   VARCHAR,
    last_name    VARCHAR,
    faction      VARCHAR
);

CREATE TABLE IF NOT EXISTS speeches (
    id             INTEGER PRIMARY KEY,
    session        VARCHAR,
    electoral_term INTEGER,
    date           DATE,
    politician_id  INTEGER,
    first_name     VARCHAR,
    last_name      VARCHAR,
    faction        VARCHAR,
    position_short VARCHAR,
    position_long  VARCHAR,
    speech_content TEXT
);

CREATE TABLE IF NOT EXISTS ministers (
    full_name      VARCHAR PRIMARY KEY,
    first_name     VARCHAR,
    last_name      VARCHAR,
    party          VARCHAR,
    wikipedia_url  VARCHAR
);

CREATE TABLE IF NOT EXISTS minister_roles (
    full_name  VARCHAR,
    from_year  INTEGER,
    to_year    INTEGER,
    ministry   VARCHAR
);
"""


def init_db(db_path: str | Path) -> None:
    """Create the DuckDB file and tables if they do not exist."""
    with duckdb.connect(str(db_path)) as conn:
        conn.execute(DDL)
    print(f"[load] Database initialised → {db_path}", flush=True)


def load_data(
    db_path: str | Path,
    speakers: pd.DataFrame,
    speeches: pd.DataFrame,
) -> None:
    """Upsert speakers and append speeches using direct DataFrame transfers."""
    with duckdb.connect(str(db_path)) as conn:
        # speakers: insert-or-ignore so repeated runs don't duplicate rows
        existing_ids: set[int] = set(
            conn.execute("SELECT id FROM speakers").fetchdf()["id"].tolist()
        )
        new_speakers = speakers[~speakers["id"].isin(existing_ids)]
        if not new_speakers.empty:
            conn.execute(
                "INSERT INTO speakers SELECT * FROM new_speakers"
            )
            print(
                f"[load] Inserted {len(new_speakers)} new speakers", flush=True
            )

        # speeches: determine next id offset so re-runs don't collide
        max_id_row = conn.execute("SELECT COALESCE(MAX(id), -1) FROM speeches").fetchone()
        offset = int(max_id_row[0]) + 1 if max_id_row else 0
        speeches_to_insert = speeches.copy()
        speeches_to_insert["id"] = speeches_to_insert["id"] + offset

        conn.execute("INSERT INTO speeches SELECT * FROM speeches_to_insert")
        print(f"[load] Inserted {len(speeches_to_insert)} speeches", flush=True)

    print(f"[load] Done → {db_path}", flush=True)


def load_ministers(
    db_path: str | Path,
    ministers: pd.DataFrame,
    roles: pd.DataFrame,
) -> None:
    """Replace ministers and minister_roles tables (full refresh on each run)."""
    ministers_df = ministers
    roles_df = roles
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("DELETE FROM minister_roles")
        conn.execute("DELETE FROM ministers")
        conn.execute("INSERT INTO ministers SELECT * FROM ministers_df")
        conn.execute("INSERT INTO minister_roles SELECT * FROM roles_df")
        print(
            f"[load] {len(ministers_df)} ministers, {len(roles_df)} role periods → {db_path}",
            flush=True,
        )


def finalize_db(
    db_path: str | Path,
    text_table: bool = False,
) -> None:
    """Materialise derived columns the app reads on every request.

    Adds two columns to ``speeches`` and fills them once:
      * ``faction_normalized`` — the resolved party (see FACTION_NORMALIZE_SQL).
      * ``search_text`` — ``lower(speech_content)``; pre-lowered for fast LIKE
        scans (~5× faster than calling ``lower()`` per query over ~1.8 GB).

    Run after the speeches AND ministers tables are loaded.  Safe to re-run.

    Pass ``text_table=True`` to move ``speech_content`` into a dedicated
    ``speech_texts(id, speech_content)`` side table. The lean ``speeches`` table
    is faster for analytical aggregations; the reader JOINs the side table on
    demand. Either way the full original-cased text is always available.
    """
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("ALTER TABLE speeches ADD COLUMN IF NOT EXISTS faction_normalized VARCHAR")
        conn.execute(f"UPDATE speeches s SET faction_normalized = ({FACTION_NORMALIZE_SQL})")
        print("[finalize] faction_normalized materialised", flush=True)

        conn.execute("ALTER TABLE speeches ADD COLUMN IF NOT EXISTS search_text VARCHAR")
        conn.execute("UPDATE speeches SET search_text = lower(speech_content)")
        print("[finalize] search_text materialised", flush=True)

        if text_table:
            conn.execute(
                "CREATE OR REPLACE TABLE speech_texts AS "
                "SELECT id, speech_content FROM speeches"
            )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_speech_texts_id ON speech_texts(id)")
            conn.execute("ALTER TABLE speeches DROP COLUMN IF EXISTS speech_content")
            print("[finalize] original text moved to speech_texts side table", flush=True)

        conn.execute("CHECKPOINT")
    print(f"[finalize] Done → {db_path}", flush=True)


def query(db_path: str | Path, sql: str) -> pd.DataFrame:
    """Run an arbitrary SQL query and return the result as a DataFrame."""
    with duckdb.connect(str(db_path), read_only=True) as conn:
        return conn.execute(sql).fetchdf()
