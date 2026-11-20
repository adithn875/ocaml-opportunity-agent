-- User-owned Telegram subscriptions. Service-role workflows complete the link
-- after a user starts the bot with their short-lived, opaque link token.

create table public.telegram_link_tokens (
    user_id uuid primary key references auth.users(id) on delete cascade,
    token uuid not null unique default gen_random_uuid(),
    expires_at timestamptz not null default now() + interval '1 day',
    created_at timestamptz not null default now()
);

create table public.telegram_subscriptions (
    user_id uuid primary key references auth.users(id) on delete cascade,
    chat_id bigint not null unique,
    enabled boolean not null default true,
    linked_at timestamptz not null default now(),
    last_checked_at timestamptz not null default now(),
    last_sent_at timestamptz
);

alter table public.telegram_link_tokens enable row level security;
alter table public.telegram_subscriptions enable row level security;

grant select, insert, update, delete on public.telegram_link_tokens to authenticated;
grant select, delete on public.telegram_subscriptions to authenticated;

create policy "users manage their Telegram link token"
    on public.telegram_link_tokens for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "users read their Telegram subscription"
    on public.telegram_subscriptions for select
    using (auth.uid() = user_id);

create policy "users disconnect their Telegram subscription"
    on public.telegram_subscriptions for delete
    using (auth.uid() = user_id);
