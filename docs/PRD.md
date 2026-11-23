# Product Requirements Document — OCaml Jobs

**Status:** v1 SaaS definition
**Product:** OCaml Jobs
**Owner:** Product / Founder
**Last updated:** 23 November 2026

## 1. Product summary

OCaml Jobs is a focused job-intelligence SaaS for people working in OCaml,
functional programming, compilers, programming languages, formal methods, and
program analysis. It turns a fragmented set of employer career pages, community
posts, research openings, and job boards into a trusted, searchable opportunity
index with personal matching and alerts.

The product is not a general job board. Its differentiation is relevance and
signal quality: a small number of highly relevant roles, transparently linked to
their original source, rather than a large feed of weak keyword matches.

## 2. Problem

Specialist candidates miss strong opportunities because relevant roles are
distributed across niche communities, research institutes, company career pages,
and broad job boards. Conventional job sites return too much noise: a role may
mention OCaml incidentally while having no meaningful connection to language
engineering or functional programming.

Employers in this niche also struggle to reach qualified candidates without
paying for a broad, poorly targeted posting channel.

## 3. Target users

| Segment | Need | Primary value |
|---|---|---|
| OCaml / FP engineer | Find relevant roles quickly | Curated feed, matching, alerts |
| Researcher or graduate | Discover compiler, PL, formal-methods roles | Domain-specific search and explanation |
| Hiring manager / employer | Reach qualified niche candidates | Approved job posting and qualified visibility |
| Site operator | Keep the index trustworthy | Source health, review queue, moderation |

## 4. Product goals

1. Make newly posted, relevant opportunities discoverable within 24 hours.
2. Let a signed-in candidate see and act on their best matches in under five
   minutes.
3. Keep false positives low enough that users trust notifications.
4. Give employers a simple path to submit a role for approval.
5. Establish a sustainable subscription and posting-revenue model without
   degrading the public utility of the index.

## 5. Non-goals for v1

- Becoming a general-purpose job board.
- Replacing an employer's applicant-tracking system.
- Automatically applying to jobs on a candidate's behalf.
- Promising completeness for sources that cannot be collected compliantly.
- Using opaque AI scores without showing the user why a role matched.

## 6. User experience

### Public visitor

1. Lands on a public feed of current jobs.
2. Searches by company, role, location, or domain topic.
3. Filters by source and minimum match score.
4. Opens the original employer or source link to apply.
5. Is invited to create an account to save roles and receive tailored alerts.

### Candidate member

1. Creates an account and supplies skills, preferred locations, remote preference,
   and a minimum match score.
2. Receives a personalized score and a short explanation for every role.
3. Saves roles, marks them interested/not relevant, and tracks application state.
4. Receives an in-app inbox, optional browser push, and optional Telegram alerts
   for new matching roles.

### Employer

1. Creates an employer account or verifies an organization.
2. Submits a role with title, company, location, description, and apply URL.
3. Receives a review-status update.
4. Once approved, the role appears in the index and receives qualified views and
   application-click analytics.

### Operator

1. Monitors collector success, freshness, and source health.
2. Reviews employer and community submissions.
3. Corrects, archives, or removes inaccurate listings.
4. Monitors notification delivery and data-quality metrics.

## 7. Functional requirements

### A. Opportunity collection and quality

- Collect from approved public sources on a scheduled daily run.
- Deduplicate records by canonical URL and retain source attribution.
- Extract title, company, location, employment type where available,
  description, source URL, first-seen date, and source name.
- Attach transparent technology/domain tags only when supported by the title or
  source description, so users can scan a specialist role without guessing.
- Apply deterministic OCaml/PL relevance rules before costly contextual scoring.
- Rank roles using transparent technical relevance and practical-suitability
  components.
- Support manual sources and human review when compliant automation is not
  available.
- Display source and original application link for every published listing.

### B. Candidate accounts and personalization

- Support email/password account creation, sign-in, and sign-out.
- Store a profile containing skills, preferred locations, remote preference, and
  minimum score.
- Support saved jobs, relevance feedback, and application-status tracking.
- Calculate a personal match score and human-readable reasons for each job.
- Allow users to opt into daily or weekly alerts and choose a minimum alert score.

### C. Notifications

- Create a durable in-app notification record for new matching jobs.
- Support optional web-push subscriptions and Telegram delivery.
- Avoid duplicate delivery for the same user/job pair.
- Allow a user to mark notifications read and control delivery preferences.

### D. Employer workflow

- Accept public role submissions with validation and abuse protection.
- Keep new submissions unpublished until moderator approval.
- Add employer verification, self-service listing management, expiry dates, and
  posting analytics in the paid SaaS phase.

### E. Admin operations

- Provide a protected review queue for job submissions.
- Show source health: last successful run, collector status, freshness, errors,
  and roles produced.
- Record enough run-level information to troubleshoot collection and sync failures.

## 8. Existing implementation (foundation already built)

The repository already provides much of the v1 foundation:

- Python collectors for OCaml.org, Jane Street, OCaml Discuss, HN Who's Hiring,
  Tezos, Inria, Frama-C, OCamlPro, TrustInSoft, and FP Launchpad.
- SQLite persistence, candidate filtering, LLM-assisted evaluation, and an OCaml
  deterministic scoring component.
- A daily GitHub Actions pipeline that collects, scores, ranks, syncs, and
  persists state.
- Supabase schema and a static web client with authentication, job feed, search,
  profile matching, saved jobs, feedback, application tracking, moderation,
  source health, listing freshness, community stale-listing reports, Telegram,
  in-app inbox, and web-push UI.

