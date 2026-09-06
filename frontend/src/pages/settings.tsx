import { useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  Code2,
  Copy,
  KeyRound,
  Link2,
  LockKeyhole,
  PlugZap,
  Plus,
  Server,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import {
  api,
  field,
  navigate,
  refresh,
  send,
  stamp,
  useResource,
} from "../api";
import {
  Action,
  Badge,
  Button,
  Card,
  Checkbox,
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
  type Assignment,
  type AuditEntry,
  type Connection,
  type Dashboard,
  type Deployment,
  type PlatformProfile,
  type Policy,
  type SocialApp,
  type Token,
  type WorkspaceConfig,
} from "../types";

export function Agents() {
  const { data: d, isPending, error } = useResource<Dashboard>("/dashboard");
  const { user, notify } = useApp();
  if (!d) return <QueryState loading={isPending} error={error} />;
  return (
    <>
      <PageHead
        title="An expert in every role."
        description="Build a verification team around your organization’s models and priorities."
        eyebrow="YOUR AGENT TEAM"
        action={
          user.role === "admin" ? (
            <Button variant="secondary" onClick={() => navigate("connections")}>
              <Plus className="size-4" />
              Add an AI connection
            </Button>
          ) : undefined
        }
      />
      <div className="agent-page-intro">
        <div className="flex items-center gap-3">
          <span className="step-circle">
            <ShieldCheck className="size-5" />
          </span>
          <div>
            <h2>Four roles. One reviewable record.</h2>
            <p>
              Choose a primary model and an optional fallback for each
              specialist.
            </p>
          </div>
        </div>
        <Badge value={d.roles.length === 4 ? "ready" : "setup"}>
          {d.roles.length} / 4 assigned
        </Badge>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        {roles.map((role, i) => {
          const assigned = d.roles.find((r) => r.role === role.id);
          return (
            <Card className="agent-setting-card" key={role.id}>
              <div className="mb-6 flex items-start justify-between">
                <span className="agent-index">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <Badge value={assigned ? "ready" : "setup"}>
                  {assigned ? "Assigned" : "Needs a model"}
                </Badge>
              </div>
              <h2>{role.name}</h2>
              <p>{role.description}</p>
              <Form
                key={`${assigned?.connection_id || ""}:${assigned?.fallback_id || ""}`}
                onSubmit={async (f) => {
                  await send(
                    "/agents/" + role.id,
                    {
                      connection_id: field(f, "connection_id"),
                      fallback_id: field(f, "fallback_id") || null,
                    },
                    "PUT",
                  );
                  notify("Agent assignment saved");
                  await refresh();
                }}
              >
                <Field label="Primary connection">
                  <select
                    name="connection_id"
                    required
                    defaultValue={assigned?.connection_id || ""}
                    disabled={user.role !== "admin"}
                  >
                    <option value="">Select a model connection</option>
                    {d.connections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} · {c.model}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Fallback connection">
                  <select
                    name="fallback_id"
                    defaultValue={assigned?.fallback_id || ""}
                    disabled={user.role !== "admin"}
                  >
                    <option value="">No fallback</option>
                    {d.connections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </Field>
                {user.role === "admin" && (
                  <Button type="submit" variant="secondary">
                    Save assignment
                    <Check className="size-4" />
                  </Button>
                )}
              </Form>
            </Card>
          );
        })}
      </div>
      <Notice className="mt-6">
        Roles can share a model or use different providers. Agreement between
        agents does not establish truth; findings must be grounded in retrieved
        evidence and reviewed by your team.
      </Notice>
    </>
  );
}

type ConnectionsData = {
  connections: Connection[];
  roles: Assignment[];
  search: { provider: string; credential_configured: boolean };
};
export function Connections() {
  const {
    data: d,
    isPending,
    error,
  } = useResource<ConnectionsData>("/connections");
  const { notify } = useApp();
  const [kind, setKind] = useState("openai_responses"),
    [base, setBase] = useState("https://api.openai.com/v1"),
    [local, setLocal] = useState(false),
    [name, setName] = useState(""),
    [model, setModel] = useState("");
  if (!d) return <QueryState loading={isPending} error={error} />;
  return (
    <>
      <PageHead
        title="Connected intelligence."
        description="Bring your AI providers and evidence search into a single private workspace."
        eyebrow="AI CONNECTIONS"
      />
      <div className="space-y-6">
        <Card className="p-6">
          <SectionTitle
            title="Your model connections"
            description="Test each endpoint before assigning it to your team."
            action={
              <Badge value="configured">
                {d.connections.length} configured
              </Badge>
            }
          />
          {d.connections.length ? (
            <div className="divide-y divide-slate-100">
              {d.connections.map((c) => (
                <div className="connection-row" key={c.id}>
                  <span className="connection-icon">
                    <Server className="size-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <h3>{c.name}</h3>
                    <p>
                      {c.model} · {c.kind.replaceAll("_", " ")}
                    </p>
                    <small>{c.base_url}</small>
                  </div>
                  <span className="hidden text-xs text-slate-500 sm:inline">
                    {c.local_endpoint
                      ? "Local endpoint"
                      : c.credential_configured
                        ? "Key encrypted"
                        : "No key set"}
                  </span>
                  <Action
                    onAction={async () => {
                      const result = await send<{ elapsed_ms: number }>(
                        "/connections/" + c.id + "/test",
                      );
                      notify(
                        "Connection verified in " +
                          (result.elapsed_ms / 1000).toFixed(1) +
                          " seconds",
                      );
                    }}
                  >
                    <PlugZap className="size-4" />
                    Test connection
                  </Action>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-sm text-slate-500">
              Add your first model below to activate the agent team.
            </div>
          )}
        </Card>
        <div className="content-grid">
          <Card className="p-6 sm:p-7">
            <SectionTitle
              title="Add an AI connection"
              description="Hosted APIs and local model servers are supported."
            />
            <Form
              onSubmit={async (f, form) => {
                await send("/connections", {
                  name,
                  kind,
                  base_url: base,
                  model,
                  api_key: String(f.get("api_key") || ""),
                  local_endpoint: local,
                });
                notify(
                  "Connection added. Unassigned agents now use this model.",
                );
                form.querySelector<HTMLInputElement>(
                  'input[name="api_key"]',
                )!.value = "";
                await refresh();
              }}
            >
              <div className="grid gap-5 sm:grid-cols-2">
                <Field label="Connection name">
                  <input
                    name="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    placeholder="e.g. Research model"
                  />
                </Field>
                <Field label="API protocol">
                  <select
                    name="kind"
                    value={kind}
                    onChange={(e) => {
                      setKind(e.target.value);
                      setBase(
                        e.target.value === "anthropic"
                          ? "https://api.anthropic.com/v1"
                          : e.target.value === "agent_endpoint"
                            ? ""
                            : "https://api.openai.com/v1",
                      );
                    }}
                  >
                    <option value="openai_responses">OpenAI Responses</option>
                    <option value="openai_chat">OpenAI-compatible Chat</option>
                    <option value="anthropic">Anthropic Messages</option>
                    <option value="agent_endpoint">
                      Custom agent endpoint
                    </option>
                  </select>
                </Field>
              </div>
              <Field label="Base URL">
                <input
                  name="base_url"
                  type="url"
                  value={base}
                  onChange={(e) => setBase(e.target.value)}
                  required
                />
              </Field>
              <Field label="Model ID">
                <input
                  name="model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  required
                  placeholder="A model available to your API account"
                />
              </Field>
              <Field
                label="API key"
                hint="Stored encrypted. Never returned by the API."
              >
                <input
                  name="api_key"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Enter your provider’s key"
                />
              </Field>
              <Checkbox
                name="local_endpoint"
                checked={local}
                onChange={setLocal}
              >
                This is a local model server (loopback addresses only)
              </Checkbox>
              <div className="flex flex-wrap gap-3">
                <Button type="submit">
                  <Plus className="size-4" />
                  Add connection
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setName("Local Qwen · development");
                    setKind("openai_chat");
                    setBase("http://127.0.0.1:8087/v1");
                    setModel("qwen3-4b-local");
                    setLocal(true);
                  }}
                >
                  Use local preset
                </Button>
              </div>
            </Form>
          </Card>
          <div className="space-y-6">
            <Card className="p-6">
              <SectionTitle
                title="Evidence search"
                description="Help your agents find original sources."
              />
              <Form
                onSubmit={async (f, form) => {
                  await send(
                    "/search",
                    {
                      provider: field(f, "provider"),
                      api_key: String(f.get("api_key") || ""),
                    },
                    "PUT",
                  );
                  notify("Search settings saved");
                  form.querySelector<HTMLInputElement>(
                    'input[name="api_key"]',
                  )!.value = "";
                  await refresh();
                }}
              >
                <Field label="Search provider">
                  <select name="provider" defaultValue={d.search.provider}>
                    <option value="none">Supplied source URLs only</option>
                    <option value="tavily">Tavily · web search</option>
                    <option value="wikipedia">
                      Wikipedia · background research
                    </option>
                  </select>
                </Field>
                <Field label="Tavily API key">
                  <input
                    name="api_key"
                    type="password"
                    autoComplete="new-password"
                    placeholder={
                      d.search.credential_configured
                        ? "Stored; leave blank to keep"
                        : "Required for Tavily"
                    }
                  />
                </Field>
                <Button type="submit" variant="secondary">
                  Save search settings
                </Button>
              </Form>
            </Card>
            <Notice>
              Hosted requests may incur provider usage charges. Local-only
              submissions cannot be sent to hosted models, including fallback
              providers.
            </Notice>
            <Card className="p-6">
              <SectionTitle title="Custom agent contract" />
              <p className="text-sm leading-6 text-slate-500">
                Agent endpoints receive a role, instructions, input and response
                schema. Return a structured result with optional usage details.
              </p>
              <pre className="json-code mt-4">
                {'{ "result": { … }, "usage": { … } }'}
              </pre>
            </Card>
          </div>
        </div>
      </div>
    </>
  );
}

const exampleEvent = {
  event_id: "unique-event-id",
  platform: "partner_feed",
  content_id: "post-123",
  revision: 1,
  text: "The original post text",
  author_ref: "verified-platform-id",
  author_verified: true,
  evidence_urls: [],
  allow_external_processing: false,
  allow_web_search: false,
};
export function Integrations() {
  const { data, isPending, error } = useResource<Token[]>("/tokens");
  const { notify } = useApp();
  const [token, setToken] = useState("");
  if (!data) return <QueryState loading={isPending} error={error} />;
  return (
    <>
      <PageHead
        title="Built to connect."
        description="Feed authorized platform content into the same evidence workflow."
        eyebrow="PLATFORM INTEGRATIONS"
      />
      <div className="content-grid">
        <div className="space-y-6">
          <Card className="p-6">
            <SectionTitle
              title="Integration tokens"
              description="Scoped credentials for your trusted ingestion services."
            />
            <Form
              onSubmit={async (f) => {
                const result = await send<{ token: string }>("/tokens", {
                  name: field(f, "name"),
                });
                setToken(result.token);
                await refresh();
              }}
            >
              <Field label="Integration name">
                <input
                  name="name"
                  required
                  placeholder="e.g. Platform staging feed"
                />
              </Field>
              <Button type="submit">
                <KeyRound className="size-4" />
                Create token
              </Button>
            </Form>
            {token && (
              <div className="mt-5">
                <Notice tone="success">
                  Copy this token now. It will only be shown once.
                </Notice>
                <pre className="json-code mt-3">{token}</pre>
                <Action
                  variant="ghost"
                  className="mt-2"
                  onAction={async () => {
                    await navigator.clipboard.writeText(token);
                    notify("Integration token copied");
                  }}
                >
                  <Copy className="size-4" />
                  Copy token
                </Action>
              </div>
            )}
            <div className="mt-6 divide-y divide-slate-100">
              {data.map((t) => (
                <div
                  key={t.id}
                  className="flex items-center justify-between gap-4 py-4"
                >
                  <div>
                    <h3 className="text-sm font-medium">{t.name}</h3>
                    <p className="mt-1 text-xs text-slate-400">
                      Created {stamp(t.created)}
                    </p>
                  </div>
                  <Action
                    variant="ghost"
                    aria-label={"Revoke " + t.name}
                    onAction={async () => {
                      await api("/tokens/" + t.id, { method: "DELETE" });
                      notify("Integration token revoked");
                      await refresh();
                    }}
                  >
                    <Trash2 className="size-4" />
                    Revoke
                  </Action>
                </div>
              ))}
            </div>
          </Card>
          <Notice>
            Integration tokens can submit content events. They cannot read
            cases, change policies or manage AI credentials.
          </Notice>
        </div>
        <Card className="p-6">
          <SectionTitle
            title="One event contract"
            description="Send a bearer-authenticated request to the intake API."
          />
          <div className="endpoint-label">
            <span>POST</span>
            <code>/api/content-events</code>
          </div>
          <pre className="json-code mt-5">
            {JSON.stringify(exampleEvent, null, 2)}
          </pre>
          <p className="my-5 text-xs leading-6 text-slate-500">
            Reusing an event ID with an identical payload is safe. Edits and
            deletions require an increasing revision. Set event_type to edited
            or deleted.
          </p>
          <a
            href="/api/openapi.json"
            target="_blank"
            rel="noreferrer"
            className="text-link"
          >
            Open API specification
            <ArrowUpRight className="size-4" />
          </a>
          <div className="mt-6 border-t border-slate-100 pt-5 text-xs leading-6 text-slate-500">
            The demo includes customer-authorized X, Facebook and professional
            Instagram account adapters. WhatsApp and platform-wide feeds require
            an authorized customer ingestion service. External account actions
            are not connected.
          </div>
        </Card>
      </div>
    </>
  );
}

function PolicyFields({ policy }: { policy: Policy }) {
  return (
    <>
      <Field label="Incident window (days)">
        <input
          name="window_days"
          type="number"
          min={1}
          max={730}
          defaultValue={policy.window_days}
          required
        />
      </Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Admin review threshold">
          <input
            name="admin_threshold"
            type="number"
            min={2}
            max={10}
            defaultValue={policy.admin_threshold}
            required
          />
        </Field>
        <Field label="Senior review threshold">
          <input
            name="senior_threshold"
            type="number"
            min={3}
            max={20}
            defaultValue={policy.senior_threshold}
            required
          />
        </Field>
      </div>
    </>
  );
}
const policyValues = (f: FormData) => ({
  window_days: Number(f.get("window_days")),
  admin_threshold: Number(f.get("admin_threshold")),
  senior_threshold: Number(f.get("senior_threshold")),
});
export function PolicyPage() {
  const { data: d, isPending, error } = useResource<Dashboard>("/dashboard");
  const { notify } = useApp();
  if (!d) return <QueryState loading={isPending} error={error} />;
  return (
    <>
      <PageHead
        title="A standard your team can trust."
        description="Make review and repeat-incident rules explicit, consistent and reversible."
        eyebrow="REVIEW POLICY"
      />
      <div className="content-grid">
        <Card className="p-7">
          <SectionTitle
            title="Confirmed-incident thresholds"
            description="These workspace defaults can be overridden for each platform."
          />
          <Form
            onSubmit={async (f) => {
              await send("/policy", policyValues(f), "PUT");
              notify("Review policy saved");
              await refresh();
            }}
          >
            <PolicyFields policy={d.policy} />
            <Button type="submit">
              Save policy
              <Check className="size-4" />
            </Button>
          </Form>
        </Card>
        <div className="space-y-6">
          <Card className="p-6">
            <SectionTitle title="Every incident has a record" />
            <div className="space-y-5 text-sm leading-6 text-slate-500">
              {[
                "A reviewer confirms a cited adverse finding against an applicable platform rule.",
                "A verified author and distinct incident key are required. Duplicates count once.",
                "Appeals remove contested incidents from escalation. Overturned decisions stay excluded.",
              ].map((t, i) => (
                <div className="flex gap-3" key={t}>
                  <span className="step-circle">{i + 1}</span>
                  <p>{t}</p>
                </div>
              ))}
            </div>
          </Card>
          <Notice>
            Automatic account disabling and external enforcement are disabled.
            Escalations remain available for a platform administrator to review.
          </Notice>
        </div>
      </div>
    </>
  );
}

export function Audit() {
  const { data, isPending, error } = useResource<AuditEntry[]>("/audit");
  const [search, setSearch] = useState("");
  if (!data) return <QueryState loading={isPending} error={error} />;
  const entries = data.filter((e) =>
    (e.actor + " " + e.action + " " + e.subject)
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHead
        title="A record of every decision."
        description="Trace configuration changes, investigations and reviewer actions."
        eyebrow="AUDIT TRAIL"
      />
      <Card className="overflow-hidden">
        <div className="queue-toolbar">
          <Field label="Filter audit events" className="w-full max-w-md">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search actor, action or subject…"
            />
          </Field>
          <span className="text-xs text-slate-400">
            Latest {data.length} events
          </span>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Record</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id}>
                  <td className="whitespace-nowrap">{stamp(e.created)}</td>
                  <td>{e.actor}</td>
                  <td>
                    <span className="audit-action">{e.action}</span>
                  </td>
                  <td>
                    <details>
                      <summary className="cursor-pointer text-xs">
                        {e.subject.slice(0, 16) || "Workspace"}
                        <ChevronRight className="ml-1 inline size-3" />
                      </summary>
                      <pre className="json-code mt-3 max-w-lg">
                        {JSON.stringify(e.details, null, 2)}
                      </pre>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!entries.length && (
          <p className="p-8 text-center text-sm text-slate-500">
            No events match this filter.
          </p>
        )}
      </Card>
    </>
  );
}

export function WorkspaceSetup() {
  const config = useResource<WorkspaceConfig>("/workspace"),
    deployment = useResource<Deployment>("/deployment"),
    dashboard = useResource<Dashboard>("/dashboard");
  const { notify } = useApp();
  if (!config.data || !deployment.data || !dashboard.data)
    return (
      <QueryState
        loading={
          config.isPending || deployment.isPending || dashboard.isPending
        }
        error={config.error || deployment.error || dashboard.error}
      />
    );
  const { workspace: w, platforms } = config.data,
    d = deployment.data;
  return (
    <>
      <PageHead
        title="Make this workspace yours."
        description="Set your identity, platform preferences and operating boundaries."
        eyebrow="WORKSPACE SETUP"
      />
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-6 sm:p-7">
          <SectionTitle
            title="Organization & identity"
            description="A private workspace that feels like part of your team."
          />
          <Form
            onSubmit={async (f) => {
              await send(
                "/workspace",
                {
                  name: field(f, "name"),
                  organization: field(f, "organization"),
                  demo_daily_limit: Number(f.get("demo_daily_limit")),
                },
                "PUT",
              );
              notify("Workspace updated");
              await refresh();
            }}
          >
            <Field label="Product name">
              <input
                name="name"
                defaultValue={w.name}
                maxLength={70}
                required
              />
            </Field>
            <Field label="Organization / workspace name">
              <input
                name="organization"
                defaultValue={w.organization}
                maxLength={100}
                required
              />
            </Field>
            <Field
              label="Daily demo checks per user"
              hint="The allowance resets at midnight UTC."
            >
              <input
                name="demo_daily_limit"
                type="number"
                min={1}
                max={200}
                defaultValue={w.demo_daily_limit}
                required
              />
            </Field>
            <Button type="submit">
              Save workspace
              <Check className="size-4" />
            </Button>
          </Form>
        </Card>
        <Card className="p-6 sm:p-7">
          <SectionTitle
            title="Server readiness"
            action={
              <Badge value={d.ready ? "ready" : "setup"}>
                {d.ready ? "Configured" : "Setup needed"}
              </Badge>
            }
          />
          <div className="readiness-checks">
            {d.checks.map((c) => (
              <div key={c.id}>
                {c.ok ? (
                  <CheckCircle2 className="size-[18px] text-emerald-700" />
                ) : (
                  <Circle className="size-[18px] text-amber-600" />
                )}
                <p>
                  {c.label}
                  {!c.required && <small>Recommended</small>}
                </p>
              </div>
            ))}
          </div>
          <div className="server-info">
            <code>{d.public_url}</code>
            <p>
              {d.worker_count} workers · {d.queue_limit} queued or active cases
            </p>
          </div>
          <p className="mt-4 text-xs leading-5 text-slate-500">
            {d.deployment_model}. {d.assessment}
          </p>
          <Button
            variant="secondary"
            className="mt-5"
            onClick={() => navigate("connections")}
          >
            Configure AI & search
            <ArrowRight className="size-4" />
          </Button>
        </Card>
      </div>
      <Card className="mt-7 p-6 sm:p-7">
        <SectionTitle
          title="Platform profiles"
          description="Set processing permissions and escalation rules for each channel."
          action={
            <a className="text-link text-xs" href="#policy">
              Default policy
              <ArrowUpRight className="size-3.5" />
            </a>
          }
        />
        <div className="platform-profiles">
          {Object.entries(platforms).map(([key, p]) => (
            <details className="platform-profile" key={key}>
              <summary>
                <PlatformMark platform={key} />
                <div>
                  <strong>{p.display_name}</strong>
                  <span>
                    {p.policy ? "Custom escalation policy" : "Workspace policy"}
                  </span>
                </div>
                <Badge value={p.enabled ? "active" : "disabled"}>
                  {p.enabled ? "Enabled" : "Disabled"}
                </Badge>
                <ChevronRight className="ml-2 size-4" />
              </summary>
              <div className="max-w-3xl py-6 sm:pl-14">
                <Form
                  onSubmit={async (f) => {
                    await send(
                      "/platforms/" + key,
                      {
                        display_name: field(f, "display_name"),
                        enabled: f.has("enabled"),
                        allow_hosted: f.has("allow_hosted"),
                        allow_search: f.has("allow_search"),
                        policy: f.has("custom_policy") ? policyValues(f) : null,
                      },
                      "PUT",
                    );
                    notify("Platform profile saved");
                    await refresh();
                  }}
                >
                  <Field label="Display name">
                    <input
                      name="display_name"
                      defaultValue={p.display_name}
                      maxLength={70}
                      required
                    />
                  </Field>
                  <Checkbox name="enabled" defaultChecked={p.enabled}>
                    Accept content from this platform
                  </Checkbox>
                  <Checkbox name="allow_hosted" defaultChecked={p.allow_hosted}>
                    Permit hosted AI when the submission also allows it
                  </Checkbox>
                  <Checkbox name="allow_search" defaultChecked={p.allow_search}>
                    Permit evidence search when the submission also allows it
                  </Checkbox>
                  <div className="form-divider" />
                  <Checkbox
                    name="custom_policy"
                    defaultChecked={Boolean(p.policy)}
                  >
                    Use platform-specific escalation thresholds
                  </Checkbox>
                  <PolicyFields policy={p.policy || dashboard.data!.policy} />
                  <Button type="submit" variant="secondary">
                    Save {p.display_name}
                    <Check className="size-4" />
                  </Button>
                </Form>
              </div>
            </details>
          ))}
        </div>
      </Card>
      <Notice className="mt-6">
        Only eligible, human-confirmed incidents enter escalation. Demo checks
        never create strikes. External account actions are not enabled.
      </Notice>
    </>
  );
}

export function PlatformApps() {
  const {
    data: apps,
    isPending,
    error,
  } = useResource<SocialApp[]>("/social/apps");
  const { notify } = useApp();
  if (!apps) return <QueryState loading={isPending} error={error} />;
  return (
    <>
      <PageHead
        title="Your channels. Your credentials."
        description="Connect social accounts through your organization’s approved developer apps."
        eyebrow="PLATFORM APPS"
        action={
          <Button variant="secondary" onClick={() => navigate("demo")}>
            Open demo lab
            <ArrowRight className="size-4" />
          </Button>
        }
      />
      <Notice className="mb-6">
        Register each callback exactly as shown in the platform’s developer
        console. Available posts depend on the account’s granted permissions and
        the platform’s app review.
      </Notice>
      <div className="social-apps-grid">
        {apps.map((p) => (
          <Card className="social-app-card" key={p.provider}>
            <div className="mb-5 flex items-center justify-between">
              <PlatformMark platform={p.provider} />
              <Badge value={p.configured ? "ready" : "setup"}>
                {p.configured ? "Configured" : "Setup required"}
              </Badge>
            </div>
            <h2>{platformNames[p.provider]}</h2>
            <p>{p.note}</p>
            <Form
              onSubmit={async (f, form) => {
                await send(
                  "/social/apps/" + p.provider,
                  {
                    client_id: field(f, "client_id"),
                    client_secret: String(f.get("client_secret") || ""),
                    graph_version: field(f, "graph_version"),
                  },
                  "PUT",
                );
                form.querySelector<HTMLInputElement>(
                  'input[name="client_secret"]',
                )!.value = "";
                notify("Platform app configuration saved");
                await refresh();
              }}
            >
              <Field label="Client / app ID">
                <input
                  name="client_id"
                  defaultValue={p.client_id}
                  maxLength={300}
                  required
                  autoComplete="off"
                />
              </Field>
              <Field
                label={
                  p.provider === "x"
                    ? "Client secret (confidential apps)"
                    : "App secret"
                }
              >
                <input
                  name="client_secret"
                  type="password"
                  autoComplete="new-password"
                  placeholder={
                    p.credential_configured
                      ? "Stored; leave blank to keep"
                      : "Enter your developer app secret"
                  }
                />
              </Field>
              {p.provider !== "x" && (
                <Field
                  label="Graph API version"
                  hint="Use the supported version selected in your Meta developer console."
                >
                  <input
                    name="graph_version"
                    defaultValue={p.graph_version}
                    pattern={"v[0-9]{1,3}\\.0"}
                    required
                    placeholder="e.g. your app’s selected version"
                  />
                </Field>
              )}
              <Field label="OAuth callback URL">
                <input
                  name="callback"
                  readOnly
                  value={p.callback_url}
                  onFocus={(e) => e.target.select()}
                />
              </Field>
              <Action
                variant="ghost"
                type="button"
                className="!mt-2 text-xs"
                onAction={async () => {
                  await navigator.clipboard.writeText(p.callback_url);
                  notify("Callback URL copied");
                }}
              >
                <Copy className="size-3.5" />
                Copy callback
              </Action>
              <div className="scopes">
                <LockKeyhole className="size-3.5 shrink-0" />
                <span>{p.scopes}</span>
              </div>
              <Button type="submit" className="w-full">
                Save app configuration
              </Button>
            </Form>
            <p className="mt-5 !text-xs">
              Changing credentials requires existing accounts to reconnect.
            </p>
          </Card>
        ))}
      </div>
    </>
  );
}
