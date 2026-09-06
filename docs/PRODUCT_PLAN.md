# Product plan for platform moderation teams

## Product decision

Build an evidence and review service for Trust & Safety teams. It ingests authorized content events, extracts checkable claims, investigates them, presents supporting and contradicting evidence, and recommends a policy-specific next step. The customer controls its rules and account actions.

The buyer is the head of moderation, platform integrity or Trust & Safety; daily users are reviewers, escalation specialists and policy analysts. An engineering team integrates the feed and the action interface. The product must improve their existing process rather than require replacement of their entire moderation stack.

The user's proposed escalation idea is supported as a **configurable, reviewed workflow**: a second eligible confirmed incident raises an admin case; a third raises an account-restriction review. Raw model flags do not increment strikes. Permanent account disabling is not an automatic result of three uncertain predictions.

## What is being detected

Separate three questions:

1. What exactly does this post claim, and does the author endorse that claim?
2. What does the available evidence establish, at the relevant time and place?
3. Does the customer's policy call for context, a warning, a restriction, or no action?

These answers are different. A false statement may be quoted in a debunk, an old true report may be presented as current, and a sensational headline may still be accurate. An inaccurate statement does not establish that its author intended to deceive.

Use claim-level outcomes: supported, contradicted, missing context, outdated context, conflicting evidence, unresolved, or not checkable. Also record context such as opinion, prediction, satire, quotation, disputed allegation and correction. A post with several claims must retain separate assessments; do not hide contradictory outcomes inside an average score.

