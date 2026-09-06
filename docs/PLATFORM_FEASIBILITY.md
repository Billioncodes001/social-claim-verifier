# Platform feasibility and source notes

Checked 2026-09-06 UTC. Documentation access does not mean the project has API credentials, permissions, a commercial data license or an enterprise partnership. Recheck provider terms, versions and permissions when implementing each adapter.

## Compatibility has two meanings

**Content compatibility:** the shared engine can analyze normalized content supplied lawfully by a customer, regardless of its original platform.

**Operational integration:** a platform actually authorizes access, delivers events and accepts a particular action. A standard API cannot create permissions or make different enforcement systems equivalent. The strongest enterprise deployment is inside a customer's cloud with a customer-owned content-event feed and action gateway.

| Platform | Feasible first integration | What requires additional access/design |
|---|---|---|
| X | Authorized filtered stream or other permitted API input; normalize matching posts and edits | Broad coverage depends on access/product limits. Community Notes enrollment is separate. Account suspension requires a platform-owned enforcement integration |
| Facebook | Partner-provided internal feed; alternatively appropriately authorized Page content for a restricted pilot | No assumption of a universal public feed, personal-content access or platform-wide administrative power. Research tooling is not a substitute for a commercial agreement |
| Instagram | Partner feed or authorized professional-account workflows | Meta's documented Facebook Login API cannot access consumer accounts; arbitrary whole-platform monitoring is not established by this API |
| WhatsApp | User-submitted fact-check messages to an authorized business endpoint; or a WhatsApp partnership with a separately reviewed privacy design | Ordinary private chats are end-to-end encrypted. A server deployment alone cannot inspect all of them. Forwarded content also may not establish the original author |

### X

[Filtered stream documentation](https://docs.x.com/x-api/posts/filtered-stream/introduction) describes near-real-time delivery of matching posts and approximately 6–7 seconds P99 delivery latency. This is a source observation, not a guarantee for our account or an end-to-end product SLA. A restricted feed must never be described as all posts on X.

[Community Notes introduction](https://docs.x.com/x-api/community-notes/introduction) requires developer AI access and AI Note Writer enrollment. [The quickstart](https://docs.x.com/x-api/community-notes/quickstart) says requests currently require test mode, while [the endpoint reference](https://docs.x.com/x-api/community-notes/create-a-community-note) describes both test and non-test values. This documentation tension means live availability must be confirmed with the program; do not assume we can publish notes. Proposed notes are not account sanctions, nor necessarily publicly displayed. First adapter should default to internal findings only.

### Facebook and Instagram

[Meta's official Instagram collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api) documents professional-account operations and the consumer-account limitation for the Facebook Login API. This source is Meta's own Postman documentation, not a third-party API wrapper. Permission and account-type checks belong in onboarding and adapter conformance tests.

[Meta's research-tool announcement](https://about.fb.com/news/2023/11/new-tools-to-support-independent-research/) describes Content Library/API research access and applications from qualified academic/nonprofit institutions. Do not sell a commercial feed on the assumption that we qualify. The current Transparency Center page returned HTTP 429 during research, so current eligibility must be reverified directly before relying on that route. Earlier source access is not proof of present approval.

[Meta's April 2025 update](https://about.fb.com/news/2025/03/testing-begins-community-notes-facebook-instagram-threads/amp/) says US third-party fact-checking ended and Community Notes began appearing; it also separates notes from distribution penalties. This is evidence that workflows vary, not a complete current country-by-country inventory. The customer must supply its applicable regional policies at integration time.

### WhatsApp

[WhatsApp's privacy explanation](https://www.whatsapp.com/privacyquestions) says personal messages are end-to-end encrypted and unavailable to WhatsApp/Meta as plaintext. There must be no claim that installing our service in Meta's cloud grants access to those conversations.

[Meta's WhatsApp Cloud API documentation](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api) describes business messaging and account-specific webhooks. A user can deliberately submit content to a fact-checking service through an authorized business endpoint; this is distinct from monitoring other conversations. Check current business terms and bot eligibility before launch. A submitted screenshot or forward does not prove who originally wrote it, so do not assign an originator strike from that material alone.

An on-device or privacy-preserving checking feature would be a separate WhatsApp product integration with explicit control over consent, retention and disclosure. It is not a normal Business API capability or an MVP assumption. Private group monitoring is not implied by a group invitation or a business-account token.

## Evidence and research integrations

- [Google Fact Check Tools claims search](https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search) can retrieve existing fact-checked claims, with language, publisher and age filters. A match is a candidate: confirm exact claim, time, geography and the underlying evidence. Missing results mean no match in that service, not that a claim is false or true.
- [C2PA explanation](https://c2pa.org/specifications/specifications/1.4/explainer/Explainer.html) distinguishes provenance from factual truth. Missing credentials are not proof of manipulation. Credentials and forensic detectors should contribute specific evidence rather than a universal authenticity score.
- [ClaimCheck research](https://aclanthology.org/2025.knowledgenlp-1.26/) describes known-claim matching plus web-evidence processing. Its benchmark result is evidence of an evaluated research approach, not an accuracy guarantee for this project, languages, current news or production prevalence.
- [The DSA official text](https://eur-lex.europa.eu/eli/reg/2022/2065/oj/eng), especially Articles 17 and 20, informs reasons/appeal design for applicable deployments. False information is not automatically illegal; legal basis and platform-policy basis must be stored separately.

## Deployment and rights decisions still open

No platform connection has been created. Needed from a pilot customer: authorized event feed, deletion/visibility-change semantics, content retention terms, country/language scope, applicable policies, reviewers, output workflow, data/model provider permissions, expected volume and acceptable operational error rates. These are integration requirements, not reasons to stop building an offline prototype.
