export type User = {
  id?: string;
  username: string;
  role: "admin" | "reviewer";
};
export type Workspace = {
  name: string;
  organization: string;
  demo_daily_limit: number;
};
export type Policy = {
  window_days: number;
  admin_threshold: number;
  senior_threshold: number;
};
export type PlatformProfile = {
  display_name: string;
  enabled: boolean;
  allow_hosted: boolean;
  allow_search: boolean;
  policy: Policy | null;
};
export type WorkspaceConfig = {
  workspace: Workspace;
  platforms: Record<string, PlatformProfile>;
};
export type Connection = {
  id: string;
  name: string;
  kind: string;
  model: string;
  base_url: string;
  local_endpoint: boolean;
  credential_configured: boolean;
};
export type Assignment = {
  role: string;
  connection_id: string;
  fallback_id: string | null;
};
export type AccountHistory = {
  author_ref: string;
  platform: string;
  eligible_incidents: number;
  escalation: string;
};
export type Dashboard = {
  total: number;
  counts: Record<string, number>;
  connections: Connection[];
  roles: Assignment[];
  policy: Policy;
  escalations: AccountHistory[];
};
export type CaseSummary = {
  id: string;
  platform: string;
  status: string;
  text: string;
  created: string;
  author_ref?: string;
  is_demo?: number;
};
export type Claim = {
  id: string;
  text: string;
  context: string;
  checkable: boolean;
  quote: string;
};
export type Judgment = {
  claim_id: string;
  verdict: string;
  rationale: string;
  citations: { evidence_id: string; quote: string }[];
  citation_check?: string;
};
export type Evidence = {
  id: string;
  url: string;
  title: string;
  status: string;
  text: string;
  error?: string;
  host: string;
  retrieved_at: string;
  published_at?: string;
  sha256: string;
  duplicate_content?: boolean;
};
export type Assessment = {
  summary?: string;
  claims: Claim[];
  judgments: Judgment[];
  evidence: Evidence[];
  limitations: string[];
  elapsed_ms: number;
};
export type Run = {
  id: string;
  role: string;
  status: string;
  model?: string;
  elapsed_ms?: number;
  error?: string;
  output?: unknown;
  usage?: unknown;
};
export type Review = {
  decision: string;
  reason: string;
  reviewer: string;
  updated: string;
  policy_rule: string;
  incident_key: string;
};
export type CaseDetail = CaseSummary & {
  evidence_review: {
    as_of: string;
    stale_after_days: number;
    sources: {
      evidence_id: string;
      age_days: number | null;
      computed_sha256: string | null;
      warnings: string[];
      source_changes: {
        case_id: string;
        revision: number;
        evidence_id: string;
        sha256: string;
        retrieved_at: string | null;
      }[];
    }[];
    related_revisions: { case_id: string; revision: number }[];
    limits: string[];
  };
  revision: number;
  stage: string;
  error?: string;
  author_verified: boolean;
  input: { text: string; source_url: string; evidence_urls: string[] };
  result: Assessment | null;
  runs: Run[];
  review: Review | null;
  account: AccountHistory | null;
  can_confirm: boolean;
};
export type Monitor = {
  enabled: boolean;
  interval_minutes: number;
  batch_limit: number;
  allow_external_processing: boolean;
  allow_web_search: boolean;
};
export type SocialAccount = {
  id: string;
  provider: string;
  display_name: string;
  status: string;
  last_sync: string | null;
  error?: string;
  monitor: Monitor;
};
export type SocialPost = {
  id: string;
  text: string;
  source_url: string;
  posted_at: string | null;
};
export type DemoData = {
  accounts: SocialAccount[];
  cases: CaseSummary[];
  used_today: number;
  daily_limit: number;
  connection_notice: string;
  platforms: {
    provider: string;
    configured: boolean;
    enabled: boolean;
    note: string;
  }[];
};
export type SocialApp = {
  provider: string;
  configured: boolean;
  client_id: string;
  credential_configured: boolean;
  graph_version: string;
  callback_url: string;
  scopes: string;
  note: string;
};
export type Deployment = {
  ready: boolean;
  checks: { id: string; label: string; ok: boolean; required: boolean }[];
  public_url: string;
  worker_count: number;
  queue_limit: number;
  deployment_model: string;
  assessment: string;
};
export type AuditEntry = {
  id: number;
  created: string;
  actor: string;
  action: string;
  subject: string;
  details: unknown;
};
export type Token = { id: string; name: string; created: string };
export const platformNames: Record<string, string> = {
  x: "X / Twitter",
  facebook: "Facebook",
  instagram: "Instagram",
  whatsapp: "WhatsApp",
  partner_feed: "Partner feed",
  rss: "RSS",
  manual: "Pasted post",
};
export const roles = [
  {
    id: "extractor",
    name: "Claim extractor",
    description:
      "Separates factual claims from opinion and preserves the original context.",
    short: "Extract claims",
  },
  {
    id: "analyst",
    name: "Evidence analyst",
    description:
      "Examines retrieved sources and builds a cited, claim-by-claim assessment.",
    short: "Examine evidence",
  },
  {
    id: "challenger",
    name: "Independent challenger",
    description:
      "Questions weak evidence, missing context and unsupported conclusions.",
    short: "Challenge findings",
  },
  {
    id: "adjudicator",
    name: "Final adjudicator",
    description:
      "Reconciles findings into an assessment your team can inspect and review.",
    short: "Reconcile findings",
  },
];