Media authenticity is a separate dimension. Synthetic media can be clearly labeled fiction; authentic footage can have a false caption. Content Credentials can support provenance verification, but provenance alone does not establish the truth of a depicted claim. [C2PA explanation](https://c2pa.org/specifications/specifications/1.4/explainer/Explainer.html).

## Example user journey

Illustrative scenario, not an accusation about a real person: a post says a video shows flooding in City A today. The service extracts the location, date and event claim; checks whether the caption endorses it; finds an earlier occurrence of the footage; and compares that source's location and date. A similarity hit alone is not enough: the reviewer needs matched frames, relevant source context and a reason the earlier attribution is reliable.

If evidence establishes that the footage is older, the suggested label could say that the video predates the event. It must not claim that no flooding happened in City A, because that is a separate proposition. If the original source cannot be verified, the case remains unresolved. A reviewer may approve a contextual label; account penalties require a separate policy decision.

## Core capabilities

| Capability | Required behavior |
|---|---|
| Content intake | Text, captions, links and later images/audio/video; create, edit, delete and visibility-change events |
| Claim extraction | Original spans, entities, quantities, dates, geography, endorsement and surrounding context |
| Evidence retrieval | Known fact-check lookup, primary documents, original media and corroborating reporting; preserve contradictory evidence |
| Evidence quality | Check relevance, publication date, independence, provenance and source limitations; count copied reports as one underlying source |
| Verification | Assess each claim against fetched evidence; validate citations and abstain when evidence is insufficient |
| Media context | OCR, transcription, frame sampling, earlier-media matching and provenance checks with separate error indicators |
| Case prioritization | Potential harm, observed reach and growth, urgency and reviewer capacity; reach changes priority, not truth |
| Reviewer workspace | Post context, exact claim, evidence passages, dates, alternative explanations, policy rule and suggested action |
| Repeat incidents | Tenant-specific confirmed decisions with deduplication, expiry, corrections and appeal reversal |
| Reporting | Internal alerts, queue aging, reasons, evidence, adjudication history and reversal metrics |
| Policy controls | Region, language, content type, jurisdiction, severity, label wording, escalation and expiry |
| Operations | Data isolation, deployment options, observability, availability, backpressure, cost controls and rollback |

## First version

Recommended initial assumptions: one partner feed, English text and link posts, narrow verifiable news claims with dates, quotations or event assertions, plus retrieval of previously checked claims. The language is a starting scope, not a claim of global coverage. Support image attachments as retained context initially; do not silently treat an unprocessed image as verified.

Deliver a working intake API, review queue, evidence-backed claim assessment, evidence history, reviewer decisions, reversible incident ledger, and a monitoring dashboard. A customer receives findings through an authenticated API/webhook and can use its own moderation interface.

Do not include live account disabling in the first release. Medical, legal, financial and rapidly developing emergency claims require specialist review; the service can prioritize these without deciding them from model memory. Comprehensive multilingual and video coverage needs separate evaluation and staffing.

## Speed and scale

Set separate service targets for ingestion, triage, known-claim matching and novel investigation. Proposed pilot targets, all unmeasured:

- Acknowledge a valid event within 500 ms at P95 after it reaches our gateway.
- Return a preliminary internal triage result within five seconds for supported text inputs.
- Resolve suitable known-claim matches within five seconds after intake when evidence is cached and still applicable.
- Give a first evidence-backed result or explicit unresolved status within 60 seconds for the defined text investigation workload.

These are engineering targets, not promises that breaking news becomes knowable within a minute. Complex video and novel events can take longer. Publish-to-intake delay belongs to the platform/feed and must be measured separately; X's published stream description itself lists nonzero delivery latency. [X filtered stream](https://docs.x.com/x-api/posts/filtered-stream/introduction).

Use inexpensive screening and a cache before expensive research. Merge matching claims into research tasks while retaining each post's context. Prioritize deep investigations, cap retrieval budgets, and shed or delay low-priority work during surges. An outage or missing source must produce pending/unresolved status, never a false label by default.

## Repeat-offender policy

The example policy implements the user's intended escalation without equating suspicion with guilt:

| Eligible confirmed incidents within a customer-defined window | Proposed next step |
|---|---|
| First | Reviewer chooses a contextual label or warning under the customer's policy |
| Second | Automatically create an internal admin review case with evidence and decision history |
| Third | Escalate to a senior reviewer for a possible temporary restriction or suspension |
| Severe repeated abuse | Permanent disabling only through the customer's authorized adjudication process |

For the initial example, use a proposed 180-day window, not a universal rule. Only distinct, policy-eligible, confirmed incidents count. Define whether substantially identical reposts are one incident; avoid double penalties from duplicate events, edits or retries. Raw reports, model confidence, Community Notes or account popularity do not automatically qualify.

Pause new escalation from an incident under appeal. If an incident is overturned, remove its contribution, recompute the account state and issue a compensating action request where authorized. Preserve a minimal decision audit while respecting deletion requirements. Account compromise, quoted material, corrections and the author's response belong in review. Do not maintain a universal cross-platform blacklist or infer identities across unrelated accounts.

## What makes it commercially useful

The differentiator is not simply an LLM that returns true or false. It is a reproducible evidence packet, effective abstention, reliable integrations, efficient review and tenant-controlled deployment. X already exposes an AI Community Notes program, and Meta has announced a Community Notes approach in the United States. A product pitch must accommodate existing systems and regional differences. [X program](https://docs.x.com/x-api/community-notes/introduction), [Meta announcement and April 2025 update](https://about.fb.com/news/2025/03/testing-begins-community-notes-facebook-instagram-threads/amp/).

Proposed sales path: first validate with a platform moderation team that can grant an authorized feed and assign reviewers; demonstrate value against its baseline; then pursue larger enterprise integrations. No partnership or willingness to buy from Meta or X has been established.

Offer a paid pilot and an annual software/support license with usage bands or customer-hosted deployment. Charge for service capacity and evidence processing, not bans issued. Measure reviewer minutes saved, useful cases discovered, supported coverage, false flags, reversal rates and cost per reviewed case. Pricing requires actual compute/data costs and customer discovery; there is no defensible price or revenue forecast yet.

Operating cost should be modeled as:

`screened items × screening cost + researched claims × retrieval/inference cost + media minutes × processing cost + reviewer time + storage/network/data licenses`

Illustrative arithmetic only: at 10 million posts per day, researching 1% creates 100,000 investigations per day. Even a small research fraction needs disciplined caching, evidence reuse and budgets. User-supplied private content must not be sent to third-party models or search providers contrary to the customer's processing agreement.

## Buyer requirements before production

Expect security review, a data-processing agreement, regional hosting requirements, access controls, deletion support, model and data licensing checks, incident response, capacity testing and a support arrangement. Requirements such as SOC 2 or ISO certification are procurement questions, not certifications the project currently holds.

Plan for children’s data, sensitive claims, regional speech rules, reviewer wellbeing, notification wording and appeals. Relevant legal obligations depend on deployment and jurisdiction. For EU deployments, counsel should assess the DSA's reasons and complaint-handling duties and applicable privacy/automated-decision rules. DSA Article 20(6) addresses qualified staff supervision of complaint decisions; it is not a blanket statement that all initial moderation must be manual. [DSA official text, Articles 17 and 20](https://eur-lex.europa.eu/eli/reg/2022/2065/oj/eng).

## Delivery gates

1. **Design and partner scope:** choose one domain, feed, language, policy and benchmark; agree data rights and review staffing.
2. **Internal prototype:** event ingestion, claim/evidence pipeline, unresolved handling and reviewer cases; test offline and replay events.
3. **Shadow pilot:** run on authorized real content with no user-facing action; compare with independently adjudicated decisions and measure cost/latency.
4. **Assisted deployment:** reviewers approve contextual labels under a measured policy; appeals and rollback work before activation.
5. **Expansion:** separately qualify new languages, video, feeds and any limited automated action. Account-disabling authority stays with the platform.

Progress is determined by evidence and acceptance gates, not an invented completion date. The next implementation deliverable is an executable vertical slice from an incoming event to a reviewer-visible evidence case, with no production enforcement side effect.
