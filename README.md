# Claim Verifier

[![Verify and install](https://github.com/Billioncodes001/social-claim-verifier/actions/workflows/ci.yml/badge.svg)](https://github.com/Billioncodes001/social-claim-verifier/actions/workflows/ci.yml)

**Evidence-backed claim assessment for platform moderation teams.**

Claim Verifier turns submitted social content into a reviewable investigation: extracted claims, retrieved sources, cited findings, agent activity and a human decision record. Deploy one private workspace on a customer's server, connect the customer's AI providers, and adapt intake and review policies to each platform. Four AI roles support the workflow; reviewers remain responsible for assessing evidence and deciding incidents or appeals.

**Release status: v0.3 customer pilot.** Includes a React/TypeScript workspace, Tailwind CSS design system, accessible motion, customizable platform policies, a real post demo, customer-owned social OAuth apps and a generated server installation. This is not yet an enterprise-scale moderation product or a validated general-purpose truth detector.

[Use cases](#use-cases) · [Server installation](#install-on-a-customers-server) · [Demo and social accounts](#try-the-demo-and-connect-accounts) · [AI connections](#connect-your-ai-apis) · [API integration](#integrate-a-platform-content-feed) · [Customization](#customize-a-customer-workspace) · [Troubleshooting](#troubleshooting)

## Use cases

| Customer need                           | Workflow                                                                                    | Result                                                                          |
| --------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Triage a potentially misleading post    | Submit its text and context, retrieve evidence, then inspect the cited assessment           | A case for a reviewer, with claim-level findings and source records             |
| Demonstrate the product to a customer   | Configure models, open Demo lab and check a supplied caption or the built-in example        | A real investigation that cannot create an account incident                     |
| Check connected-account content         | Authorize a customer-configured X, Facebook or professional Instagram app, then fetch posts | Assessments of selected post text or an opt-in sample of recent posts           |
| Integrate an existing moderation system | Map created, edited and deleted content into authenticated content events                   | Durable, versioned investigations with duplicate detection                      |
| Follow a feed or defined topic          | Run the RSS worker or an authorized X filtered-stream worker                                | Queued investigations and an outbox for pending deliveries                      |
| Review repeat incidents and appeals     | Confirm eligible, distinct incidents under a policy rule; record appeals or overturns       | Configurable admin/senior-review escalation without automatic account disabling |
| Deploy for different organizations      | Set workspace identity, platform permissions, model assignments and review thresholds       | One isolated customer installation with its own database and credentials        |

The current product assesses **text and captions in an English-text pilot**. It does not analyze images, video or audio, determine whether a person intended to lie, or access a platform's entire user-content feed. Platform access comes from the customer's authorized integrations.

## How an investigation works

1. **Intake:** accept content and its revision through the workspace, Demo lab or integration API.
2. **Extraction:** identify up to five claims and retain their original wording and context.
3. **Evidence retrieval:** fetch supplied sources or discover sources through permitted search; record retrieved text, timestamps and hashes.
4. **Analysis and challenge:** run the analyst and challenger concurrently against the claims and evidence.
5. **Adjudication:** produce claim-level findings, validate citations and abstain when evidence requirements are not met.
6. **Review:** inspect sources and agent records, then record an eligible decision or appeal and export the case as JSON.

| Finding                                | Meaning for the reviewer                                                   |
| -------------------------------------- | -------------------------------------------------------------------------- |
| `supported`                            | Retrieved evidence supports the claim                                      |
| `contradicted`                         | Retrieved evidence conflicts with the claim                                |
| `missing_context` / `outdated_context` | Important context is absent or no longer current                           |
| `conflicting_evidence`                 | The investigation contains a material conflict requiring review            |
| `unresolved`                           | There is not enough usable evidence to settle the claim                    |
| `not_checkable`                        | The statement is not suitable for factual verification, such as an opinion |

These are model-assisted findings, not guarantees of truth. Citation matching verifies that a quoted passage exists in retrieved text; it does not establish the source's reliability or whether that passage proves the conclusion. Multiple model roles do not count as independent evidence sources.

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

For a first successful check, use **Demo lab → Load example**, allow the processing mode required by your chosen models, and submit. Open the resulting investigation to inspect the claim, retrieved NASA source, verdict and four agent records. If the result is blocked or unresolved, follow its reported reason before expanding the pilot.

Upgrade with `git pull` followed by the same Compose command. Keep the existing deployment directory and volume. Back up the database and its matching master key before upgrades. Do not use `down --volumes` on a customer installation. [The CI workflow](.github/workflows/ci.yml) builds the image and exercises provisioning, login, non-root operation and persistence after restart on Linux.

## Try the demo and connect accounts

**Demo lab** works immediately after model configuration: paste post text or a caption, optionally add its original URL, and supply evidence URLs or enable configured search. **Load example** checks a deliberately incorrect Apollo 11 date against NASA. Findings, sources and agent activity appear in the same investigation view. A URL alone does not imply that a post was retrieved.

Under **Platform apps**, administrators enter their own developer app credentials and copy the displayed callback into their developer console. Secrets are encrypted and never returned. Users then authorize their own accounts from Demo lab. The app requests read permissions; social passwords are never collected.

| Platform           | Account demo access                                                    | Customer requirements                                                                                           |
| ------------------ | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| X / Twitter        | Personal account OAuth, latest posts or a supplied accessible post URL | OAuth 2.0 app, API access, `tweet.read users.read offline.access`; PKCE and refresh-token rotation supported    |
| Facebook           | Connected user's returned posts; URL selection from the recent batch   | Facebook Login app, app secret, supported Graph version, `user_posts` permission and any applicable Meta review |
| Instagram          | Business/creator captions; URL selection from the recent batch         | Instagram Login app, app secret, supported Graph version, `instagram_business_basic`                            |
| Personal Instagram | Paste the caption and original URL                                     | Consumer account feeds are unavailable through this professional-account API                                    |

The table describes the adapters and scopes implemented in this repository. Confirm that the customer's app is approved for its intended use before enabling an account demo. See the official [X OAuth flow](https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code), [Meta permissions reference](https://developers.facebook.com/docs/permissions/) and [Meta's Instagram Login collection](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login). App approval, access tiers and available content are controlled by each platform. Customer credentials are not bundled. OAuth/token and timeline behavior is exercised with protocol fixtures; a real customer account still needs an acceptance test with its granted permissions. Meta access tokens currently require reconnection when they expire; automatic Meta long-lived token renewal is not implemented.

Set `VERIFIER_PUBLIC_URL` to the exact origin used to open the workspace, then register the callback shown in **Platform apps**. Its form is `https://claims.example.com/api/social/callback/x` (replace `x` with `facebook` or `instagram` for those adapters). Start account authorization from the same signed-in workspace session. Use an HTTPS deployment for a customer demo; loopback callbacks depend on the developer app's permitted redirect settings.

Connected accounts can fetch up to 10 recent posts and check selected text. Opt-in monitoring persists across server restarts, defaults to one post every 15 minutes, and can sample 1–5 latest posts at intervals of 5 minutes or longer. It skips unchanged content and respects the daily per-user demo limit and processing permissions. It is not a complete archive; high-volume accounts can produce more posts than the sample. Connected post caches expire after 24 hours. Disconnect removes local tokens and cached posts; revoke access in the platform's account settings if desired. Existing demo investigations can be deleted separately.

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
source .venv/bin/activate  # Bash; PowerShell: .\.venv\Scripts\Activate.ps1
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

For the built-in protocols, supply the API base URL including any required version prefix; the adapter appends `/responses`, `/chat/completions` or `/messages`. For a custom agent, supply the complete JSON endpoint URL. Choose a model that supports the selected protocol and the structured output expected by the roles. The connection probe verifies a small request; run an evidence-backed demo to verify the full workflow.

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

## Integrate a platform content feed

Create an integration token in **Integrations**. Copy it when it is shown and store it in the calling service's secret manager or environment. The token has `content-events:write` scope: it can enqueue content, but cannot read investigations or administer the workspace.

The following Bash example submits the repository's [sample content event](examples/content-event.json) to a local installation:

```bash
export VERIFIER_INGEST_TOKEN='replace-with-your-integration-token'
curl --fail-with-body http://127.0.0.1:8791/api/content-events \
  -H "Authorization: Bearer $VERIFIER_INGEST_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary @examples/content-event.json
```

PowerShell equivalent, with `VERIFIER_INGEST_TOKEN` already set in the environment:

```powershell
Invoke-RestMethod -Method Post `
  -Uri 'http://127.0.0.1:8791/api/content-events' `
  -Headers @{ Authorization = "Bearer $env:VERIFIER_INGEST_TOKEN" } `
  -ContentType 'application/json' `
  -InFile 'examples/content-event.json'
```

Replace the loopback address with your HTTPS workspace origin for a remote installation. The example permits local AI processing and supplies a NASA evidence URL. For hosted models, set `allow_external_processing` to `true` in the event and permit hosted processing in the platform profile. Source retrieval still makes network requests even when hosted AI and search are disabled.

Accepted events return **HTTP 202** with `{"case_id":"<case identifier>","duplicate":false}`. Acceptance means the case was queued, not that its assessment has completed. Open the case in the workspace; the intake token cannot retrieve its result. The authenticated API schema is available at `/api/openapi.json` to signed-in workspace users.

| Field or behavior        | Integration contract                                                                                                                                       |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `event_id`               | Stable identifier for one delivery. Retry an identical payload with the same ID; successful repeats return the original case with `duplicate: true`        |
| `platform`, `content_id` | Identify the source and its stable content object                                                                                                          |
| `revision`               | Positive, strictly increasing integer for each new version of that content                                                                                 |
| `event_type`             | `created`, `edited` or `deleted`; edits supersede prior cases and deletion removes active case content                                                     |
| `text`                   | Required for non-deletion events; up to 16,000 characters. A social URL is not a substitute for post text                                                  |
| `evidence_urls`          | Up to six retrievable source URLs; search can supplement them when configured and allowed                                                                  |
| `author_verified`        | Assert only when your trusted intake service has verified the platform author. Browser users and demo submissions cannot assert this for incident counting |
| Processing permissions   | `allow_external_processing` and `allow_web_search` default to `false`; the platform profile must also allow requested operations                           |
| HTTP 409                 | Event ID reused with a different payload, or a stale/non-increasing revision; correct the event contract rather than blindly retrying                      |
| HTTP 429                 | Queue or applicable demo quota is full; retry later using the original event ID and payload                                                                |

The common contract accepts X, Facebook, Instagram, WhatsApp, partner-feed, RSS and manual content. Selecting a platform value does not create a connector or grant access to that platform. Automated result delivery to a platform, public warning labels and account enforcement are not implemented.

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

Use `--allow-external` and/or `--allow-search` to authorize those operations for RSS/X workers. Their defaults restrict AI processing to local models and evidence retrieval to supplied URLs.

The common intake endpoint accepts `manual`, `x`, `facebook`, `instagram`, `whatsapp`, `partner_feed` and `rss`. RSS and X have feed workers; the Demo lab also has account adapters for X, Facebook and professional Instagram accounts. WhatsApp and platform-wide moderation feeds require a customer's authorized ingestion service to map available content to the intake contract. This service has no access to arbitrary private messages or platform-wide feeds.

See [examples/content-event.json](examples/content-event.json). The authenticated OpenAPI contract is at `/api/openapi.json`. The customer's trusted ingestion service is responsible for asserting `author_verified`; browser-entered author references cannot create strikes.

For a remote workspace, add `--url https://claims.example.com` to the connector command. Keep its `--state` SQLite outbox on persistent storage. Each JSONL line must be a complete content-event object; processing permissions are carried in that event. The `--allow-external` and `--allow-search` flags control events generated by the RSS/X workers.

## Customize a customer workspace

| Configuration surface                    | What the customer can change                                                                                                 |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Workspace setup**                      | Workspace name, organization name and per-user demo quota (default 20 investigations per UTC day)                            |
| **Platform profiles** in Workspace setup | Enabled platforms, hosted AI permission, search permission and optional platform-specific policy overrides                   |
| **Connections / Agent team**             | Provider endpoints, credentials, model IDs, primary assignments and optional role fallbacks                                  |
| **Evidence search**                      | No search, Tavily or Wikipedia; supplied source URLs remain available                                                        |
| **Policy**                               | Incident window and escalation thresholds; defaults are 180 days, two incidents for admin review and three for senior review |
| **Platform apps**                        | Customer-owned OAuth credentials and Graph API version used by the Meta adapters                                             |
| **Integrations**                         | Create or revoke ingestion tokens for customer feed services                                                                 |
| Deployment environment                   | Public URL, allowed hosts, cookies, encryption key, queue capacity and investigation concurrency                             |

Branding settings change the workspace and organization names. Colors, typography, page structure and additional platform adapters are source-level customizations. There is no no-code theme editor or arbitrary policy-rule language.

Create reviewer accounts through the server CLI using the same data directory as the running application. In the generated Compose installation:

```sh
docker compose -f .deployment/compose.yaml exec verifier \
  claim-verifier create-user --username reviewer --role reviewer --data-dir /data
```

Use `reset-password --username reviewer --data-dir /data` through the same service to reset a password interactively. A reset revokes that user's existing sessions.

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

The generated image does not bundle an AI model. Connect a provider reachable from the container. A loopback model URL inside a container refers to that container, not the host computer; the current network policy restricts local model endpoints to loopback. For the bundled Windows model, use the native Windows workflow. Other container-local model arrangements require deliberate deployment configuration.

## Troubleshooting

| Symptom                                                | Resolution                                                                                                                                                                  |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/healthz` succeeds but `/readyz` returns 503          | Create an administrator and assign all four agent roles. Then test each connection separately                                                                               |
| Models connect but an investigation is blocked         | Check per-case hosted-processing consent, platform permissions, model assignments and the reported provider/schema error                                                    |
| A finding is unresolved                                | Inspect retrieved sources, rejected citations and challenger concerns. Supply better evidence or enable permitted search; do not treat missing evidence as proof of falsity |
| Pasting a post URL retrieves no text                   | Paste the post/caption or use an authorized connected-account adapter. URL-only intake does not scrape arbitrary social pages                                               |
| OAuth callback or account retrieval fails              | Match `VERIFIER_PUBLIC_URL` and the registered callback, check requested permissions/Graph version, and reconnect expired accounts                                          |
| The installer reports that `.deployment` exists        | Reuse that bundle. Its secret key belongs with its database; do not replace it to upgrade                                                                                   |
| Hosted login fails or cookies are missing              | Check HTTPS ingress, the exact allowed hostname and secure-cookie settings                                                                                                  |
| A confirmed incident cannot be recorded                | The case must be eligible, non-demo, have cited adverse findings and a verified author, and include a policy rule and distinct incident key                                 |
| Intake returns 429                                     | Let queued work drain, check demo quotas where applicable, then retry the same delivery; tune worker capacity only after measuring it                                       |
| The frontend is missing or stale after a source update | Run `npm ci` and `npm run build`, then restart the application. Docker builds the frontend automatically                                                                    |

For local source upgrades, stop the app, pull changes, reinstall `requirements.lock` and the editable package, rebuild the frontend, and restart with the same data directory. Preserve `.runtime` and its matching master key. Use a consistent SQLite backup or stop the app while copying its database; copying a live database file alone can miss pending WAL data.

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

The recorded baseline has 74 backend tests and eight browser scenarios, plus a real local-model/source smoke evaluation and container provisioning/restart checks. See the [verification summary](artifacts/verification-summary.json), [interface validation](artifacts/web-interface-validation.json) and [container validation](artifacts/container-validation.json) for exact scope and tested revisions.

These are integration smoke checks, **not a representative accuracy benchmark**. Production readiness still requires independent labeled evaluations, measured false-positive rates, stronger-model comparisons, media/adversarial tests, customer platform access, load testing and security review. There is no guaranteed latency or throughput target. Images, video, audio, enforcement, SSO and billing are not implemented.

## Project structure and contribution

| Location                                                                | Responsibility                                                    |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `verifier/app.py`, `verifier/social.py`                                 | Workspace HTTP API, account adapters and demo monitoring          |
| `verifier/intake.py`, `verifier/connectors.py`                          | Versioned content events and feed delivery                        |
| `verifier/pipeline.py`, `verifier/providers.py`, `verifier/evidence.py` | AI orchestration, provider protocols and evidence retrieval       |
| `verifier/policy.py`, `verifier/security.py`, `verifier/db.py`          | Incident eligibility, access controls, encryption and persistence |
| `frontend/src/`                                                         | React workspace and platform configuration interfaces             |
| `scripts/deploy.py`, `Dockerfile`                                       | Customer installation bundle and container build                  |
| `tests/`, `frontend/tests/`, `artifacts/`                               | Regression coverage and recorded validation evidence              |

Report reproducible issues with the version, deployment method and sanitized error information. Do not attach API keys, OAuth tokens, database backups, login credentials or private post content. Add regression coverage for provider, intake, policy or permission changes and run the relevant verification commands before opening a pull request.

The [architecture](docs/ARCHITECTURE.md), [product plan](docs/PRODUCT_PLAN.md), [platform feasibility notes](docs/PLATFORM_FEASIBILITY.md) and [validation plan](docs/VALIDATION_PLAN.md) describe the broader product target. This README, the implementation and the running API define what exists now.

The companion [X Browser MCP](https://github.com/Billioncodes001/x-browser-mcp) provides local browser-based X research. You can manually submit its captured post text and original URL here; the projects do not currently share credentials or an automatic ingestion bridge. Claim Verifier is independent of the social platforms and AI providers it can connect to.
