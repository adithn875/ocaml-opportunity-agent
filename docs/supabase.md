# Supabase setup

This project uses Supabase's free PostgreSQL database, Data API, and Auth for
the Phase 2 web application.

1. Create a free Supabase project.
2. In the SQL Editor, run `supabase/migrations/001_phase_2.sql`.
3. Copy the project URL and publishable (or legacy anon) key into
   `web/config.js`. Those values are safe to expose in the browser because the
   migration enables Row Level Security.
4. Keep the service-role key private. Add `SUPABASE_URL` and
   `SUPABASE_SERVICE_ROLE_KEY` as GitHub Actions secrets. The collection
   workflow then runs `PYTHONPATH=src python -m ocaml_agent.supabase_sync`
   after ranking. The workflow skips synchronization until both secrets exist.
5. Deploy the `web/` directory to Cloudflare Pages by following
   `docs/cloudflare-pages.md`. In Supabase Auth settings, add the resulting
   `pages.dev` URL as a redirect URL before enabling email confirmation.

The `jobs` table is publicly readable. Saved jobs and alert preferences are
restricted to the signed-in user by Row Level Security policies.
