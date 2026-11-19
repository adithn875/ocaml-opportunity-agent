-- One-time compatibility migration for databases created before Phase 2.
-- Every statement is idempotent and preserves existing job rows.

alter table public.jobs
    add column if not exists company text,
    add column if not exists employment_type text,
    add column if not exists location text,
    add column if not exists remote text,
    add column if not exists posted_date text,
    add column if not exists deadline text,
    add column if not exists source text,
    add column if not exists description text,
    add column if not exists deterministic_score numeric,
    add column if not exists llm_score numeric,
    add column if not exists final_score numeric,
    add column if not exists first_seen timestamptz;

create index if not exists jobs_final_score_index
    on public.jobs (final_score desc);

create index if not exists jobs_source_index
    on public.jobs (source);

notify pgrst, 'reload schema';
