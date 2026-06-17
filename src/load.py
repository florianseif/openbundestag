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
# falls back, in order, to: the ministers table, other speeches by the same
# person (their own declared faction — kept first so era-correct labels such as
# PDS are not overwritten by the registry's modern "Die Linke"), a name-based
# lookup, and finally the official MdB-Stammdaten registry (politician_terms),
# which recovers session chairs and others whose speeches never carry a faction.
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
                -- 1. name match in ministers table — exact or first-token match.
                --    NULLIF guards against scraped ministers with an empty party
                --    (e.g. Steffi Lemke), so the empty string does not short-
                --    circuit COALESCE and we fall through to the steps below.
                NULLIF(trim(
                    (SELECT m.party FROM ministers m
                     WHERE LOWER(m.full_name) = LOWER(trim(s.first_name) || ' ' || s.last_name)
                        OR (LOWER(m.last_name) = LOWER(s.last_name)
                            AND LOWER(trim(s.first_name)) LIKE LOWER(m.first_name) || '%')
                     ORDER BY m.full_name
                     LIMIT 1)
                ), ''),
                -- 2. cross-reference by politician_id (modern terms, stable IDs).
                --    Prefer the faction the speaker actually declared in their
                --    own speeches over the registry, so era-correct labels
                --    (e.g. PDS before the 2007 rename to Die Linke) are kept.
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
                -- 4. official MdB-Stammdaten registry, term-specific. Resolves
                --    session chairs (Vize-/Präsidenten) and other members whose
                --    speeches never carry a faction tag. This single fallback
                --    recovers ~13k otherwise-Unknown speeches (term 12 alone:
                --    ~11k, dominated by Vizepräsident Cronenberg / Becker).
                (SELECT pt.faction FROM politician_terms pt
                 WHERE pt.id = s.politician_id
                   AND s.politician_id != -1
                   AND pt.electoral_term = s.electoral_term
                   AND pt.faction IS NOT NULL AND trim(pt.faction) != ''
                 ORDER BY pt.faction
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
            -- Final fallback to the official MdB-Stammdaten registry
            (SELECT pt.faction FROM politician_terms pt
             WHERE pt.id = s.politician_id
               AND s.politician_id != -1
               AND pt.electoral_term = s.electoral_term
               AND pt.faction IS NOT NULL AND trim(pt.faction) != ''
             ORDER BY pt.faction
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
        _backfill_missing_names(conn)

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


# Tables carried over verbatim by optimize_db (everything except speeches,
# which is rebuilt lean, and speech_texts, which is (re)materialised).
_CARRY_TABLES = [
    "speakers", "ministers", "minister_roles", "zwischenrufe",
    "politicians", "politician_terms", "session_files",
    "legacy_match_unresolved",
]

# Canonical display-name view (one row per member) — mirrors stammdaten.build_registry
# so the optimized DB keeps top-politician name resolution working.
_REGISTRY_VIEW_SQL = """
    CREATE OR REPLACE VIEW _registry_names AS
    SELECT id, trim(first_name) || ' ' || trim(last_name) AS name
    FROM (
        SELECT id, first_name, last_name,
               row_number() OVER (
                   PARTITION BY id
                   ORDER BY (name_bis = '') DESC, name_von DESC
               ) AS rn
        FROM politicians
    )
    WHERE rn = 1
"""


def optimize_db(db_path: str | Path) -> None:
    """Rewrite a finalized DB into the compact, fast "Option C" layout.

    Run as the LAST pipeline phase. It produces a fresh, tightly-packed file —
    the only reliable way to actually shrink the on-disk size, since DuckDB
    reclaims free blocks for reuse but never shrinks the file in place after the
    big in-place UPDATEs/DROP COLUMN that finalize performs.

    Resulting layout:
      * ``speeches``     — metadata + ``faction_normalized`` + ``search_text``
                           (lowercased). No inline ``speech_content``, so the
                           per-keyword scan reads only the lean search column.
      * ``speech_texts`` — ``(id, speech_content)`` original-cased text, read
                           only by the drill-down reader.

    Idempotent and input-agnostic: works whether the source keeps
    ``speech_content`` inline (default finalize) or already in a side table
    (``--text-table`` finalize). Writes ``<db>.optimizing`` then atomically
    renames it over ``db_path``.
    """
    src = Path(db_path)
    tmp = src.with_suffix(src.suffix + ".optimizing")
    for p in (tmp, Path(str(tmp) + ".wal")):
        if p.exists():
            p.unlink()

    with duckdb.connect(src, read_only=True) as probe:
        speech_cols = {r[1] for r in probe.execute("PRAGMA table_info('speeches')").fetchall()}
        tables = {r[0] for r in probe.execute(
            "SELECT table_name FROM information_schema.tables"
        ).fetchall()}
    if "search_text" not in speech_cols:
        raise RuntimeError(
            "optimize requires a finalized DB (speeches.search_text missing). "
            "Run:  uv run run.py --phase finalize"
        )
    text_inline = "speech_content" in speech_cols
    has_text_side = "speech_texts" in tables

    lean_cols = ", ".join(c for c in speech_cols if c != "speech_content")
    con = duckdb.connect(tmp)
    try:
        con.execute("PRAGMA threads=8")
        con.execute(f"ATTACH '{src.as_posix()}' AS s (READ_ONLY)")
        con.execute(f"CREATE TABLE speeches AS SELECT {lean_cols} FROM s.speeches")
        if text_inline:
            con.execute("CREATE TABLE speech_texts AS SELECT id, speech_content FROM s.speeches")
        elif has_text_side:
            con.execute("CREATE TABLE speech_texts AS SELECT id, speech_content FROM s.speech_texts")
        else:
            raise RuntimeError("No speech_content found inline or in speech_texts.")
        con.execute("CREATE UNIQUE INDEX idx_speech_texts_id ON speech_texts(id)")
        for t in _CARRY_TABLES:
            if t in tables:
                con.execute(f"CREATE TABLE {t} AS SELECT * FROM s.{t}")
        if "politicians" in tables:
            con.execute(_REGISTRY_VIEW_SQL)
        con.execute("CHECKPOINT")
    finally:
        con.close()

    size_gb = tmp.stat().st_size / 1e9
    src.unlink(missing_ok=True)
    Path(str(src) + ".wal").unlink(missing_ok=True)
    tmp.rename(src)
    print(f"[optimize] Compact Option-C DB written → {src} ({size_gb:.2f} GB)", flush=True)


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


def _backfill_missing_names(conn: duckdb.DuckDBPyConnection) -> None:
    """Fill in blank speaker names from the speakers table.

    A handful of modern speeches resolve to a stable politician_id but lose
    their first/last name during XML parsing (e.g. Albert Weiler, term 19).
    The canonical name lives in the speakers table keyed by that same id, so we
    copy it back. Idempotent: only touches rows whose name is currently empty.
    """
    affected = conn.execute(
        """
        SELECT COUNT(*) FROM speeches s JOIN speakers k ON k.id = s.politician_id
        WHERE s.politician_id != -1
          AND (s.last_name IS NULL OR trim(s.last_name) = '')
          AND trim(COALESCE(k.last_name, '')) != ''
        """
    ).fetchone()[0]
    if affected:
        conn.execute(
            """
            UPDATE speeches s
            SET first_name = k.first_name,
                last_name  = k.last_name
            FROM speakers k
            WHERE k.id = s.politician_id
              AND s.politician_id != -1
              AND (s.last_name IS NULL OR trim(s.last_name) = '')
              AND trim(COALESCE(k.last_name, '')) != ''
            """
        )
    print(f"[finalize] Backfilled {affected} blank speaker name(s) from speakers", flush=True)


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
