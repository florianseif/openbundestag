"""Persist speakers and speeches DataFrames into a local DuckDB file."""

from pathlib import Path

import duckdb
import pandas as pd

from src.queries import PARTY_FULL_NAMES

_KNOWN_PARTIES: list[str] = list(PARTY_FULL_NAMES.keys())

# The 16 German Bundesländer as they appear in the XML faction field for
# Bundesrat speakers (state representatives who address the Bundestag).
_BUNDESLAENDER: tuple[str, ...] = (
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen",
    "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen",
    "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen",
    "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen",
)

# SQL IN-list literal, e.g.  'Bayern', 'Berlin', ...
_BUNDESLAENDER_SQL = ", ".join(f"'{s}'" for s in _BUNDESLAENDER)

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
FACTION_NORMALIZE_SQL = f"""
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
        WHEN trim(faction) IN ('CDU/CSU', 'SPD', 'FDP', 'AfD', 'Bündnis 90/Die Grünen', 'Die Linke', 'PDS', 'BSW', 'Fraktionslos')
            THEN trim(faction)
        ELSE COALESCE(
            -- For legacy data with city/district names in faction, try to resolve via politician_id
            (SELECT s2.faction FROM speeches s2
             WHERE s2.politician_id = s.politician_id
               AND s2.politician_id != -1
               AND s2.faction IS NOT NULL AND trim(s2.faction) != ''
             ORDER BY s2.date, s2.id
             LIMIT 1),
            -- Fallback to name-based lookup
            (SELECT s3.faction FROM speeches s3
             WHERE LOWER(s3.last_name) = LOWER(s.last_name)
               AND LOWER(trim(s3.first_name)) LIKE LOWER(split_part(trim(s.first_name), ' ', 1)) || '%'
               AND s3.faction IS NOT NULL AND trim(s3.faction) != ''
             ORDER BY s3.date, s3.id
             LIMIT 1),
            'Unknown'
        )
    END
"""

DDL = """
CREATE TABLE IF NOT EXISTS speakers (
    id           BIGINT PRIMARY KEY,
    first_name   VARCHAR,
    last_name    VARCHAR,
    faction      VARCHAR
);

CREATE TABLE IF NOT EXISTS session_files (
    id             INTEGER PRIMARY KEY,
    electoral_term INTEGER NOT NULL,
    session        VARCHAR NOT NULL,
    filename       VARCHAR NOT NULL,
    UNIQUE (electoral_term, session)
);

CREATE TABLE IF NOT EXISTS speeches (
    id             INTEGER PRIMARY KEY,
    session        VARCHAR,
    electoral_term INTEGER,
    date           DATE,
    politician_id  BIGINT,
    first_name     VARCHAR,
    last_name      VARCHAR,
    faction        VARCHAR,
    position_short VARCHAR,
    position_long  VARCHAR,
    speech_content TEXT,
    file_id        INTEGER REFERENCES session_files(id)
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

CREATE TABLE IF NOT EXISTS zwischenrufe (
    id                   INTEGER PRIMARY KEY,
    speech_id            INTEGER,
    electoral_term       INTEGER,
    session              VARCHAR,
    date                 DATE,
    target_speaker_id    BIGINT,
    target_speaker_party VARCHAR,
    type                 VARCHAR,
    caller_name          VARCHAR,
    caller_party         VARCHAR,
    text                 VARCHAR,
    raw                  VARCHAR
);
"""


def init_db(db_path: str | Path) -> None:
    """Create the DuckDB file and tables if they do not exist."""
    with duckdb.connect(str(db_path)) as conn:
        conn.execute(DDL)
    print(f"[load] Database initialised → {db_path}", flush=True)


_SPEECH_COLS = [
    "id", "session", "electoral_term", "date", "politician_id",
    "first_name", "last_name", "faction", "position_short",
    "position_long", "speech_content",
]


