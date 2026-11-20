# Cloudflare Pages deployment

Cloudflare Pages hosts the static `web/` application on its free tier. The
workflow uses Direct Upload from GitHub Actions, so do not connect this
repository through Cloudflare's Git integration.

1. In Cloudflare, create a **Pages** project with Direct Upload. Set its
   production branch to `main` and note its project name.
2. Create a custom Cloudflare API token with **Account → Cloudflare Pages →
   Edit** permission.
3. In GitHub **Settings → Secrets and variables → Actions**, add:
   - `CLOUDFLARE_API_TOKEN` as a repository secret.
   - `CLOUDFLARE_ACCOUNT_ID` as a repository secret.
   - `CLOUDFLARE_PAGES_PROJECT` as a repository variable.
   - `SUPABASE_URL` as a repository variable.
   - `SUPABASE_PUBLISHABLE_KEY` as a repository variable.
   - `TELEGRAM_BOT_USERNAME` as a repository variable when enabling free
     user Telegram alerts. Use the bot username without `@`.
4. The workflow generates `web/config.js` with the two public Supabase values.
   Do not put a Supabase service-role key in this file or in a repository
   variable.
5. Push a change to `main` or run **Deploy web app to Cloudflare Pages** from
   the Actions tab.

The workflow uploads the `web/` directory with Wrangler. The first successful
production deployment is available at `<project-name>.pages.dev`.
