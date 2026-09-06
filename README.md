# Claim Verifier

A working, privately deployed fact-checking workspace for platform moderation teams. Four AI roles extract claims, analyze retrieved evidence, challenge weak reasoning and produce a cited assessment. Reviewers inspect sources and record decisions or appeals.

**Release status: v0.3 customer pilot.** Includes a React/TypeScript workspace, Tailwind CSS design system, accessible motion, customizable platform policies, a real post demo, customer-owned social OAuth apps and a generated server installation. This is not yet an enterprise-scale moderation product or a validated general-purpose truth detector.

## Install on a customer's server

Requires Git, Python 3.11+ and Docker with Compose. The installer itself has no Python dependencies.

```sh
git clone https://github.com/Billioncodes001/social-claim-verifier.git
cd social-claim-verifier
python scripts/deploy.py --domain claims.your-company.com
docker compose -f .deployment/compose.yaml up -d --build
```

Point the domain's DNS to the server and allow inbound ports 80/443 before starting. Caddy obtains and renews HTTPS certificates. For a local evaluation, omit `--domain`; the service binds to `127.0.0.1:8791` (`--port` can change that local port).

The installer creates a private `.deployment` directory, random administrator password and encryption key. Read `.deployment/START.txt` and `.deployment/secrets/admin_password` **locally** to sign in as `admin`. A one-shot initializer provisions the persistent volume; the running app is unprivileged and cannot read the bootstrap secrets. Existing bundles are never overwritten. On Windows, restrict access to the directory using your organization's NTFS permissions; POSIX file modes are applied on Linux.

After login, open **Connections** to add/test your AI API, **Agent team** to assign models, and **Workspace setup** to set branding, quotas and platform policies. Configure evidence search or supply original source URLs. `/healthz` reports a live database-backed service; `/readyz` returns 503 until an administrator and four model assignments exist. Readiness checks configuration, not provider availability or factual accuracy.

Upgrade with `git pull` followed by the same Compose command. Keep the existing deployment directory and volume. Back up the database and its matching master key before upgrades. Do not use `down --volumes` on a customer installation. [The CI workflow](.github/workflows/ci.yml) builds the image and exercises provisioning, login, non-root operation and persistence after restart on Linux.

## Try the demo and connect accounts

**Demo lab** works immediately after model configuration: paste post text or a caption, optionally add its original URL, and supply evidence URLs or enable configured search. **Load example** checks a deliberately incorrect Apollo 11 date against NASA. Findings, sources and agent activity appear in the same investigation view. A URL alone does not imply that a post was retrieved.

Under **Platform apps**, administrators enter their own developer app credentials and copy the displayed callback into their developer console. Secrets are encrypted and never returned. Users then authorize their own accounts from Demo lab. The app requests read permissions; social passwords are never collected.

| Platform | Account demo access | Customer requirements |
| --- | --- | --- |
| X / Twitter | Personal account OAuth, latest posts or a supplied accessible post URL | OAuth 2.0 app, API access, `tweet.read users.read offline.access`; PKCE and refresh-token rotation supported |
| Facebook | Connected user's returned posts; URL selection from the recent batch | Facebook Login app, app secret, supported Graph version, `user_posts` permission and any applicable Meta review |
| Instagram | Business/creator captions; URL selection from the recent batch | Instagram Login app, app secret, supported Graph version, `instagram_business_basic` |
| Personal Instagram | Paste the caption and original URL | Consumer account feeds are unavailable through this professional-account API |