def load_data(
    db_path: str | Path,
    speakers: pd.DataFrame,
    speeches: pd.DataFrame,
) -> None:
    """Upsert speakers and append speeches using direct DataFrame transfers."""
    with duckdb.connect(str(db_path)) as conn:
        # Migrate existing DBs that predate session_files / file_id.
        conn.execute(
            "ALTER TABLE speeches ADD COLUMN IF NOT EXISTS file_id INTEGER"
        )

        # speakers: insert-or-ignore so repeated runs don't duplicate rows
        existing_ids: set[int] = set(
            conn.execute("SELECT id FROM speakers").fetchdf()["id"].tolist()
        )
        new_speakers = speakers[~speakers["id"].isin(existing_ids)]
        if not new_speakers.empty:
            conn.execute("INSERT INTO speakers SELECT * FROM new_speakers")
            print(f"[load] Inserted {len(new_speakers)} new speakers", flush=True)

        # session_files: upsert one row per unique (electoral_term, session).
        if "filename" in speeches.columns:
            new_files = (
                speeches[["electoral_term", "session", "filename"]]
                .drop_duplicates(subset=["electoral_term", "session"])
                .copy()
            )
            existing_sessions = conn.execute(
                "SELECT electoral_term, session FROM session_files"
            ).fetchdf()
            existing_keys = set(
                zip(existing_sessions["electoral_term"], existing_sessions["session"])
            )
            to_add = new_files[
                ~new_files.apply(
                    lambda r: (r["electoral_term"], r["session"]) in existing_keys,
                    axis=1,
                )
            ].copy()
            if not to_add.empty:
                max_fid = conn.execute(
                    "SELECT COALESCE(MAX(id), 0) FROM session_files"
                ).fetchone()[0]
                to_add.insert(0, "id", range(max_fid + 1, max_fid + 1 + len(to_add)))
                conn.execute("INSERT INTO session_files SELECT * FROM to_add")
                print(f"[load] Registered {len(to_add)} session files", flush=True)

        # speeches: insert only the canonical columns (file_id is set below).
        max_id_row = conn.execute(
            "SELECT COALESCE(MAX(id), -1) FROM speeches"
        ).fetchone()
        offset = int(max_id_row[0]) + 1 if max_id_row else 0
        speeches_to_insert = speeches[_SPEECH_COLS].copy()
        speeches_to_insert["id"] = speeches_to_insert["id"] + offset
        col_list = ", ".join(_SPEECH_COLS)
        conn.execute(
            f"INSERT INTO speeches ({col_list}) SELECT {col_list} FROM speeches_to_insert"
        )
        print(f"[load] Inserted {len(speeches_to_insert)} speeches", flush=True)

        # Populate file_id for newly inserted speeches via session join.
        conn.execute(
            """
            UPDATE speeches s
            SET file_id = sf.id
            FROM session_files sf
            WHERE sf.electoral_term = s.electoral_term
              AND sf.session = s.session
              AND s.file_id IS NULL
            """
        )

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
        _delete_guests(conn, db_path)

        conn.execute("ALTER TABLE speeches ADD COLUMN IF NOT EXISTS faction_normalized VARCHAR")
        conn.execute(f"UPDATE speeches s SET faction_normalized = ({FACTION_NORMALIZE_SQL})")
        print("[finalize] faction_normalized materialised", flush=True)

        _log_unknown_speakers(conn, db_path)

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


