# Claim Verifier

A working, privately deployed fact-checking workspace for platform moderation teams. Four AI roles extract claims, analyze retrieved evidence, challenge weak reasoning and produce a cited assessment. Reviewers inspect sources and record decisions or appeals.

**Release status: functional English-text pilot.** The server, dashboard, model connectors, persistent queue, feed workers and tests are implemented. This is not yet an enterprise-scale moderation product or a validated general-purpose truth detector.

## Run on Windows

```powershell
git clone https://github.com/Billioncodes001/social-claim-verifier.git
cd social-claim-verifier
.\scripts\start-local.ps1 -DownloadModel
```

Open **http://127.0.0.1:8791** and create the first administrator. Local model setup assigns all four roles to Qwen. On later runs, use `start-local.ps1` without `-DownloadModel`. If the live-validation script created a development workspace, its owner login is stored in `.runtime/owner-credentials.json`, excluded from Git along with all runtime data.

On a fresh Windows installation, use `start-local.ps1 -DownloadModel` to download the pinned llama.cpp Vulkan runtime and Qwen3-4B GGUF (about 2.5 GB). Downloads are SHA-256 verified. Provenance is saved in `.runtime/local-model/provenance.json`. This model is for development; sharing it across roles does not make those roles independent sources.

Stop the two services with `scripts/stop-local.ps1`. It verifies each PID's executable before stopping it and leaves other projects running.

## Connect your AI APIs

Python 3.11+ is required. No Node build is needed.

```sh
python -m venv .venv
# Activate the environment using your shell's normal command.
python -m pip install -r requirements.lock
python -m pip install -e '.[test]'
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

The common intake endpoint accepts `manual`, `x`, `facebook`, `instagram`, `whatsapp`, `partner_feed` and `rss`. **Only RSS and X have source workers in this release.** Facebook, Instagram and WhatsApp need a customer-authorized adapter that maps available content to the intake contract. This service has no access to arbitrary private messages or platform-wide feeds.

See [examples/content-event.json](examples/content-event.json). The authenticated OpenAPI contract is at `/api/openapi.json`. The customer's trusted ingestion service is responsible for asserting `author_verified`; browser-entered author references cannot create strikes.

## Deploy a customer pilot

The Dockerfile and Compose configuration run one workspace with a persistent volume, unprivileged user, read-only application filesystem, dropped capabilities and a loopback-bound port. **Docker is not installed on the development machine; the image has not been built or executed here.**

```sh
docker compose up -d --build
docker compose exec verifier claim-verifier create-user --username admin --role admin --data-dir /data
```

For hosting, use HTTPS ingress, set `VERIFIER_ALLOWED_HOSTS` to the exact hostname, set `VERIFIER_SECURE_COOKIES=1`, keep `VERIFIER_DISABLE_WEB_SETUP=1`, and supply a persistent secret-managed master key. Create reviewers or reset a password through the server CLI:

```sh
claim-verifier create-user --username reviewer --role reviewer
claim-verifier reset-password --username owner
```

Run **one process per customer**, with one SQLite volume. The pilot permits two simultaneous investigations and 100 queued/processing cases. It does not support multiple service instances sharing a database. SSO, multi-tenant SaaS, distributed queues and high availability remain production work.

Back up the database and key together using encrypted, retention-controlled storage. Logical deletion removes content from active records; already-transmitted provider requests, old backups and filesystem remnants need separate storage/provider retention controls. Audit history is application-managed, not an immutable external ledger. Evidence can become stale and require re-investigation.

## Verification

```sh
python -m pytest -q
python scripts/live_validation.py
node --check verifier/static/app.js
```

Tests cover authorization, secret handling, body/network limits, provider protocols, fallbacks, citation integrity, abstention, claim completeness, idempotency, edits, deletion races, incidents, appeals, restart recovery and connector delivery.

[artifacts/live-validation.json](artifacts/live-validation.json) records real HTTP/model/source runs: a false historical date, a correct date, missing evidence, opinion and an embedded malicious instruction. The script creates a development owner only in a fresh workspace and otherwise uses saved development credentials. Run it only in development. [artifacts/live-feed-validation.json](artifacts/live-feed-validation.json) records the separate live RSS intake check.

These are integration smoke checks, **not a representative accuracy benchmark**. Production readiness still requires independent labeled evaluations, measured false-positive rates, stronger-model comparisons, media/adversarial tests, customer platform access, load testing and security review. Images, video, audio, enforcement, SSO and billing are not implemented.

The earlier documents in `docs/` describe the broader product target. This README and the running API define what exists now.
