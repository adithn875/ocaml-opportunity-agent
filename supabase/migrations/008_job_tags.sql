-- Transparent, deterministic tags make specialist jobs scannable without
-- requiring users to infer a role's focus from a long description.

alter table public.jobs
    add column if not exists tags text[] not null default '{}';

create index if not exists jobs_tags_index
    on public.jobs using gin (tags);
