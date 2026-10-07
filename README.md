# OCaml Opportunity Agent

> An open-source agent for discovering, filtering, and ranking software opportunities with a focus on **OCaml, compilers, programming languages, formal methods, and static analysis**.

[![OCaml](https://img.shields.io/badge/OCaml-5.x-EC6813?logo=ocaml&logoColor=white)](https://ocaml.org/)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Overview

Finding genuinely relevant OCaml opportunities is harder than finding generic software jobs.

Important opportunities can be scattered across company career pages, OCaml community discussions, research institutes, compiler projects, formal-methods organizations, hiring threads, and open-source communities.

A simple keyword search produces too much noise.

**OCaml Opportunity Agent** is designed to solve that problem with a multi-stage pipeline:

```text
Opportunity Sources
        │
        ▼
Scrapling Collectors
        │
        ▼
SQLite
        │
        ▼
Deterministic OCaml Scoring
        │
        ▼
Candidate Filtering
        │
        ▼
LLM Contextual Scoring
        │
        ▼
Final Ranking
        │
        ▼
Daily Digest
The system is intentionally hybrid:
- Python handles collection, storage, orchestration, and integrations.
- OCaml handles deterministic domain-specific relevance scoring.
- LLMs provide contextual judgment after deterministic filtering.
The goal is not to replace deterministic logic with an LLM. It is to use each tool where it is strongest.
Current Status
Stage	Status
Source configuration	✅ Complete
Scrapling-based collection	✅ Complete
SQLite storage	✅ Complete
OCaml deterministic scoring	✅ Complete
Candidate filtering	✅ Complete
LLM contextual scoring	✅ Complete
Final ranking	🚧 Next
Daily digest	🚧 Planned
Email/message delivery	🚧 Planned
GitHub Actions automation	🚧 Planned


The current local dataset contains 221 collected opportunities.
67 candidates passed the filtering stage and received LLM scores.
Architecture
┌───────────────────────────────────────────────────────┐
│                  Opportunity Sources                  │
│                                                       │
│ OCaml.org • Discuss • Jane Street • Inria • OCamlPro │
│ Tezos • Frama-C • TrustInSoft • HN Who's Hiring      │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────┐
│                 Python Collection Layer               │
│                                                       │
│                 Scrapling + Collectors               │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────┐
│                        SQLite                         │
│                                                       │
│ title • company • location • description • source    │
│ deterministic score • LLM score • LLM reason         │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────┐
│                  OCaml Scoring Engine                 │
│                                                       │
│       Signal detection → weighted domain score       │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────┐
│                  Candidate Filtering                  │
│                                                       │
│       Remove weak matches and aggregate posts        │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────┐
│                    LLM Scoring                        │
│                                                       │
│              OmniRoute → reasoning model              │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
                    Final Ranking
                         TODO

Why Two Ranking Layers?
1. Deterministic OCaml Scoring
The first ranking layer is implemented in OCaml.
It looks for domain signals such as:
Signal	Weight
OxCaml	35
OCaml	30
Compiler	25
Dune	15
Opam	15
Functional Programming	15
Programming Languages	15
Type Systems	15
Static Analysis	15
Formal Verification	15
Formal Methods	15
OCaml Ecosystem	15


This provides an explainable and reproducible first-pass score.
2. LLM Contextual Scoring
Candidates are then evaluated using an OpenAI-compatible LLM endpoint through OmniRoute.
The LLM considers:
- job title
- company
- location
- description
- OCaml relevance
- compiler/programming-language relevance
- formal-methods relevance
- static-analysis relevance
Each evaluation produces:
score: 0–100
reason: short explanation
model: model used

The deterministic and LLM scores remain separate in SQLite.
Example Results
Some highly relevant opportunities currently identified by the pipeline include:
Research engineer: static analysis of OCaml programs       100
Research engineer or postdoc: static analysis of OCaml     100
Tools & Compilers Research and Development Internship      100
OCaml Developer                                             100
Software Engineer (OCaml) — LexiFi                          98
Programming Language Engineer                                95+
Compiler Engineer                                            95+

The system also identifies weaker matches, including generic engineering roles where OCaml is only indirectly relevant.
The objective is therefore not simply to search for the word "OCaml".
Sources
The collector currently supports:
- OCaml.org
- OCaml Discuss
- Hacker News Who's Hiring
- Jane Street
- OCamlPro
- Inria
- Tezos
- TrustInSoft
- Frama-C
Source configuration lives in:
config/sources.yaml

The collection layer uses Scrapling fetchers.
Project Structure
ocaml-opportunity-agent/
│
├── config/
│   └── sources.yaml
│
├── ocaml-scoring/
│   └── ocaml_scoring/
│       ├── bin/
│       ├── lib/
│       │   ├── detect.ml
│       │   ├── job.ml
│       │   ├── scoring.ml
│       │   └── signal.ml
│       ├── test/
│       ├── dune-project
│       └── ocaml_scoring.opam
│
├── scripts/
│   └── check_sources.py
│
├── src/
│   └── ocaml_agent/
│       ├── candidates.py
│       ├── collect.py
│       ├── collector.py
│       ├── db.py
│       ├── llm_score.py
│       ├── score_jobs.py
│       └── source-specific collectors
│
├── tests/
│   └── test_candidates.py
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md

Installation
Clone the repository:
git clone https://github.com/adithn875/ocaml-opportunity-agent.git
cd ocaml-opportunity-agent

Create the Python environment:
python3 -m venv .venv
source .venv/bin/activate

Install dependencies:
pip install -r requirements.txt

Install Scrapling browser dependencies:
scrapling install

Check Agent Reach:
agent-reach doctor

Initialize the database:
PYTHONPATH=src .venv/bin/python -m ocaml_agent.db

Check configured sources:
PYTHONPATH=src .venv/bin/python scripts/check_sources.py

Collect Opportunities
Run:
PYTHONPATH=src .venv/bin/python -m ocaml_agent.collect

Collected opportunities are stored locally in:
data/agent.db

The database is intentionally ignored by Git.
Deterministic OCaml Scoring
Build the OCaml scoring engine:
cd ocaml-scoring/ocaml_scoring
dune build

Run tests:
dune test

Return to the project root:
cd ../..

Score the collected opportunities:
PYTHONPATH=src .venv/bin/python -m ocaml_agent.score_jobs

Candidate Filtering
Inspect the filtered candidate set:
PYTHONPATH=src .venv/bin/python -m ocaml_agent.candidates

The filter accepts opportunities that either:
1. have a sufficiently strong deterministic score and a real source description, or
2. have an explicitly OCaml-relevant title such as OCaml, compiler, formal methods, static analysis, or type systems.
It rejects:
- announcement-only posts
- aggregate job lists
- weak generic title-only matches
- weak source-only matches
LLM Scoring
LLM scoring uses the local OmniRoute OpenAI-compatible API.
Set the API key in your environment:
export OMNIROUTE_API_KEY="your-api-key"

Then run:
PYTHONPATH=src .venv/bin/python -m ocaml_agent.llm_score

The current route is:
auto/best-reasoning

This allows OmniRoute to select the configured best reasoning model instead of hard-coding a single model.
Never commit API keys to Git.
Data Model
The main SQLite table is:
seen_items

Important fields include:
id
canonical_url
title
company
type
location
remote
posted_date
deadline
source
description
score
llm_score
llm_reason
llm_model
first_seen
emailed

The deterministic OCaml score and LLM score are intentionally stored independently.
Design Principles
Deterministic First
Not every scraped opportunity should consume an LLM request.
Deterministic filtering reduces noise and API usage before contextual evaluation.
Explainable Scoring
The OCaml scoring engine is deliberately simple enough to inspect and reason about.
A developer should be able to understand why an opportunity received its deterministic score.
Preserve Source Data
Descriptions and source metadata are retained where available so ranking logic can be improved without requiring another scrape.
Fail Safely
A failure from one source should not prevent the remaining sources from being processed.
Separate Responsibilities
Collection, storage, deterministic scoring, LLM evaluation, ranking, and delivery are separate stages.
This makes the system easier to test and extend.
Roadmap
Discovery
- [x] Multi-source opportunity collection
- [x] SQLite persistence
- [x] Description enrichment
- [x] Source verification
Ranking
- [x] Deterministic OCaml scoring
- [x] Candidate filtering
- [x] LLM contextual scoring
- [ ] Final ranking formula
- [ ] Duplicate/opportunity clustering
- [ ] Freshness scoring
Delivery
- [ ] Daily digest generation
- [ ] Email delivery
- [ ] Message/notification integration
- [ ] Already-seen opportunity handling
Automation
- [ ] GitHub Actions scheduled execution
- [ ] Automated daily collection
- [ ] Daily ranking pipeline
- [ ] Failure reporting
Future Ideas
- [ ] Personal preference learning
- [ ] Company-level opportunity tracking
- [ ] Internship/full-time classification
- [ ] Location preference scoring
- [ ] Salary extraction
- [ ] Application deadline tracking
- [ ] Historical ranking analysis
Why OCaml?
OCaml is not only the subject of the opportunities being discovered — it is also part of the system itself.
The deterministic relevance engine is written in OCaml as a practical example of using OCaml for a real production-style component inside a larger application.
The scoring layer uses concepts including:
- algebraic data types
- pattern matching
- modules
- functional programming
- deterministic transformations
- testable domain logic
Python handles collection and integrations, while OCaml owns the domain-specific scoring logic.
Contributing
Contributions are welcome.
Useful areas include:
- adding reliable OCaml-related opportunity sources
- improving source-specific collectors
- improving relevance signals
- improving candidate filtering
- adding tests
- improving ranking
- building delivery integrations
- improving documentation
Before submitting a pull request, run:
dune test

and the Python test suite.
Please do not commit:
.env
data/*.db
.venv/
_build/

Security
Never commit API keys, tokens, cookies, credentials, or private collected data.
Local secrets belong in environment variables or .env, which is intentionally ignored by Git.
License
This project is intended to be released under the MIT License.
Author
Adith N K
Building an OCaml-focused opportunity discovery system while learning, contributing to, and exploring the OCaml ecosystem.
- GitHub: https://github.com/adithn875
- Project: https://github.com/adithn875/ocaml-opportunity-agent
If you find the project useful, consider giving it a ⭐.
