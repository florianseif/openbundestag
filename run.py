#!/usr/bin/env python
"""OpenBundestag — Bundestag speech pipeline.

Usage examples:
    uv run run.py --phase all
    uv run run.py --phase extract --term 20
    uv run run.py --phase load --term 19 --db custom.db
"""

from pathlib import Path

import click


@click.command()
@click.option(
    "--phase",
    default="all",
    show_default=True,
    type=click.Choice(
        ["extract", "transform", "load", "ministers", "finalize", "zwischenrufe", "all"],
        case_sensitive=False,
    ),
    help="Pipeline phase to execute.",
)
@click.option(
    "--term",
    default=20,
    show_default=True,
    type=int,
    help="Wahlperiode (electoral term) to process.",
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
    help="In the finalize phase, move the original-cased speech_content into a "
         "speech_texts side table (keeps the main table lean while the "
         "drill-down reader can join the full passage on demand).",
)
def main(
    phase: str, term: int, db: str, data_dir: str, text_table: bool
) -> None:
    """Run the OpenBundestag data pipeline."""
    data_path = Path(data_dir)
    term_dir = data_path / f"term_{term:02d}"
    phase = phase.lower()

    click.echo(
        f"OpenBundestag  |  phase={phase}  term={term}  db={db}"
    )

    # ------------------------------------------------------------------
    # EXTRACT: fetch raw XML files from Bundestag open-data endpoints
    # ------------------------------------------------------------------
    if phase in ("extract", "all"):
        from src.extract import download_term

        download_term(term, data_path)

    # ------------------------------------------------------------------
    # TRANSFORM: parse XML → DataFrames (needed for load too)
    # ------------------------------------------------------------------
    speakers_df = None
    speeches_df = None

    if phase in ("transform", "load", "all"):
        from src.transform import transform_term

        speakers_df, speeches_df = transform_term(term_dir, term)

    # ------------------------------------------------------------------
    # LOAD: write DataFrames into DuckDB
    # ------------------------------------------------------------------
    if phase in ("load", "all"):
        from src.load import init_db, load_data

        init_db(db)
        load_data(db, speakers_df, speeches_df)

    if phase in ("ministers", "all"):
        from src.scrape_ministers import scrape
        from src.load import init_db, load_ministers

        init_db(db)
        ministers_df, roles_df = scrape()
        load_ministers(db, ministers_df, roles_df)

    # ------------------------------------------------------------------
    # FINALIZE: materialise derived columns the app reads on every request
    # (must run after speeches + ministers are present)
    # ------------------------------------------------------------------
    if phase in ("finalize", "all"):
        from src.load import finalize_db

        finalize_db(db, text_table=text_table)

    # ------------------------------------------------------------------
    # ZWISCHENRUFE: extract interjections from XML / speech text
    # (must run after finalize — needs faction_normalized)
    # ------------------------------------------------------------------
    if phase in ("zwischenrufe", "all"):
        from src.zwischenrufe import extract_modern_term, extract_legacy_term
        from src.load import init_db, load_zwischenrufe

        init_db(db)
        modern_cutoff = 19
        if term >= modern_cutoff:
            zdf = extract_modern_term(db, term_dir, term)
        else:
            zdf = extract_legacy_term(db, term)

        load_zwischenrufe(db, zdf, term)

    click.echo("Pipeline finished.")


if __name__ == "__main__":
    main()
