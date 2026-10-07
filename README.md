# OCaml Opportunity Agent

An open-source agent that collects OCaml-related opportunities, stores them in
SQLite, and ranks them with a deterministic OCaml scoring engine. Email and LLM
ranking are intentionally deferred.

Status: Milestone 3.2 (deterministic candidate filtering).

## Candidate filtering

Candidate filtering is derived from SQLite; it does not change stored scores or
add a candidate-status column. An opportunity is eligible for a later ranking
stage when it either:

- has a score of at least 30 and a non-empty source description; or
- has an explicit OCaml-relevant title cue, such as OCaml, compiler,
  compilation, formal methods, static analysis, or type systems.

Announcements and aggregate job-list posts are excluded. This preserves strong
title-only roles when a source has no description, while rejecting generic
source-only matches such as a description-less "Software Engineer" entry.

Inspect the derived set with:

    PYTHONPATH=src .venv/bin/python -m ocaml_agent.candidates

## Setup
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    scrapling install          # downloads browser deps used by the browser fetchers
    agent-reach doctor         # shows which social channels work on your machine
    python -m src.ocaml_agent.db        # creates data/agent.db
    python scripts/check_sources.py     # robots.txt + load check for every source