def _delete_guests(
    conn: duckdb.DuckDBPyConnection,
    db_path: str | Path,
) -> None:
    """Remove non-MdB (guest) speeches before materialising derived columns.

    Bundesrat speakers carry a Bundesland name as their faction field.  They
    are not elected Bundestag members and are excluded from all analysis.  We
    log them to a CSV first so the deletion is auditable, then delete from both
    speeches and any stale zwischenrufe that targeted them.
    """
    guest_df: pd.DataFrame = conn.execute(
        f"""
        SELECT
            first_name || ' ' || last_name AS speaker,
            faction                         AS raw_faction,
            COUNT(*)                        AS speeches
        FROM speeches
        WHERE trim(faction) IN ({_BUNDESLAENDER_SQL})
        GROUP BY speaker, raw_faction
        ORDER BY speeches DESC
        """
    ).fetchdf()

    total = int(guest_df["speeches"].sum()) if not guest_df.empty else 0
    print(
        f"[finalize] Removing {total:,} guest speeches "
        f"({len(guest_df):,} distinct speakers)",
        flush=True,
    )
    if not guest_df.empty:
        log_path = Path(str(db_path)).with_suffix(".guests.csv")
        guest_df.to_csv(log_path, index=False)
        print(f"[finalize] Guest speakers logged → {log_path}", flush=True)

    conn.execute(
        f"DELETE FROM speeches WHERE trim(faction) IN ({_BUNDESLAENDER_SQL})"
    )


def _log_unknown_speakers(
    conn: duckdb.DuckDBPyConnection,
    db_path: str | Path,
) -> None:
    """Log MdBs whose party could not be resolved to a CSV for review.

    These entries remain in the DB with faction_normalized = 'Unknown' and are
    excluded from dashboard queries.  The CSV shows the raw faction string so
    you can spot missing normalisation rules.
    """
    unknown_df: pd.DataFrame = conn.execute(
        """
        SELECT
            first_name || ' ' || last_name AS speaker,
            faction                         AS raw_faction,
            COUNT(*)                        AS speeches
        FROM speeches
        WHERE faction_normalized = 'Unknown'
        GROUP BY speaker, raw_faction
        ORDER BY speeches DESC
        """
    ).fetchdf()

    total = int(unknown_df["speeches"].sum()) if not unknown_df.empty else 0
    print(
        f"[finalize] Unknown party: {total:,} speeches, "
        f"{len(unknown_df):,} distinct speakers",
        flush=True,
    )
    if not unknown_df.empty:
        log_path = Path(str(db_path)).with_suffix(".unknown_speakers.csv")
        unknown_df.to_csv(log_path, index=False)
        print(f"[finalize] Unknown speakers logged → {log_path}", flush=True)


def load_zwischenrufe(
    db_path: str | Path,
    df: pd.DataFrame,
    electoral_term: int,
) -> None:
    """Replace zwischenrufe for *electoral_term* with the given DataFrame.

    Deletes all existing rows for the term first so re-runs are idempotent.
    The id column is assigned as a sequential offset from the current table max.
    """
    if df.empty:
        print(f"[load] No zwischenrufe to load for term {electoral_term}", flush=True)
        return

    with duckdb.connect(str(db_path)) as conn:
        conn.execute("DELETE FROM zwischenrufe WHERE electoral_term = ?", [electoral_term])

        max_id_row = conn.execute("SELECT COALESCE(MAX(id), -1) FROM zwischenrufe").fetchone()
        offset = int(max_id_row[0]) + 1  # type: ignore[index]

        df_to_insert = df.copy()
        # Drop rows whose caller_party is not a recognised party (e.g. city names
        # from legacy terms where only constituency info was present in the text).
        if "caller_party" in df_to_insert.columns:
            df_to_insert = df_to_insert[df_to_insert["caller_party"].isin(_KNOWN_PARTIES)]
        df_to_insert = df_to_insert.reset_index(drop=True)
        df_to_insert.insert(0, "id", range(offset, offset + len(df_to_insert)))

        conn.execute("INSERT INTO zwischenrufe SELECT * FROM df_to_insert")
        skipped = len(df) - len(df_to_insert)
        print(
            f"[load] Inserted {len(df_to_insert):,} zwischenrufe for term {electoral_term}"
            + (f" ({skipped:,} skipped — unknown caller_party)" if skipped else ""),
            flush=True,
        )

    print(f"[load] zwischenrufe done → {db_path}", flush=True)


def query(db_path: str | Path, sql: str) -> pd.DataFrame:
    """Run an arbitrary SQL query and return the result as a DataFrame."""
    with duckdb.connect(str(db_path), read_only=True) as conn:
        return conn.execute(sql).fetchdf()