The immediate product task is to productionize and package these capabilities as
one dependable SaaS experience—not to rebuild the collection engine.

## 9. SaaS packaging and pricing hypothesis

### Free candidate tier

- Public search and original application links.
- Account, saved roles, and basic personalized matching.
- Weekly email or in-app digest.

### Pro candidate tier (hypothesis: $9–15/month)

- Immediate browser/Telegram alerts.
- Higher number of saved searches and profiles.
- Advanced filters, application tracker, and match-history insights.
- Early access to employer-posted roles, if employers opt in.

### Employer tier (hypothesis: $149–399/listing or subscription)

- Verified organization page and self-service job posting.
- Featured listing and targeted alert inclusion.
- Posting analytics: qualified views, saves, and outbound apply clicks.
- Multi-seat posting management in a later release.

Pricing is a validation hypothesis, not a launch commitment. Charge employers
first; do not gate the essential public discovery experience prematurely.

## 10. Success metrics

| Area | Metric | Initial target |
|---|---|---|
| Supply | Fresh relevant roles published | 90% within 24 hours of discovery |
| Quality | Confirmed false-positive rate | Under 10% of reviewed listings |
| Activation | New members who save a role or complete profile | 35% in first session |
| Retention | Monthly active signed-in candidates | 30% of sign-ups after 30 days |
| Engagement | Alert-to-job-open rate | 20% or greater |
| Marketplace | Employer submission approval-to-publish time | Under one business day |
| Revenue | First paid employer postings | 3–5 during validation |

## 11. Roadmap

### Phase 0 — Production readiness (2–3 weeks)

- Run the full test suite in a reproducible Python environment.
- Apply all Supabase migrations and validate row-level security.
- Configure production secrets for Supabase, VAPID, Telegram, LLM provider, and
  workflow state.
- Deploy the web app on Cloudflare Pages (or equivalent) with a production
  domain, privacy policy, and monitoring.
- Add error tracking, collector run logs, backups, and a release checklist.
- Remove generated backup artifacts from the repository and add appropriate
  ignore rules.

### Phase 1 — Public beta (4–6 weeks)

- Launch the public index and candidate accounts.
- Validate all active collectors and add freshness/error dashboards.
- Invite 25–50 target users from the OCaml/PL community.
- Conduct weekly false-positive review and refine relevance rules.
- Ship email magic-link onboarding and transactional notification fallback.

### Phase 2 — Monetizable employer workflow (6–8 weeks)

- Add verified employer profiles, posting management, expiry/renewal, and
  paid-checkout integration.
- Add abuse prevention: rate limits, CAPTCHA, URL/domain verification, and
  moderation audit log.
- Add privacy-safe click and listing analytics.
- Pilot paid listings with 3–5 employers.

### Phase 3 — Growth (ongoing)

- Add saved searches, email digests, teams/multi-seat employer accounts, and
  referral attribution.
- Expand sources only after compliance and relevance validation.
- Consider adjacent communities (Rust, Haskell, formal verification) only if they
  preserve the core product's signal quality.

## 12. Technical requirements

- **Frontend:** static web app, responsive and accessible; deploy behind HTTPS.
- **Data/auth:** Supabase Postgres and Auth with row-level security.
- **Pipeline:** GitHub Actions scheduled run; Python collection/orchestration and
  OCaml deterministic scorer.
- **Storage:** move from workflow-owned SQLite state toward Postgres as the
  production source of truth once collection writes are safely transactional.
- **Reliability:** idempotent sync, deduplication, retries with bounded backoff,
  source-specific failure isolation, and alerting on failed runs.
- **Security:** no secrets in the browser or repository; least-privilege service
  keys; CSP/security headers; audit logging for admin actions.
- **Privacy:** collect only profile/preferences necessary for matching; publish a
  retention/deletion policy and account deletion flow before public launch.

## 13. Key risks and mitigations

| Risk | Mitigation |
|---|---|
| Scrapers break or breach source terms | Prefer official feeds/APIs, track health, respect robots/terms, retain manual workflow |
| Weak relevance destroys trust | Deterministic gate, review samples weekly, explain matching, let users mark roles not relevant |
| LLM cost or outage | Keep deterministic scorer as baseline; queue/retry contextual evaluation; cap calls |
| Thin niche market | Validate with community interviews and employer pilots before broad feature expansion |
| Notification fatigue | Strict threshold defaults, frequency controls, per-job deduplication, easy opt-out |
| Data/privacy issue | RLS tests, minimal data collection, secure secrets, deletion/export workflow |

## 14. Launch criteria

The public beta is ready when:

1. The scheduled pipeline completes successfully for seven consecutive days.
2. At least 90% of enabled sources have a visible freshness/health state.
3. Public and authenticated flows work against production Supabase with RLS
   verified.
4. A new user can create an account, set a profile, save a role, and receive a
   test notification end-to-end.
5. The operator can approve a submitted job and see it in the public feed.
6. Privacy, Terms, and contact/support paths are published.

## 15. Open decisions

1. Product name and domain: retain **OCaml Jobs** or adopt a broader brand that
   can expand beyond OCaml later?
2. Initial launch geography: global/remote-first versus a focused European cohort?
3. Should paid candidate features launch immediately, or only after employer
   revenue validates demand?
4. Which channel is the default alert: email, browser push, or Telegram?
5. When should SQLite be retired as workflow state in favor of direct Postgres
   collection writes?