See the official [X OAuth flow](https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code) and [Meta's Instagram Login collection](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login). App approval, access tiers and available content are controlled by each platform. Customer credentials are not bundled. OAuth/token and timeline behavior is exercised with protocol fixtures; a real customer account still needs an acceptance test with its granted permissions. Meta access tokens currently require reconnection when they expire; automatic Meta long-lived token renewal is not implemented.

Connected accounts can fetch up to 10 recent posts and check selected text. Opt-in monitoring persists across server restarts, samples 1–5 latest posts every 5 minutes or longer, and skips unchanged content. It respects the daily per-user demo limit and processing permissions. It is not a complete archive; high-volume accounts can produce more posts than the sample. Connected post caches expire after 24 hours. Disconnect removes local tokens and cached posts; revoke access in the platform's account settings if desired. Existing demo investigations can be deleted separately.

Demo investigations cannot create account strikes. Reviewers see only their own demo cases; administrators can inspect them. Account credentials and cached posts remain private to their owner. Automatic checks require configured evidence search to discover sources; without retrieved evidence, findings stay unresolved. Images, video and audio are not inspected.

## Run on Windows

Install Python 3.11+ and Node.js 22.12+ (Node 24 is used in CI). The startup script builds the frontend automatically on the first run.

```powershell
git clone https://github.com/Billioncodes001/social-claim-verifier.git
cd social-claim-verifier
.\scripts\start-local.ps1 -DownloadModel
```

Open **http://127.0.0.1:8791** and create the first administrator. Local model setup assigns all four roles to Qwen. On later runs, use `start-local.ps1` without `-DownloadModel`. If the live-validation script created a development workspace, its owner login is stored in `.runtime/owner-credentials.json`, excluded from Git along with all runtime data.

On a fresh Windows installation, use `start-local.ps1 -DownloadModel` to download the pinned llama.cpp Vulkan runtime and Qwen3-4B GGUF (about 2.5 GB). Downloads are SHA-256 verified. Provenance is saved in `.runtime/local-model/provenance.json`. This model is for development; sharing it across roles does not make those roles independent sources.

Stop the two services with `scripts/stop-local.ps1`. It verifies each PID's executable before stopping it and leaves other projects running.

## Connect your AI APIs

Python 3.11+ and Node.js 22.12+ are required for source development. Docker builds the frontend in its own Node stage; the final runtime requires only Python.

```sh
python -m venv .venv
# Activate the environment using your shell's normal command.
python -m pip install -r requirements.lock
python -m pip install -e '.[test]'
npm ci
npm run build
claim-verifier serve --port 8791
```

1. Create the first administrator in the local browser.
2. In **Connections**, add an endpoint, model ID and key. Supported protocols: OpenAI Responses, OpenAI-compatible Chat, Anthropic Messages, and a custom JSON agent endpoint.
3. **Test connection** makes a real, small model request. Hosted requests may incur your provider's usage charges.
4. In **Agent team**, assign a primary and optional fallback for each role. Different roles can use different providers.
5. Configure Tavily for web search, Wikipedia for limited background research, or use supplied source URLs.
6. In **Investigate**, submit the original post. Explicitly allow hosted processing and/or search when appropriate. A local-only submission never falls back to a hosted provider.

Custom agent endpoints receive `{role, instructions, input, response_schema}` and return `{result, usage}`; `result` must satisfy the supplied schema. API keys are sent in a bearer header. Hosted endpoints require public HTTPS; local connections are restricted to loopback addresses.

Keys are encrypted at rest with Fernet and never returned by the API. `VERIFIER_MASTER_KEY` can supply the encryption key; otherwise one is generated in the private data directory. Protect that directory and key with deployment access controls and encrypted storage.

## Implemented behavior

- Extractor, analyst, challenger and adjudicator roles; analyst and challenger run concurrently. Every run retains model identity, structured output, token usage when available, status and latency.
- Actual source retrieval with bounded content, timestamps and SHA-256 hashes. Search snippets and model memory do not substitute for source evidence.
- Factual conclusions require citations matching retrieved text. Rejected citations, missing evidence or challenger-reported gaps lead to abstention. Opposite analyst/adjudicator conclusions become `conflicting_evidence`.
- Durable SQLite jobs recover after restart. Provider retries, fallbacks, queue limits, bounded model outputs and a ten-minute investigation deadline limit work.
- Idempotent events and increasing content revisions. Edits supersede older cases. Deletions clear active case content, sources, reviews and model outputs; late model responses cannot restore them.
- Reviewer-confirmed incidents require cited adverse findings, a verified platform author, a policy rule and a distinct incident key. Duplicates count once. Appeals remove contested incidents from escalation; overturned incidents stay excluded.
- Configurable escalation: two distinct confirmed incidents prompt admin review; three prompt senior review. **Accounts are not automatically disabled.** The incident window uses the original intake date.
- Admin/reviewer roles, scoped integration tokens, audit history and JSON case export.

Citation matching establishes that words appeared in a source, not source reliability, entailment or truth. Findings still require human review.

## Run content monitors

Create a token under **Integrations**, then set it in the process environment as `VERIFIER_INGEST_TOKEN`. Tokens can submit events only; they cannot read cases or manage settings.

```sh
# One live feed check; omit --once to monitor every five minutes.
python -m verifier.connectors rss --feed https://www.nasa.gov/feed/ --once --limit 1

# Uses the existing rules on your customer-authorized X filtered stream.
# Also set X_BEARER_TOKEN; your X API subscription/charges apply.
python -m verifier.connectors x --allow-search --allow-external

# Deliver normalized partner events or retry pending deliveries.
python -m verifier.connectors jsonl --file events.jsonl
python -m verifier.connectors drain
```

The durable connector outbox retains undelivered events and clears delivered payloads. RSS tracks edits/duplicates and never treats feed publishers as verified social users. The X worker handles edit history and full `note_tweet` text and reconnects with backoff. It does not create filter rules, implement archival catch-up, or consume X deletion compliance events; a reconnect can leave a source-stream gap.

Use `--allow-external` and/or `--allow-search` to authorize those operations per connector. Defaults restrict processing to local models and supplied evidence URLs.

The common intake endpoint accepts `manual`, `x`, `facebook`, `instagram`, `whatsapp`, `partner_feed` and `rss`. RSS and X have feed workers; the Demo lab also has account adapters for X, Facebook and professional Instagram accounts. WhatsApp and platform-wide moderation feeds require a customer's authorized ingestion service to map available content to the intake contract. This service has no access to arbitrary private messages or platform-wide feeds.

See [examples/content-event.json](examples/content-event.json). The authenticated OpenAPI contract is at `/api/openapi.json`. The customer's trusted ingestion service is responsible for asserting `author_verified`; browser-entered author references cannot create strikes.

## Deploy a customer pilot

Use the generated installation at the top of this README for automatic provisioning and optional HTTPS. The root Compose file remains a minimal option with manual administrator creation:

```sh
docker compose up -d --build
docker compose exec verifier claim-verifier create-user --username admin --role admin --data-dir /data
```

For hosting, use HTTPS ingress, set `VERIFIER_ALLOWED_HOSTS` to the exact hostname, set `VERIFIER_SECURE_COOKIES=1`, keep `VERIFIER_DISABLE_WEB_SETUP=1`, and supply a persistent secret-managed master key. Create reviewers or reset a password through the server CLI:

```sh
claim-verifier create-user --username reviewer --role reviewer
claim-verifier reset-password --username owner
```

Run **one process per customer**, with one SQLite volume. Defaults allow two simultaneous investigations and 100 queued/processing cases. The generated Compose environment exposes `VERIFIER_WORKERS` (1–16) and `VERIFIER_QUEUE_LIMIT` (1–10,000); increasing them needs capacity testing. **Workspace setup** controls branding, demo quotas and each platform's enabled state, hosted AI permission, search permission and escalation thresholds. It does not support multiple service instances sharing a database. SSO, multi-tenant SaaS, distributed queues and high availability remain production work.

Back up the database and key together using encrypted, retention-controlled storage. Logical deletion removes content from active records; already-transmitted provider requests, old backups and filesystem remnants need separate storage/provider retention controls. Audit history is application-managed, not an immutable external ledger. Evidence can become stale and require re-investigation.

## Verification

```sh
python -m pytest -q
python scripts/live_validation.py
npm run build
npx playwright install --no-shell chromium
npm run test:ui
```

Tests cover authorization, secret handling, body/network limits, provider protocols, fallbacks, citation integrity, abstention, claim completeness, idempotency, edits, deletion races, incidents, appeals, restart recovery, connector delivery, OAuth session binding/replay, connected-post normalization, polling consent, demo privacy/quotas, platform policies, schema migration and server provisioning. GitHub Actions runs the regression suite on Windows and Linux plus an actual Docker installation smoke test.

The browser suite runs against an isolated temporary backend with **synthetic** accounts and evidence, never customer data. It exercises every route, post intake, connected post retrieval, monitoring, branding, model assignment, Meta configuration, evidence inspection, reviewer decisions, permission boundaries, mobile keyboard navigation, reduced motion and desktop/phone accessibility. Layouts are checked at 320, 390, 768, 1024 and 1440 pixels. Browser fixtures test interface behavior; they do not establish live platform access or factual accuracy.

## Frontend development

`frontend/src/` contains React 19 and strict TypeScript components, Tailwind CSS 4, Motion transitions, TanStack Query and Lucide icons. DM Sans and Newsreader fonts and the photography are served locally. Motion respects the operating system's reduced-motion preference. Mobile navigation has keyboard focus containment and Escape dismissal.

Use `npm run dev` with the Python service running on port 8791 for hot reload. Use `npm run build` after changes to update the assets served by Python. Compiled files are generated under `verifier/static/dist/` and excluded from Git. The multi-stage Docker build generates the same production bundle. Branding and all existing server-side workflows remain configurable.

The Apollo 11 images illustrate the supplied NASA example: [Earth above the lunar horizon, AS11-44-6550](https://images.nasa.gov/details/as11-44-6550) and [Lunar module ascent stage, AS11-44-6642](https://images.nasa.gov/details/as11-44-6642). Images are credited to NASA and used as factual editorial illustrations under its [media guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/); no NASA endorsement is implied. Bundled font licenses are in `frontend/public/assets/font-licenses.txt`.

[artifacts/live-validation.json](artifacts/live-validation.json) records real HTTP/model/source runs: a false historical date, a correct date, missing evidence, opinion and an embedded malicious instruction. The script creates a development owner only in a fresh workspace and otherwise uses saved development credentials. Run it only in development. [artifacts/live-feed-validation.json](artifacts/live-feed-validation.json) records the separate live RSS intake check.

These are integration smoke checks, **not a representative accuracy benchmark**. Production readiness still requires independent labeled evaluations, measured false-positive rates, stronger-model comparisons, media/adversarial tests, customer platform access, load testing and security review. Images, video, audio, enforcement, SSO and billing are not implemented.

The earlier documents in `docs/` describe the broader product target. This README and the running API define what exists now.
