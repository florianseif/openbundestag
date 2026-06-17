#!/usr/bin/env python
"""OpenBundestag — Bundestag speech pipeline.

Usage examples:
    uv run run.py --phase all                       # full build, term 21
    uv run run.py --phase all --all-terms           # full rebuild, ALL terms
    uv run run.py --phase load --all-terms          # one phase, every term
    uv run run.py --phase extract --term 21         # download a single term
    uv run run.py --phase load --term 19 --db custom.db
"""

from pathlib import Path

import click

# Per-term phases operate on one term's files; global phases run once over the
# whole DB.  A full build interleaves them in strict dependency order:
#
#   per-term : extract → transform → load
#   global   : ministers → stammdaten → finalize → legacy-match
#   per-term : zwischenrufe
#   global   : optimize        (LAST — shrinks the file)
#
# stammdaten MUST precede finalize: finalize's faction fallback
# (FACTION_NORMALIZE_SQL) reads the politician_terms table that stammdaten
# builds.  optimize MUST be last so every earlier write is included.
PER_TERM_PHASES = ("extract", "transform", "load", "zwischenrufe")
GLOBAL_PHASES = (
    "ministers", "stammdaten", "finalize", "legacy-match", "optimize",
)


def _run_one(
    phase: str, term: int, data_path: Path, db: str, text_table: bool
) -> None:
    """Execute a single pipeline phase.

    Per-term phases act on ``term``; global phases ignore it.  ``load`` parses
    its own term via transform, so transform never needs to run separately
    ahead of it.
    """
    term_dir = data_path / f"term_{term:02d}"

    if phase == "extract":
        from src.extract import download_term

        download_term(term, data_path)

    elif phase == "transform":
        # Parse-only (debugging); nothing is persisted without ``load``.
        from src.transform import transform_term

        transform_term(term_dir, term)

    elif phase == "load":
        from src.load import init_db, load_data
        from src.transform import transform_term

        init_db(db)
        speakers_df, speeches_df = transform_term(term_dir, term)
        load_data(db, speakers_df, speeches_df)

    elif phase == "ministers":
        from src.scrape_ministers import scrape
        from src.load import init_db, load_ministers

        init_db(db)
        ministers_df, roles_df = scrape()
        load_ministers(db, ministers_df, roles_df)

    elif phase == "stammdaten":
        from src.extract import download_stammdaten
        from src.stammdaten import build_registry
        from src.load import init_db

        init_db(db)
        xml_path = download_stammdaten(data_path)
        build_registry(db, xml_path)

    elif phase == "finalize":
        from src.load import finalize_db

        finalize_db(db, text_table=text_table)

    elif phase == "legacy-match":
        from src.match_legacy import match_legacy

        match_legacy(db)

    elif phase == "zwischenrufe":
        from src.zwischenrufe import extract_modern_term, extract_legacy_term
        from src.load import init_db, load_zwischenrufe

        init_db(db)
        modern_cutoff = 19
        if term >= modern_cutoff:
            zdf = extract_modern_term(db, term_dir, term)
        else:
            zdf = extract_legacy_term(db, term)
        load_zwischenrufe(db, zdf, term)

    elif phase == "optimize":
        from src.load import optimize_db

        optimize_db(db)


def _run_full_build(
    terms: list[int], data_path: Path, db: str, text_table: bool,
    skip_extract: bool,
) -> None:
    """Run every phase across ``terms`` in dependency order."""
    for t in terms:
        if not skip_extract:
            click.echo(f"--- extract term {t} ---")
            _run_one("extract", t, data_path, db, text_table)
        click.echo(f"--- load term {t} ---")
        _run_one("load", t, data_path, db, text_table)

    for gphase in ("ministers", "stammdaten", "finalize", "legacy-match"):
        click.echo(f"--- {gphase} ---")
        _run_one(gphase, terms[-1], data_path, db, text_table)

    for t in terms:
        click.echo(f"--- zwischenrufe term {t} ---")
        _run_one("zwischenrufe", t, data_path, db, text_table)

    click.echo("--- optimize ---")
    _run_one("optimize", terms[-1], data_path, db, text_table)


@click.command()
@click.option(
    "--phase",
    default="all",
    show_default=True,
    type=click.Choice(
        ["extract", "transform", "load", "ministers", "finalize",
         "stammdaten", "legacy-match", "zwischenrufe", "optimize", "all"],
        case_sensitive=False,
    ),
    help="Pipeline phase to execute ('all' = the full build).",
)
@click.option(
    "--term",
    default=21,
    show_default=True,
    type=int,
    help="Wahlperiode (electoral term) to process. Ignored with --all-terms.",
)
@click.option(
    "--all-terms",
    is_flag=True,
    default=False,
    help="Process every term (1–21) instead of a single --term. With "
         "--phase all this rebuilds the whole DB in one command; with a "
         "single per-term phase it runs that phase for each term. "
         "Note: --phase all --all-terms SKIPS extract (builds from already "
         "downloaded data) — run --phase extract --all-terms to (re)download.",
)
@click.option(
    "--db",
    default="openbundestag-data.db",
    show_default=True,
    help="Path to the DuckDB output file.",
)
@click.option(
    "--data-dir",
    default="data",
    show_default=True,
    help="Directory for downloaded raw XML files.",
)
@click.option(
    "--text-table",
    is_flag=True,
    default=False,
    help="In the finalize phase, move the original-cased speech_content "
         "into a speech_texts side table (keeps the main table lean while "
         "the drill-down reader can join the full passage on demand).",
)
def main(
    phase: str, term: int, all_terms: bool, db: str, data_dir: str,
    text_table: bool,
) -> None:
    """Run the OpenBundestag data pipeline."""
    data_path = Path(data_dir)
    phase = phase.lower()

    if all_terms:
        from src.extract import ALL_TERMS

        terms = list(ALL_TERMS)
    else:
        terms = [term]

    if all_terms:
        scope = f"all-terms={terms[0]}-{terms[-1]}"
    else:
        scope = f"term={term}"
    click.echo(f"OpenBundestag  |  phase={phase}  {scope}  db={db}")

    if phase == "all":
        # A full build. For --all-terms we skip the slow, bot-protected extract
        # (it is re-entrant; raw data is normally already present) so the
        # rebuild is quick. Single-term --phase all keeps the original
        # behaviour and downloads first.
        skip_extract = all_terms
        if skip_extract:
            click.echo(
                "[all-terms] skipping extract — building from downloaded data "
                "(run --phase extract --all-terms to (re)download)"
            )
        _run_full_build(terms, data_path, db, text_table, skip_extract)
    elif phase in GLOBAL_PHASES:
        # Term-independent: run exactly once even with --all-terms.
        if all_terms:
            click.echo(
                f"[all-terms] '{phase}' is term-independent — running once"
            )
        _run_one(phase, terms[-1], data_path, db, text_table)
    else:
        # A single per-term phase, for one term or every term.
        for t in terms:
            if all_terms:
                click.echo(f"--- {phase} term {t} ---")
            _run_one(phase, t, data_path, db, text_table)

    click.echo("Pipeline finished.")


if __name__ == "__main__":
    main()
