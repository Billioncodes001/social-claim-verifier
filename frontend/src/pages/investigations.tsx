import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  Circle,
  ClipboardCheck,
  Clock3,
  Download,
  FileSearch,
  Filter,
  Plus,
  Search,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { field, navigate, refresh, send, stamp, useResource } from "../api";
import {
  Action,
  Badge,
  Button,
  Card,
  CaseList,
  Empty,
  External,
  Field,
  Form,
  Notice,
  PageHead,
  PlatformMark,
  QueryState,
  SectionTitle,
  useApp,
} from "../ui";
import {
  platformNames,
  roles,
  type CaseDetail,
  type CaseSummary,
  type Dashboard,
} from "../types";
import { PostForm } from "./demo";

export function Overview() {
  const dashboard = useResource<Dashboard>("/dashboard", 10000),
    cases = useResource<CaseSummary[]>("/cases", 10000);
  const { user } = useApp();
  if (!dashboard.data || !cases.data)
    return (
      <QueryState
        loading={dashboard.isPending || cases.isPending}
        error={dashboard.error || cases.error}
      />
    );
  const d = dashboard.data,
    working = (d.counts.processing || 0) + (d.counts.queued || 0);
  return (
    <>
      <PageHead
        title="The bigger picture."
        description="Your verification operations, considered at a glance."
        eyebrow="WORKSPACE OVERVIEW"
        action={
          <Button onClick={() => navigate("investigate")}>
            <Plus className="size-4" />
            New investigation
          </Button>
        }
      />
      <div className="overview-intro">
        <div>
          <span className="eyebrow">EVIDENCE BEFORE ACTION</span>
          <h2>
            More context.
            <br />
            <em>Better decisions.</em>
          </h2>
          <p>
            Your agents investigate the claims.
            <br />
            Your team makes the call.
          </p>
          <a className="text-link" href="#demo">
            Explore the verification demo
            <ArrowRight className="size-4" />
          </a>
        </div>
        <div className="overview-image">
          <img
            src="/assets/apollo-lunar-module.jpg"
            alt="Apollo 11 lunar module above the lunar surface"
          />
          <div>
            <span>THE ORIGINAL SOURCE MATTERS.</span>
            <small>NASA · Apollo 11 photographic record</small>
          </div>
        </div>
      </div>
      <div className="stats-grid">
        {[
          {
            label: "Total investigations",
            value: d.total,
            icon: FileSearch,
            note: "All submitted content",
            route: "queue",
          },
          {
            label: "Ready for review",
            value: d.counts.needs_review || 0,
            icon: ClipboardCheck,
            note: "Awaiting a human decision",
            route: "queue?status=needs_review",
          },
          {
            label: "Agents at work",
            value: working,
            icon: Clock3,
            note: "Queued and processing",
            route: "queue?status=processing",
          },
          {
            label: "Needs attention",
            value: d.counts.blocked || 0,
            icon: SlidersHorizontal,
            note: "Review processing issues",
            route: "queue?status=blocked",
          },
        ].map((s) => (
          <a href={"#" + s.route} className="stat-card group" key={s.label}>
            <div>
              <span>{s.label}</span>
              <s.icon className="size-4 text-slate-400" />
            </div>
            <strong>{s.value}</strong>
            <p>
              {s.note}
              <ArrowUpRight className="size-3.5 transition-transform group-hover:-translate-y-0.5" />
            </p>
          </a>
        ))}
      </div>
      <div className="content-grid">
        <Card className="overflow-hidden">
          <div className="px-6 pt-6">
            <SectionTitle
              title="Recent investigations"
              description="Follow the work from intake to review."
              action={
                <a href="#queue" className="text-link text-xs">
                  View queue
                  <ArrowRight className="size-3.5" />
                </a>
              }
            />
          </div>
          <CaseList cases={cases.data.slice(0, 6)} compact />
        </Card>
        <div className="space-y-6">
          <Card className="p-6">
            <SectionTitle
              title="Your verification team"
              action={
                <a
                  className="icon-button"
                  href="#agents"
                  aria-label="View agent team"
                >
                  <ArrowUpRight className="size-4" />
                </a>
              }
            />
            <div className="agent-summary">
              {roles.map((r, i) => {
                const role = d.roles.find((x) => x.role === r.id);
                const conn = d.connections.find(
                  (x) => x.id === role?.connection_id,
                );
                return (
                  <div key={r.id}>
                    <span>{String(i + 1).padStart(2, "0")}</span>
                    <div>
                      <h3>{r.name}</h3>
                      <p>{conn?.model || "No model assigned"}</p>
                    </div>
                    <span className={`status-dot ${conn ? "" : "muted-dot"}`} />
                  </div>
                );
              })}
            </div>
            {!d.connections.length && (
              <Button
                className="mt-5 w-full"
                variant="secondary"
                onClick={() =>
                  navigate(user.role === "admin" ? "connections" : "agents")
                }
              >
                Configure your team
                <ArrowRight className="size-4" />
              </Button>
            )}
          </Card>
          <Card className="p-6">
            <SectionTitle title="Account escalations" />
            {d.escalations.length ? (
              <div className="space-y-4">
                {d.escalations.map((a) => (
                  <div className="space-y-2" key={a.platform + a.author_ref}>
                    <strong className="text-sm">{a.author_ref}</strong>
                    <p className="text-xs text-slate-500">
                      {a.eligible_incidents} confirmed incidents
                    </p>
                    <Badge value={a.escalation} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-start gap-3 text-sm leading-6 text-slate-500">
                <ShieldCheck className="mt-1 size-5 shrink-0 text-emerald-700" />
                <p>
                  No accounts currently need escalation. Only eligible, reviewed
                  incidents count.
                </p>
              </div>
            )}
            <p className="mt-5 border-t border-slate-100 pt-4 text-xs text-slate-400">
              External account actions are disabled.
            </p>
          </Card>
        </div>
      </div>
    </>
  );
}
const hashFilter = (key: string) =>
  new URLSearchParams(location.hash.split("?")[1] || "").get(key) || "";
export function Queue() {
  const [search, setSearch] = useState(() => hashFilter("search")),
    [query, setQuery] = useState(search),
    [status, setStatus] = useState(() => hashFilter("status"));
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search), 250);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    const read = () => {
      setSearch(hashFilter("search"));
      setStatus(hashFilter("status"));
    };
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  const { data, isPending, error } = useResource<CaseSummary[]>(
    "/cases?q=" +
      encodeURIComponent(query) +
      "&status=" +
      encodeURIComponent(status),
    5000,
  );
  return (
    <>
      <PageHead
        title="Review queue"
        description="Read the claim, inspect the evidence and make an informed decision."
        eyebrow="TRUST OPERATIONS"
        action={
          <Button onClick={() => navigate("investigate")}>
            <Plus className="size-4" />
            New investigation
          </Button>
        }
      />
      <Card className="overflow-hidden">
        <div className="queue-toolbar">
          <div className="search-input">
            <Search className="size-4" />
            <input
              aria-label="Search posts or author references"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search posts or author references…"
            />
          </div>
          <div className="flex items-center gap-3">
            <Filter className="size-4 text-slate-400" />
            <select
              className="status-filter"
              aria-label="Case status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">All statuses</option>
              {[
                "needs_review",
                "processing",
                "queued",
                "blocked",
                "reviewed",
                "superseded",
                "deleted",
              ].map((s) => (
                <option key={s} value={s}>
                  {s.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="list-label">
          <span>INVESTIGATION</span>
          <span>{data?.length ?? "—"} results</span>
        </div>
        {data ? (
          data.length ? (
            <CaseList cases={data} />
          ) : (
            <Empty title="No matching investigations">
              Try a different search or clear the status filter.
            </Empty>
          )
        ) : (
          <div className="p-6">
            <QueryState loading={isPending} error={error} />
          </div>
        )}
      </Card>
    </>
  );
}
export function Investigate() {
  return (
    <>
      <PageHead
        title="Open an investigation"
        description="Give your team the original content and the sources worth examining."
        eyebrow="START WITH THE CLAIM"
      />
      <div className="content-grid">
        <Card className="p-6 sm:p-8">
          <PostForm />
        </Card>
        <div className="space-y-6">
          <Card className="p-6">
            <SectionTitle
              title="A considered process"
              description="Four roles. A traceable assessment."
            />
            <div className="space-y-6">
              {roles.map((r, i) => (
                <div key={r.id} className="flex gap-4">
                  <span className="step-circle">{i + 1}</span>
                  <div>
                    <h3 className="mb-1 text-sm font-semibold">{r.name}</h3>
                    <p className="text-xs leading-6 text-slate-500">
                      {r.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
          <Notice>
            English text and captions are supported. Images, video and audio are
            not analyzed. Unresolved claims remain unresolved until evidence
            supports a conclusion.
          </Notice>
        </div>
      </div>
    </>
  );
}
function Reviewer({ c }: { c: CaseDetail }) {
  const { notify } = useApp();
  const prior = c.review?.decision;
  const choices = !prior
    ? ["dismissed", ...(c.can_confirm ? ["confirmed"] : [])]
    : prior === "confirmed"
      ? ["appealed", "overturned"]
      : prior === "appealed"
        ? ["overturned", ...(c.can_confirm ? ["confirmed"] : [])]
        : [];
  const labels: Record<string, string> = {
    dismissed: "Dismiss / no eligible violation",
    confirmed: "Confirm eligible policy violation",
    appealed: "Open an appeal",
    overturned: "Overturn decision",
  };
  return (
    <Card className="p-6">
      <SectionTitle title="Reviewer decision" />
      {c.review && (
        <div className="mb-5 rounded-lg bg-stone-50 p-4">
          <Badge value={c.review.decision} />
          <p className="mt-3 text-sm leading-6">{c.review.reason}</p>
          <p className="mt-3 text-xs text-slate-500">
            {c.review.reviewer} · {stamp(c.review.updated)}
          </p>
        </div>
      )}
      {choices.length && ["needs_review", "reviewed"].includes(c.status) ? (
        <Form
          onSubmit={async (f) => {
            await send("/cases/" + c.id + "/decisions", {
              decision: field(f, "decision"),
              reason: field(f, "reason"),
              policy_rule: field(f, "policy_rule"),
              incident_key: field(f, "incident_key"),
            });
            notify("Reviewer decision recorded");
            await refresh();
          }}
        >
          <Field label="Decision">
            <select name="decision">
              {choices.map((value) => (
                <option key={value} value={value}>
                  {labels[value]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Reason">
            <textarea
              name="reason"
              rows={4}
              required
              minLength={15}
              placeholder="Explain your decision with evidence and context…"
            />
          </Field>
          {c.can_confirm && (
            <>
              <Field label="Applicable policy rule">
                <input
                  name="policy_rule"
                  defaultValue={c.review?.policy_rule || ""}
                />
              </Field>
              <Field label="Distinct incident key">
                <input
                  name="incident_key"
                  defaultValue={c.review?.incident_key || ""}
                />
              </Field>
            </>
          )}
          <Button type="submit" className="w-full">
            <ClipboardCheck className="size-4" />
            Record decision
          </Button>
        </Form>
      ) : (
        <p className="text-sm text-slate-500">
          This decision or content version is closed.
        </p>
      )}
      {!c.can_confirm && (
        <p className="mt-5 border-t border-slate-100 pt-4 text-xs leading-5 text-slate-500">
          {c.is_demo
            ? "Demo checks cannot create an account strike."
            : "An eligible strike requires a verified platform author and a cited adverse finding."}
        </p>
      )}
    </Card>
  );
}
export function Investigation({ id }: { id: string }) {
  const [interval, setInterval] = useState<number | undefined>(3000);
  const {
    data: c,
    isPending,
    error,
  } = useResource<CaseDetail>("/cases/" + id, interval);
  useEffect(() => {
    if (c && !["queued", "processing"].includes(c.status))
      setInterval(undefined);
    else setInterval(3000);
  }, [c?.status]);
  if (!c) return <QueryState loading={isPending} error={error} />;
  const result = c.result;
  return (
    <>
      <a href={c.is_demo ? "#demo" : "#queue"} className="back-link">
        <ArrowRight className="size-3.5 rotate-180" />
        {c.is_demo ? "Back to demo lab" : "Back to review queue"}
      </a>
      <PageHead
        title="The evidence, in context."
        description="The original claim, your agents’ findings and the sources behind them."
        eyebrow={"INVESTIGATION · " + c.id.slice(0, 8).toUpperCase()}
        action={
          <a
            className="button button-secondary"
            href={"/api/cases/" + id + "/export"}
          >
            <Download className="size-4" />
            Export report
          </a>
        }
      />
      <Card className="original-post">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <PlatformMark platform={c.platform} />
            <div>
              <strong>{platformNames[c.platform] || c.platform}</strong>
              <p>
                {stamp(c.created)} · Revision {c.revision}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {Boolean(c.is_demo) && <Badge value="demo" />}
            <Badge value={c.status} />
          </div>
        </div>
        <blockquote>
          {c.input.text || "This content has been deleted."}
        </blockquote>
        <div className="flex flex-wrap justify-between gap-3 text-xs text-slate-500">
          <span>
            {c.author_ref
              ? `${c.author_ref} · ${c.author_verified ? "Platform-verified identity" : "Unverified reference"}`
              : c.is_demo
                ? "Personal demo · no account strikes"
                : "Submitted for review"}
          </span>
          {c.input.source_url && (
            <External url={c.input.source_url}>View original post</External>
          )}
        </div>
      </Card>
      {c.error && (
        <div className="my-5">
          <Notice tone="error">{c.error}</Notice>
          <Action
            className="mt-3"
            onAction={async () => {
              await send("/cases/" + id + "/retry");
              setInterval(3000);
              await refresh();
            }}
          >
            Retry investigation
            <ArrowRight className="size-4" />
          </Action>
        </div>
      )}
      <div className="report-grid">
        <div className="min-w-0 space-y-6">
          <Card className="p-6 sm:p-7">
            <SectionTitle
              title="Claim assessments"
              action={
                result ? (
                  <span className="text-xs text-slate-400">
                    {result.claims.length} claim
                    {result.claims.length === 1 ? "" : "s"}
                  </span>
                ) : undefined
              }
            />
            {result ? (
              result.judgments.length ? (
                result.judgments.map((j) => (
                  <div className="claim-assessment" key={j.claim_id}>
                    <div className="mb-3 flex items-center justify-between gap-4">
                      <span className="eyebrow">
                        CLAIM {j.claim_id.replace("C", "")}
                      </span>
                      <Badge value={j.verdict} />
                    </div>
                    <h3>
                      {result.claims.find((x) => x.id === j.claim_id)?.text ||
                        j.claim_id}
                    </h3>
                    <p>{j.rationale}</p>
                    {j.citations.map((cite, index) => (
                      <blockquote className="evidence-quote" key={index}>
                        <span>
                          {cite.evidence_id}
                          <Check className="size-3" />
                        </span>
                        <p>“{cite.quote}”</p>
                      </blockquote>
                    ))}
                    <small className="flex items-center gap-1.5 text-xs text-slate-400">
                      <ShieldCheck className="size-3.5" />
                      {j.citation_check?.replaceAll("_", " ") ||
                        "Evidence check completed"}
                    </small>
                  </div>
                ))
              ) : (
                <Empty title="No checkable claim extracted">
                  The text may be opinion, commentary or another non-factual
                  assertion.
                </Empty>
              )
            ) : (
              <Empty
                title={
                  c.status === "deleted"
                    ? "Content removed"
                    : c.status === "blocked"
                      ? "Investigation needs attention"
                      : "Your agents are investigating"
                }
              >
                <span className="flex items-center justify-center gap-2">
                  {c.status === "processing" && <span className="status-dot" />}
                  {c.stage}
                </span>
              </Empty>
            )}
          </Card>
          {result && (
            <>
              <Card className="p-6 sm:p-7">
                <SectionTitle
                  title="Source library"
                  description="Original material retrieved for this investigation."
                />
                {result.evidence.length ? (
                  result.evidence.map((e) => (
                    <div className="source-record" key={e.id}>
                      <div className="source-record-head">
                        <span className="source-number">{e.id}</span>
                        <div className="min-w-0 flex-1">
                          <External url={e.url}>{e.title || e.url}</External>
                          <p>
                            {e.host} · Retrieved {stamp(e.retrieved_at)}
                          </p>
                        </div>
                        <Badge value={e.status} />
                      </div>
                      {e.error ? (
                        <Notice tone="error">{e.error}</Notice>
                      ) : (
                        <details className="disclosure">
                          <summary>
                            Read captured source
                            <ChevronRight className="ml-auto size-4" />
                          </summary>
                          <pre className="source-text">{e.text}</pre>
                        </details>
                      )}
                      <div className="mt-3 break-all text-[10px] text-slate-400">
                        SHA-256 {e.sha256?.slice(0, 22)}…
                        {e.duplicate_content
                          ? " · Duplicate source content"
                          : ""}
                        {e.published_at ? " · Published " + e.published_at : ""}
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">
                    No sources were supplied or retrieved.
                  </p>
                )}
              </Card>
              <Card className="p-6">
                <SectionTitle title="Limits & open questions" />
                <ul className="space-y-3">
                  {result.limitations.map((limit, i) => (
                    <li
                      className="flex gap-3 text-sm leading-6 text-slate-500"
                      key={i}
                    >
                      <Circle className="mt-2 size-1.5 shrink-0 fill-current" />
                      {limit}
                    </li>
                  ))}
                </ul>
              </Card>
            </>
          )}
        </div>
        <aside className="min-w-0 space-y-6">
          <Card className="p-6">
            <SectionTitle
              title="Agent activity"
              action={
                result ? (
                  <span className="text-xs text-slate-400">
                    {(result.elapsed_ms / 1000).toFixed(1)}s total
                  </span>
                ) : undefined
              }
            />
            <div className="agent-timeline">
              {roles.map((role, i) => {
                const run = c.runs.filter((r) => r.role === role.id).at(-1);
                return (
                  <div className="timeline-item" key={role.id}>
                    <span
                      className={`timeline-marker ${run?.status === "complete" ? "done" : ""}`}
                    >
                      {run?.status === "complete" ? (
                        <Check className="size-3.5" />
                      ) : (
                        i + 1
                      )}
                    </span>
                    <div className="min-w-0">
                      <h3>{role.name}</h3>
                      <p>{run?.model || "Awaiting assignment"}</p>
                      {run && (
                        <>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <Badge value={run.status} />
                            {run.elapsed_ms && (
                              <span className="text-[11px] text-slate-400">
                                {(run.elapsed_ms / 1000).toFixed(1)}s
                              </span>
                            )}
                          </div>
                          {run.error && (
                            <p className="mt-3 text-xs text-red-700">
                              {run.error}
                            </p>
                          )}
                          {run.output != null && (
                            <details className="mt-3">
                              <summary className="text-xs text-slate-500">
                                Inspect structured output
                              </summary>
                              <pre className="json-code mt-2">
                                {JSON.stringify(run.output, null, 2)}
                              </pre>
                            </details>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
          {result && (
            <Reviewer c={c} key={c.id + (c.review?.decision || "new")} />
          )}{" "}
          {c.account && (
            <Card className="p-6">
              <SectionTitle title="Account history" />
              <strong className="text-3xl font-medium">
                {c.account.eligible_incidents}
              </strong>
              <p className="my-3 text-sm text-slate-500">
                Eligible confirmed incidents
              </p>
              <Badge value={c.account.escalation} />
              <p className="mt-4 text-xs text-slate-400">
                No external account action is issued.
              </p>
            </Card>
          )}
        </aside>
      </div>
    </>
  );
}
