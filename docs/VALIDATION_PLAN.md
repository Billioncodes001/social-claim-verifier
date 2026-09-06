# Evaluation and real-world acceptance plan

No detector or live integration has been implemented, so no accuracy, latency or platform-compatibility result is claimed yet. Acceptance must cover evidence quality and the full review/action lifecycle, not only whether an API returns JSON.

## Evaluation data

Use licensed/public research data as a starting point and an authorized partner sample for production relevance. The [ClaimCheck paper](https://aclanthology.org/2025.knowledgenlp-1.26/) illustrates claim matching and evidence-based verification on AVeriTeC; research results cannot substitute for validation on the partner's incoming content.

Separate development, calibration and blind test data by time, event/claim cluster and source where feasible. Keep future evidence out of a test of what was knowable at the posting time. A separate retrospective evaluation may use later evidence, but report that distinction. Do not tune on the final test set or count paraphrases of a known training claim as novel generalization.

Have at least two qualified annotators assess claim boundaries, endorsement, verdict, evidence adequacy and applicable policy; adjudicate disagreements. An unresolved claim is a legitimate reference outcome. Record disagreement instead of pretending every ambiguous story has a clear label.

Start with an illustrative 1,000-item stratified development/test program to discover failure modes, then size the real evaluation from the required error bounds and actual prevalence. This is a planning number, not enough evidence to certify rare-error enforcement. Use a random production sample as well as an enriched false-claim sample; otherwise precision can be badly overstated.

## Why headline accuracy is insufficient

Illustrative calculation: among 10,000 posts, suppose 100 contain the target false claim class. A detector catching 80 of those while falsely flagging 1% of the other 9,900 produces 80 correct flags and 99 false flags. Only about 44.7% of its flags are correct. These are invented inputs demonstrating the base-rate problem, not measured performance.

Track precision of each flagged class, recall, false positives per 10,000 nonviolating items, abstention/coverage, citation correctness, source freshness, evidence sufficiency and calibration. Report confidence intervals and sample sizes. Evaluate the action recommendation separately from the factual assessment.

Break results down by language, dialect, domain, media type, content format and breaking-news status. Where lawful and appropriate, examine relevant fairness concerns without inferring sensitive identities or political profiles from users. Account reach must not change the evidence standard.

## Required test cases

| Scenario | Expected behavior |
|---|---|
| An accurate report uses an exaggerated headline | No false verdict based on tone alone |
| A debunk quotes a false claim | Preserve endorsement/negation; do not penalize the debunking author |
| Satire, opinion or prediction | Not checkable as an ordinary present factual assertion, or routed for context review |
| Real old footage is described as current | Investigate date/location; do not conclude the depicted event never occurred |
| AI-generated image is labeled as illustration | Authenticity signal does not become misinformation automatically |
| Conflicting early reports | Unresolved/conflicting evidence; scheduled recheck without a strike |
| One article is copied across 20 sites | Treat as correlated evidence, not 20 independent confirmations |
| Citation does not support the exact claim | Reject it as adequate evidence |
| A source corrects an error | Invalidate affected cache entries and reassess linked cases |
| Translation/OCR changes a name or negation | Flag extraction uncertainty; preserve the original for review |
| A malicious post instructs the bot to ban someone | Instructions have no effect on tools, evidence or policy |
| A source URL redirects to an internal cloud endpoint | Fetcher blocks access |
| Duplicate delivery or event reordering | Idempotent processing; no duplicate incidents or stale action |
| Post is deleted or edited during review | Old action becomes ineligible; current version is reconsidered |
| Second and third model flags without reviewer confirmation | Zero eligible strikes and no account penalty |
| Two distinct confirmed eligible incidents | One internal escalation, according to customer policy |
| Three confirmed incidents, then one is overturned | Recompute count and propose reversal of dependent action |
| A forward attributes a claim to an unverified user | Do not assign that person an incident |
| Retrieval, model or action endpoint is unavailable | Pending/unresolved or execution-unknown, with bounded retries |
| Cross-tenant access, injected webhook or malicious media | Request rejected; no disclosure, arbitrary callback or unsafe execution |

## Gates

**Offline prototype:** schema and policy invariants pass; evidence packets are independently reviewed; unresolved states and contradictory sources behave correctly. These checks establish software behavior, not real-world accuracy.

**Shadow pilot:** run on an authorized live feed without labels or penalties. Observe real intake delays, API limits, edits/deletes, source outages and language distribution. Independently review a random sample and all severe cases; compare to the customer's current workflow. Target duration: initially two to four weeks, extend if event diversity or sample size is inadequate.

**Reviewer-assistance release:** agree customer-specific thresholds for evidence quality, false flags, workload and latency; meet them on a held-out sample and shadow data. A tentative planning target is at least 95% precision for a narrowly defined high-confidence review queue, but the measured confidence bound, coverage and domain failures must be reported. This target does not authorize automated account penalties.

**Any automated public action:** requires a distinct measured error budget, adequate subgroup/sample coverage, rollback, user notice and appeal operations, policy approval and customer authorization. Do not choose an arbitrary model score such as 0.95 as proof of production readiness. Permanent account disabling remains human-controlled in the proposed product.

**New platform/language/media type:** test its ingestion, permission, content-context, deletion and action semantics separately. Passing an X text pilot does not mean WhatsApp, Instagram video or another language is supported.

## Pilot report

Deliver dataset scope and provenance; adjudication method; per-class confusion matrices; precision/recall with intervals; coverage and unresolved rate; error examples; evidence fidelity; end-to-end latency distributions; cost per item and investigation; reviewer handling time; queue capacity; policy outcomes; appeal reversals; and all untested areas. Preserve model, prompt, policy, adapter and evidence versions so a result can be reproduced.

Decide go/no-go using these results. A demo, synthetic fixture, attractive dashboard or successful API connection cannot by itself establish sellable moderation accuracy.
