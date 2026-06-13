---
title: OpenBundestag
emoji: 🏛️
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Worte der Macht — word usage in German Bundestag debates
---

# OpenBundestag — Worte der Macht

Explore word usage across **all 21 Wahlperioden** (1949–present) of German
Bundestag plenary debates — ~760,000 speeches, queried live with
[DuckDB](https://duckdb.org/).

Type a keyword or phrase in the sidebar and see how its usage breaks down over
time, by party, and by individual speakers.

## How it runs

This Space is a thin [Streamlit](https://streamlit.io/) frontend. The ~2 GB
DuckDB database is hosted separately as a public dataset
([`MissionJupiter/openbundestag-db`](https://huggingface.co/datasets/MissionJupiter/openbundestag-db))
and downloaded once on first start.

## Data & attribution

- Plenary transcripts: German Bundestag Open Data (§ 5 UrhG, public domain).
- Speaker metadata derived in part from Wikipedia (CC BY-SA 4.0).

A derivative reimplementation inspired by the
[Open Discourse](https://opendiscourse.de/) project.
