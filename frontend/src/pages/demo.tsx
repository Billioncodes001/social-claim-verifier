import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  Clock3,
  FileText,
  Link2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import {
  api,
  field,
  lines,
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
  CaseList,
  Checkbox,
  Consent,
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
  type DemoData,
  type SocialAccount,
  type SocialPost,
} from "../types";

export const sampleText = "Apollo 11 first landed humans on the Moon in 1972.";
export const sampleSource = "https://www.nasa.gov/mission/apollo-11/";
export function PostForm({
  demo = false,
  sample = 0,
}: {
  demo?: boolean;
  sample?: number;
}) {
  const [text, setText] = useState(""),
    [evidence, setEvidence] = useState(""),
    [platform, setPlatform] = useState("manual"),
    [source, setSource] = useState("");
  useEffect(() => {
    if (sample) {
      setText(sampleText);
      setEvidence(sampleSource);
      setPlatform("manual");
      setSource("");
    }
  }, [sample]);
  return (
    <Form
      id={demo ? "demo-form" : "investigate-form"}
      onSubmit={async (f) => {
        const content = {
          platform,
          text,
          source_url: source,
          evidence_urls: lines(f),
          allow_external_processing: f.has("external"),
          allow_web_search: f.has("search"),
        };
        const id = crypto.randomUUID();
        const result = await send<{ case_id: string; duplicate: boolean }>(
          demo ? "/demo/investigate" : "/content-events",
          demo
            ? content
            : {
                ...content,
                event_id: id,
                content_id: id,
                author_ref: field(f, "author"),
              },
        );
        await refresh();
        navigate("case/" + result.case_id);
      }}
    >
      <div className="form-section-label">
        <span>01</span>Original content
      </div>
      <div className={demo ? "" : "grid gap-5 sm:grid-cols-2"}>
        <Field label="Platform">
          <select
            name="platform"
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
          >
            {(demo
              ? ["manual", "x", "facebook", "instagram"]
              : Object.keys(platformNames)
            ).map((p) => (
              <option key={p} value={p}>
                {platformNames[p]}
              </option>
            ))}
          </select>
        </Field>
        {!demo && (
          <Field label="Author reference (optional)">
            <input
              name="author"
              placeholder="Public handle or platform reference"
            />
          </Field>
        )}
      </div>
      <Field label="Post text or caption">
        <textarea
          name="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={16000}
          required
          rows={6}
          placeholder="Paste the original wording. Include any quotation, correction or context."
        />
      </Field>
      <div className="-mt-3 flex justify-between text-xs text-slate-400">
        <span>Keep the original context intact.</span>
        <span>{text.length.toLocaleString()} / 16,000</span>
      </div>
      <Field
        label="Original post URL (optional)"
        hint="Used for attribution. Paste the text above, or select a post from a connected account."
      >
        <input
          name="source_url"
          type="url"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="https://…"
        />
      </Field>
      <div className="form-divider" />
      <div className="form-section-label">
        <span>02</span>Supporting evidence
      </div>
      <Field
        label="Evidence URLs (optional)"
        hint="Add up to six public sources, one per line. Or allow configured evidence search below."
      >
        <textarea
          name="evidence"
          rows={2}
          value={evidence}
          onChange={(e) => setEvidence(e.target.value)}
          placeholder="https://original-source.com/article"
        />
      </Field>
      <Consent />
      <div className="submit-row">
        <Button type="submit">
          <ShieldCheck className="size-4" />
          {demo ? "Fact-check this post" : "Start investigation"}
          <ArrowRight className="ml-2 size-4" />
        </Button>
        <span>
          <ShieldCheck className="size-3.5" />
          {demo ? "No account strikes" : "Human review follows"}
        </span>
      </div>
    </Form>
  );
}
function ConnectedAccount({ account: a }: { account: SocialAccount }) {
  const [posts, setPosts] = useState<SocialPost[] | null>(null);
  const { notify } = useApp();
  return (
    <Card className="p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <PlatformMark platform={a.provider} />
          <div>
            <h3 className="font-semibold">{a.display_name}</h3>
            <p className="mt-1 text-xs text-slate-500">
              {platformNames[a.provider]} · Last fetched {stamp(a.last_sync)}
            </p>
          </div>
        </div>
        <Badge value={a.status} />
      </div>
      {a.error && (
        <Notice tone="error" className="mb-4">
          {a.error}
        </Notice>
      )}
      <Form
        onSubmit={async (f) => {
          const result = await send<{ posts: SocialPost[] }>(
            "/social/accounts/" + a.id + "/posts",
            { source_url: field(f, "source_url") },
          );
          setPosts(result.posts);
          await refresh();
        }}
      >
        <Field
          label="Post URL (optional)"
          hint="Leave blank to fetch up to 10 recent posts from this account."
        >
          <input type="url" name="source_url" placeholder="https://…" />
        </Field>
        <Button type="submit" variant="secondary">
          <RefreshCw className="size-4" />
          Fetch posts
        </Button>
      </Form>
      {posts && (
        <div className="mt-6 space-y-4">
          {posts.length ? (
            posts.map((p) => (
              <div
                className="rounded-lg border border-slate-200 bg-stone-50 p-5"
                key={p.id}
              >
                <div className="mb-4 flex flex-wrap justify-between gap-2 text-xs">
                  <External url={p.source_url}>Original post</External>
                  <span className="text-slate-500">{stamp(p.posted_at)}</span>
                </div>
                <p className="mb-5 whitespace-pre-wrap text-sm leading-7">
                  {p.text}
                </p>
                <Form
                  onSubmit={async (f) => {
                    const result = await send<{ case_id: string }>(
                      "/demo/investigate",
                      {
                        post_id: p.id,
                        evidence_urls: lines(f),
                        allow_external_processing: f.has("external"),
                        allow_web_search: f.has("search"),
                      },
                    );
                    await refresh();
                    navigate("case/" + result.case_id);
                  }}
                >
                  <Field label="Evidence URLs (optional)">
                    <textarea
                      name="evidence"
                      rows={2}
                      placeholder="One original source per line"
                    />
                  </Field>
                  <Consent />
                  <Button type="submit">
                    Check this post
                    <ArrowRight className="size-4" />
                  </Button>
                </Form>
              </div>
            ))
          ) : (
            <Empty title="No text posts returned">
              You can still paste the original caption in the post demo.
            </Empty>
          )}
        </div>
      )}
      <details className="disclosure mt-6">
        <summary>
          <Clock3 className="size-4" />
          <span>Automatic checks</span>
          <Badge value={a.monitor.enabled ? "active" : "off"} />
          <ChevronRight className="ml-auto size-4" />
        </summary>
        <div className="pt-5">
          <Form
            onSubmit={async (f) => {
              await send(
                "/social/accounts/" + a.id + "/monitor",
                {
                  enabled: f.has("enabled"),
                  interval_minutes: Number(f.get("interval")),
                  batch_limit: Number(f.get("limit")),
                  allow_external_processing: f.has("external"),
                  allow_web_search: f.has("search"),
                },
                "PUT",
              );
              notify("Monitoring settings saved");
              await refresh();
            }}
          >
            <Checkbox name="enabled" defaultChecked={a.monitor.enabled}>
              Check this account’s latest posts while the server is running
            </Checkbox>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Interval (minutes)">
                <input
                  name="interval"
                  type="number"
                  min={5}
                  max={1440}
                  defaultValue={a.monitor.interval_minutes}
                  required
                />
              </Field>
              <Field label="Latest posts per check">
                <input
                  name="limit"
                  type="number"
                  min={1}
                  max={5}
                  defaultValue={a.monitor.batch_limit}
                  required
                />
              </Field>
            </div>
            <Consent
              external={a.monitor.allow_external_processing}
              search={a.monitor.allow_web_search}
            />
            <p className="text-xs leading-5 text-slate-500">
              Uses your daily demo allowance. Unchanged posts are skipped. This
              samples recent posts; it does not archive the full feed.
            </p>
            <Button type="submit" variant="secondary">
              Save monitoring
            </Button>
          </Form>
        </div>
      </details>
      <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-slate-100 pt-5">
        <Action
          variant="ghost"
          onAction={async () => {
            await api("/social/accounts/" + a.id, { method: "DELETE" });
            notify(
              "Account disconnected. Local tokens and cached posts removed.",
            );
            await refresh();
          }}
        >
          <Link2 className="size-4" />
          Disconnect
        </Action>
        <span className="text-xs text-slate-500">
          Existing investigations remain until deleted.
        </span>
      </div>
    </Card>
  );
}
export function Demo() {
  const { data: d, isPending, error } = useResource<DemoData>("/demo");
  const { user, notify } = useApp();
  const [tab, setTab] = useState("paste"),
    [sample, setSample] = useState(0);
  useEffect(() => {
    const notice = new URLSearchParams(location.hash.split("?")[1] || "").get(
      "notice",
    );
    if (notice) {
      notify(
        notice === "connected"
          ? "Account connected. Fetch recent posts to begin."
          : "Connection could not complete. Review your app settings and the connection message.",
      );
      if (notice === "connected") setTab("accounts");
      history.replaceState(null, "", "#demo");
    }
  }, [notify]);
  if (!d) return <QueryState loading={isPending} error={error} />;
  return (
    <>
      <PageHead
        title="Demo lab"
        description="Experience the complete verification workflow, from claim to context."
        eyebrow="EXPLORE THE WORKSPACE"
        action={
          <div className="quota">
            <span className="quota-icon">
              <FlaskIcon />
            </span>
            <div>
              <strong>
                {d.used_today}
                <span> / {d.daily_limit}</span>
              </strong>
              <small>checks today · UTC</small>
            </div>
          </div>
        }
      />
      <section className="demo-hero">
        <div className="demo-hero-copy">
          <div className="eyebrow">
            <span className="status-dot" />
            LIVE VERIFICATION DEMO
          </div>
          <h2>
            Every claim deserves
            <br />
            <em>a closer look.</em>
          </h2>
          <p>
            Bring a social post. Let your agents examine the evidence, question
            the context and build a reviewable assessment.
          </p>
          <div className="hero-points">
            <span>
              <Check className="size-3.5" />
              Original sources
            </span>
            <span>
              <Check className="size-3.5" />
              Four specialist roles
            </span>
            <span>
              <Check className="size-3.5" />
              Human judgment
            </span>
          </div>
        </div>
        <div className="demo-hero-photo">
          <img
            src="/assets/apollo-earthrise.jpg"
            alt="Earth rising above the Moon, captured by the Apollo 11 crew"
          />
          <div className="photo-caption">
            <span>THE VALUE OF PERSPECTIVE</span>
            <p>Apollo 11, through the original lens.</p>
            <External url="https://images.nasa.gov/details/as11-44-6550">
              NASA · AS11-44-6550
            </External>
          </div>
        </div>
      </section>
      <div className="demo-grid">
        <div className="min-w-0">
          <Card>
            <div
              className="demo-tabs"
              role="tablist"
              aria-label="Demo input method"
            >
              <button
                role="tab"
                id="paste-tab"
                aria-selected={tab === "paste"}
                aria-controls="paste-panel"
                tabIndex={tab === "paste" ? 0 : -1}
                onClick={() => setTab("paste")}
                onKeyDown={(e) => {
                  if (e.key === "ArrowRight") {
                    setTab("accounts");
                    document.getElementById("accounts-tab")?.focus();
                  }
                }}
              >
                <FileText className="size-4" />
                Paste a post
              </button>
              <button
                role="tab"
                id="accounts-tab"
                aria-selected={tab === "accounts"}
                aria-controls="accounts-panel"
                tabIndex={tab === "accounts" ? 0 : -1}
                onClick={() => setTab("accounts")}
                onKeyDown={(e) => {
                  if (e.key === "ArrowLeft") {
                    setTab("paste");
                    document.getElementById("paste-tab")?.focus();
                  }
                }}
              >
                <Link2 className="size-4" />
                Connected accounts<span>{d.accounts.length}</span>
              </button>
            </div>
            <div
              id="paste-panel"
              role="tabpanel"
              aria-labelledby="paste-tab"
              hidden={tab !== "paste"}
              className="p-6 sm:p-7"
            >
              <SectionTitle
                title="Start with the original post"
                description="Your first evidence-backed assessment is a post away."
              />
              <PostForm demo sample={sample} />
            </div>
            <div
              id="accounts-panel"
              role="tabpanel"
              aria-labelledby="accounts-tab"
              hidden={tab !== "accounts"}
              className="p-6"
            >
              <SectionTitle
                title="Your connected accounts"
                description="Choose a recent post or enable periodic checks."
                action={
                  <Action
                    variant="ghost"
                    aria-label="Refresh accounts"
                    onAction={refresh}
                  >
                    <RefreshCw className="size-4" />
                  </Action>
                }
              />
              {d.accounts.length ? (
                <div className="space-y-4">
                  {d.accounts.map((a) => (
                    <ConnectedAccount account={a} key={a.id} />
                  ))}
                </div>
              ) : (
                <Empty
                  title="Your accounts belong here"
                  action={
                    user.role === "admin" ? (
                      <Button
                        variant="secondary"
                        onClick={() => navigate("socialapps")}
                      >
                        Set up a platform app
                        <ArrowRight className="size-4" />
                      </Button>
                    ) : undefined
                  }
                >
                  Connect an account using your organization’s approved
                  developer app. You can use the pasted-post demo right away.
                </Empty>
              )}
            </div>
          </Card>
          <div className="demo-privacy">
            <ShieldCheck className="mt-0.5 size-4 shrink-0" />
            <p>
              Demo checks never create account strikes. Text and captions are
              analyzed; image, video and audio content are not inspected.
              Administrators can review demo investigations.
            </p>
          </div>
        </div>
        <aside className="space-y-5">
          <Card className="p-6">
            <SectionTitle
              title="Connect your channels"
              description="Use an account you authorize."
            />
            <div className="channel-list">
              {d.platforms.map((p) => (
                <div className="channel-item" key={p.provider}>
                  <div className="flex items-center gap-3">
                    <PlatformMark platform={p.provider} />
                    <div className="min-w-0 flex-1">
                      <h3>{platformNames[p.provider]}</h3>
                      <span>
                        {!p.enabled
                          ? "Disabled"
                          : p.configured
                            ? "App configured"
                            : "Customer app required"}
                      </span>
                    </div>
                    {p.configured && p.enabled ? (
                      <Action
                        className="icon-button"
                        variant="ghost"
                        aria-label={"Connect " + platformNames[p.provider]}
                        onAction={async () => {
                          const result = await send<{
                            authorization_url: string;
                          }>("/social/connect/" + p.provider);
                          location.assign(result.authorization_url);
                        }}
                      >
                        <Plus className="size-4" />
                      </Action>
                    ) : user.role === "admin" ? (
                      <a
                        className="icon-button"
                        href={p.enabled ? "#socialapps" : "#deployment"}
                        aria-label={"Configure " + platformNames[p.provider]}
                      >
                        <ArrowUpRight className="size-4" />
                      </a>
                    ) : null}
                  </div>
                  <p>
                    {p.provider === "instagram"
                      ? "Business / creator accounts. Personal accounts can paste a caption."
                      : p.provider === "facebook"
                        ? "Your posts, with approved read permissions."
                        : "Personal accounts through OAuth 2.0."}
                  </p>
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-start gap-2 text-xs leading-5 text-slate-500">
              <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />
              Read-only authorization. We never request your social password.
            </div>
          </Card>
          <Card className="example-card">
            <div className="example-photo">
              <img
                src="/assets/apollo-lunar-module.jpg"
                alt="Apollo 11 lunar module above the Moon, photographed from the command module"
                loading="lazy"
              />
              <span>GUIDED EXAMPLE</span>
            </div>
            <div className="p-5">
              <h3>A date worth checking.</h3>
              <p>
                Was the first Moon landing in 1972? Follow the original NASA
                record to find out.
              </p>
              <button
                className="text-link"
                onClick={() => {
                  setSample((v) => v + 1);
                  setTab("paste");
                  document.getElementById("demo-form")?.scrollIntoView({
                    behavior: matchMedia("(prefers-reduced-motion: reduce)")
                      .matches
                      ? "instant"
                      : "smooth",
                    block: "center",
                  });
                }}
              >
                Load the example
                <ArrowRight className="size-4" />
              </button>
              <div className="mt-4 text-[10px] text-slate-400">
                Image: NASA · AS11-44-6642
              </div>
            </div>
          </Card>
          <div className="process-list">
            <span className="eyebrow">HOW YOUR AGENTS WORK</span>
            {roles.map((r, i) => (
              <div key={r.id}>
                <span>{String(i + 1).padStart(2, "0")}</span>
                <p>{r.short}</p>
                <ChevronRight className="size-3.5" />
              </div>
            ))}
          </div>
        </aside>
      </div>
      {d.connection_notice && (
        <Notice tone="error" className="mt-6">
          {d.connection_notice}
        </Notice>
      )}
      <Card className="mt-8 overflow-hidden">
        <div className="px-6 pt-6">
          <SectionTitle
            title="Your recent demo checks"
            description="A record of the claims you have explored."
            action={
              <span className="text-xs text-slate-400">
                Post cache · 24 hours
              </span>
            }
          />
        </div>
        <CaseList
          cases={d.cases}
          action={(c) =>
            c.status !== "deleted" ? (
              <Action
                variant="ghost"
                className="mr-4"
                aria-label={"Delete demo check: " + c.text.slice(0, 50)}
                onAction={async () => {
                  await api("/demo/cases/" + c.id, { method: "DELETE" });
                  notify("Demo content and agent outputs deleted");
                  await refresh();
                }}
              >
                <Trash2 className="size-4" />
              </Action>
            ) : null
          }
        />
      </Card>
    </>
  );
}
function FlaskIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path d="M9 3h6M10 3v7l-5 8a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-8V3M8 15h8" />
    </svg>
  );
}
