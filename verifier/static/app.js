"use strict";
const app = document.querySelector("#app");
const state = { user: null, route: "overview", data: null, poll: null };
const roles = {
  extractor: [
    "Claim extractor",
    "Finds factual assertions and preserves their context.",
  ],
  analyst: [
    "Evidence analyst",
    "Checks each claim against retrieved source material.",
  ],
  challenger: [
    "Independent challenger",
    "Looks for weak evidence, missing context and contradictions.",
  ],
  adjudicator: [
    "Final adjudicator",
    "Reconciles the findings and produces a cited assessment.",
  ],
};
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const tag = (v) =>
  `<span class="tag ${esc(v)}">${esc(String(v).replaceAll("_", " "))}</span>`;
const stamp = (v) =>
  v
    ? new Date(v).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
const external = (url) =>
  /^https?:\/\//i.test(url || "")
    ? `href="${esc(url)}" target="_blank" rel="noopener noreferrer"`
    : "";
function toast(text) {
  const el = document.querySelector("#toast");
  el.textContent = text;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 5000);
}
async function api(path, options = {}) {
  const res = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  let body;
  try {
    body = await res.json();
  } catch {
    throw Error("The server returned an unexpected response");
  }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/auth")) {
      state.user = null;
      auth(false);
    }
    throw Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail),
    );
  }
  return body;
}
const send = (path, body, method = "POST") =>
  api(path, { method, body: JSON.stringify(body) });
function bindForm(id, handler) {
  const form = document.querySelector(id);
  if (!form) return;
  form.querySelectorAll(".field").forEach((field) => {
    const input = field.querySelector("input,select,textarea"),
      label = field.querySelector("label");
    if (input && label && !label.htmlFor) {
      input.id ||= form.id + "-" + input.name;
      label.htmlFor = input.id;
    }
  });
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const button = form.querySelector("button[type=submit]");
    const text = button.textContent;
    button.disabled = true;
    button.textContent = "Working…";
    try {
      await handler(new FormData(form), form);
    } catch (e) {
      toast(e.message);
    } finally {
      button.disabled = false;
      button.textContent = text;
    }
  });
}
function nav(route) {
  location.hash = route;
}
function shell() {
  const links = [
    ["overview", "◫", "Overview"],
    ["queue", "☷", "Review queue"],
    ["investigate", "⌕", "Investigate"],
    ["agents", "◇", "Agent team"],
  ];
  const settings = [
    ["connections", "⇄", "Connections"],
    ["integrations", "⌘", "Integrations"],
    ["policy", "⊙", "Policy"],
    ["audit", "≡", "Audit trail"],
  ];
  const item = ([id, icon, name]) =>
    `<a href="#${id}" class="${state.route === id ? "active" : ""}"><span class="nav-icon">${icon}</span>${name}</a>`;
  app.innerHTML = `<div class="layout"><aside class="sidebar"><div class="brand"><span class="logo">cv</span>Claim Verifier</div><div class="nav-label">Workspace</div><nav class="nav">${links.map(item).join("")}</nav>${state.user.role === "admin" ? `<div class="nav-label">Administration</div><nav class="nav">${settings.map(item).join("")}</nav>` : ""}<div class="sidebar-bottom"><span class="dot"></span>Private workspace<br><small>Evidence-backed review · v0.1</small></div></aside><main class="main"><header class="topbar"><div class="topbar-left"><span class="workspace-icon">▦</span><strong>Moderation workspace</strong></div><div class="topbar-right"><span class="pill">Human review enabled</span><span class="avatar">${esc(state.user.username[0].toUpperCase())}</span><span>${esc(state.user.username)}</span><button id="logout">Sign out</button></div></header><div class="content" id="view"></div></main></div>`;
  document.querySelector("#logout").onclick = async () => {
    await send("/auth/logout", {});
    state.user = null;
    clearInterval(state.poll);
    auth(false);
  };
}
function head(title, subtitle, action = "") {
  return `<div class="pagehead"><div><div class="eyebrow">Verification workspace</div><h1>${title}</h1><p>${subtitle}</p></div>${action}</div>`;
}
function rows(cases) {
  if (!cases.length)
    return `<div class="empty"><div class="empty-icon">◎</div><h3>Your first investigation starts here</h3><p>Submit a post and let your agent team build an evidence-backed assessment.</p><button data-go="investigate">Investigate a post</button></div>`;
  return cases
    .map(
      (c) =>
        `<a class="case-row" href="#case/${c.id}"><span class="platform">${esc(c.platform.slice(0, 2).toUpperCase())}</span><div><p class="case-title">${esc(c.text || "Content removed")}</p><div class="case-meta">${esc(c.platform)} · ${stamp(c.created)}${c.author_ref ? " · " + esc(c.author_ref) : ""}</div></div>${tag(c.status)}</a>`,
    )
    .join("");
}
function goButtons() {
  document
    .querySelectorAll("[data-go]")
    .forEach((el) => (el.onclick = () => nav(el.dataset.go)));
}
async function overview() {
  const [d, cases] = await Promise.all([api("/dashboard"), api("/cases")]);
  if (state.route !== "overview") return;
  state.data = d;
  document.querySelector("#view").innerHTML =
    `${head("Overview", "A clear view of your verification operations.", `<button data-go="investigate">+ New investigation</button>`)}<section class="hero"><div><div class="eyebrow">Evidence, before action.</div><h1>Know what holds up.</h1><p>Four specialized AI agents. Original sources. One reviewable record for every claim.</p><div class="actions"><button data-go="investigate">Investigate a post ↗</button><button class="secondary" data-go="agents">Meet your agents</button></div></div><div class="hero-visual"><div class="orbit"><div class="core">✓</div><span class="orbit-tag">◇ Claims extracted</span><span class="orbit-tag">↗ Sources checked</span><span class="orbit-tag">◎ Human reviewed</span></div></div></section><div class="stats">${[
      ["Investigations", d.total, "All submitted content"],
      [
        "Agents working",
        (d.counts.queued || 0) + (d.counts.processing || 0),
        "Queued and processing",
      ],
      [
        "Awaiting review",
        d.counts.needs_review || 0,
        "Ready for a human decision",
      ],
      [
        "Needs attention",
        d.counts.blocked || 0,
        "Connection or processing issues",
      ],
    ]
      .map(
        ([l, n, f]) =>
          `<div class="stat"><label>${l}</label><div class="number">${n}</div><div class="foot">${f}</div></div>`,
      )
      .join(
        "",
      )}</div><div class="grid2"><section class="panel"><div class="panelhead"><h2>Recent investigations</h2><a href="#queue">View all →</a></div>${rows(cases.slice(0, 5))}</section><div><section class="panel"><div class="panelhead"><h2>Your agent team</h2><a href="#agents">Manage →</a></div>${Object.entries(
      roles,
    )
      .map(([role, [name]], i) => {
        const map = d.roles.find((r) => r.role === role);
        const conn = d.connections.find((c) => c.id === map?.connection_id);
        return `<div class="agent-mini"><span class="agent-num">0${i + 1}</span><div><p>${name}</p><small>${esc(conn?.name || "No model connected")}</small></div><span class="tag">${conn ? "Assigned" : "Setup"}</span></div>`;
      })
      .join(
        "",
      )}</section>${d.connections.length ? "" : `<div class="notice">Connect a model to activate the agents. Hosted APIs and local model servers are supported.</div>`}<section class="panel"><h3>Account escalations</h3>${d.escalations.length ? d.escalations.map((a) => `<p>${esc(a.author_ref)} · ${a.eligible_incidents} confirmed incidents ${tag(a.escalation)}</p>`).join("") : '<p class="muted">No accounts currently need escalation.</p>'}<small>Only reviewed, eligible incidents count. Account disabling is off.</small></section></div></div>`;
  goButtons();
}
async function queue() {
  document.querySelector("#view").innerHTML =
    head(
      "Review queue",
      "Inspect claims, follow the evidence, and record a decision.",
      `<button data-go="investigate">+ New investigation</button>`,
    ) +
    `<div class="filters"><input id="search" placeholder="Search posts or author references" aria-label="Search cases"><select id="status-filter" aria-label="Case status"><option value="">All statuses</option>${["needs_review", "processing", "queued", "blocked", "reviewed", "superseded", "deleted"].map((v) => `<option value="${v}">${v.replaceAll("_", " ")}</option>`).join("")}</select></div><section class="panel" id="case-list"></section>`;
  async function refresh() {
    const q = document.querySelector("#search")?.value || "";
    const status = document.querySelector("#status-filter")?.value || "";
    const data = await api(
      "/cases?q=" +
        encodeURIComponent(q) +
        "&status=" +
        encodeURIComponent(status),
    );
    const target = document.querySelector("#case-list");
    if (target) {
      target.innerHTML = rows(data);
      goButtons();
    }
  }
  let timer;
  document.querySelector("#search").oninput = () => {
    clearTimeout(timer);
    timer = setTimeout(refresh, 250);
  };
  document.querySelector("#status-filter").onchange = refresh;
  await refresh();
  goButtons();
  state.poll = setInterval(() => refresh().catch(() => {}), 4000);
}
async function investigate() {
  document.querySelector("#view").innerHTML =
    head(
      "Investigate a post",
      "Give your agents the original wording and any sources worth checking.",
    ) +
    `<div class="grid2"><section class="panel"><form id="investigate-form"><div class="form-grid"><div class="field"><label for="platform">Platform</label><select name="platform" id="platform">${["manual", "x", "facebook", "instagram", "whatsapp", "partner_feed"].map((v) => `<option>${v}</option>`).join("")}</select></div><div class="field"><label for="author">Author reference (optional)</label><input name="author" id="author" placeholder="e.g. public account handle"></div></div><div class="field"><label for="post">Post text</label><textarea name="text" id="post" rows="7" maxlength="16000" required placeholder="Paste the exact post, including any caption, quotation or correction…"></textarea></div><div class="field"><label for="source">Original post URL (optional)</label><input name="source" id="source" type="url" placeholder="https://…"><small>Used for attribution. This release analyzes the text you submit.</small></div><div class="field"><label for="evidence">Evidence URLs</label><textarea name="evidence" id="evidence" rows="3" placeholder="One public source URL per line (up to six)"></textarea><small>Agents read the source pages, then validate their citations against the retrieved text.</small></div><div class="checks"><label><input type="checkbox" name="external">Allow this submission to be sent to configured hosted model APIs</label><label><input type="checkbox" name="search">Allow claim queries to be sent to the configured search provider</label></div><button type="submit">Start investigation →</button></form></section><div><section class="panel"><div class="eyebrow">How it works</div><h2>Four roles. A traceable decision.</h2>${Object.entries(
      roles,
    )
      .map(
        ([r, [n, d]], i) =>
          `<div class="agent-mini"><span class="agent-num">${i + 1}</span><div><p>${n}</p><small>${d}</small></div></div>`,
      )
      .join(
        "",
      )}</section><section class="panel"><h3>Try a grounded example</h3><p class="muted">Check an intentionally incorrect date against NASA's Apollo 11 record.</p><button id="sample" class="secondary">Load example</button></section><div class="notice">English text pilot. Images and videos are not analyzed yet. Unresolved claims stay unresolved. A manual author reference cannot create a verified account strike.</div></div></div>`;
  document.querySelector("#sample").onclick = () => {
    document.querySelector("#post").value =
      "Apollo 11 first landed humans on the Moon in 1972.";
    document.querySelector("#evidence").value =
      "https://www.nasa.gov/mission/apollo-11/";
  };
  bindForm("#investigate-form", async (f) => {
    const id = crypto.randomUUID();
    const result = await send("/content-events", {
      event_id: id,
      content_id: id,
      platform: f.get("platform"),
      text: f.get("text"),
      author_ref: f.get("author"),
      source_url: f.get("source"),
      evidence_urls: String(f.get("evidence"))
        .split("\n")
        .map((v) => v.trim())
        .filter(Boolean),
      allow_external_processing: f.has("external"),
      allow_web_search: f.has("search"),
    });
    nav("case/" + result.case_id);
  });
}
async function agents() {
  const d = await api("/dashboard");
  if (state.route !== "agents") return;
  document.querySelector("#view").innerHTML =
    head(
      "Your agent team",
      "Choose a model for each role. Add a fallback connection for resilience.",
    ) +
    `<div class="agent-grid">${Object.entries(roles)
      .map(([role, [name, description]], i) => {
        const assigned = d.roles.find((r) => r.role === role) || {};
        return `<section class="agent-card"><span class="agent-num">0${i + 1}</span><h2>${name}</h2><p>${description}</p><form id="role-${role}"><div class="field"><label>Primary connection</label><select name="connection_id" required><option value="">Choose a connection</option>${d.connections.map((c) => `<option value="${c.id}" ${c.id === assigned.connection_id ? "selected" : ""}>${esc(c.name)} · ${esc(c.model)}</option>`).join("")}</select></div><div class="field"><label>Fallback connection</label><select name="fallback_id"><option value="">No fallback</option>${d.connections.map((c) => `<option value="${c.id}" ${c.id === assigned.fallback_id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></div><button type="submit" class="secondary">Save assignment</button></form></section>`;
      })
      .join(
        "",
      )}</div><div class="notice">Different roles can share a model or use different providers. Their agreement does not establish truth; findings must cite retrieved evidence.</div>`;
  Object.keys(roles).forEach((role) =>
    bindForm("#role-" + role, async (f) => {
      await send(
        "/agents/" + role,
        {
          connection_id: f.get("connection_id"),
          fallback_id: f.get("fallback_id") || null,
        },
        "PUT",
      );
      toast("Agent assignment saved");
    }),
  );
}
async function connections() {
  const d = await api("/connections");
  if (state.route !== "connections") return;
  document.querySelector("#view").innerHTML =
    head(
      "Connections",
      "Bring your model APIs and search provider into one workspace.",
    ) +
    `<div class="grid2"><div><section class="panel"><div class="panelhead"><h2>Model connections</h2><span class="tag">${d.connections.length} configured</span></div>${d.connections.length ? d.connections.map((c) => `<div class="source"><div class="panelhead"><div><strong>${esc(c.name)}</strong><br><small>${esc(c.model)} · ${esc(c.kind)}</small></div><button class="secondary small" data-test="${c.id}">Test connection</button></div><small class="break">${esc(c.base_url)} · ${c.local_endpoint ? "Local endpoint" : c.credential_configured ? "Key stored securely" : "No key set"}</small></div>`).join("") : '<p class="muted">No model connected yet. Add an API or a local model server to activate the team.</p>'}</section><section class="panel"><h2>Add a model or agent API</h2><form id="connection-form"><div class="form-grid"><div class="field"><label for="conn-name">Connection name</label><input name="name" id="conn-name" required placeholder="e.g. Research model"></div><div class="field"><label for="conn-kind">API protocol</label><select name="kind" id="conn-kind"><option value="openai_responses">OpenAI Responses</option><option value="openai_chat">OpenAI-compatible Chat</option><option value="anthropic">Anthropic Messages</option><option value="agent_endpoint">Custom agent endpoint</option></select></div></div><div class="field"><label for="base">Base URL</label><input name="base_url" id="base" required type="url" value="https://api.openai.com/v1"><small>Custom agents receive role, instructions, input and response_schema; return {result, usage}.</small></div><div class="field"><label for="model">Model ID</label><input name="model" id="model" required placeholder="Enter a model available to your API account"></div><div class="field"><label for="key">API key</label><input name="api_key" id="key" type="password" autocomplete="new-password" placeholder="Stored encrypted; never returned by the API"></div><div class="checks"><label><input name="local_endpoint" id="local" type="checkbox">This is a local model server (loopback addresses only)</label></div><div class="actions"><button type="submit">Add connection</button><button type="button" class="secondary" id="local-preset">Use local model preset</button></div></form></section></div><div><section class="panel"><h2>Evidence search</h2><p class="muted">Source URLs supplied with a post work without a search key.</p><form id="search-form"><div class="field"><label for="search-provider">Search provider</label><select name="provider" id="search-provider">${[
      ["none", "Supplied URLs only"],
      ["tavily", "Tavily · web search"],
      ["wikipedia", "Wikipedia · background research"],
    ]
      .map(
        ([v, n]) =>
          `<option value="${v}" ${d.search.provider === v ? "selected" : ""}>${n}</option>`,
      )
      .join(
        "",
      )}</select></div><div class="field"><label for="search-key">Tavily API key</label><input name="api_key" id="search-key" type="password" placeholder="${d.search.credential_configured ? "Key already stored; leave blank to keep" : "Required for Tavily"}"></div><button type="submit" class="secondary">Save search settings</button></form></section><div class="notice">A connection test makes a small request to the selected provider. Hosted API usage may be billed by that provider. Local-only submissions cannot be sent to hosted models, including fallbacks.</div></div></div>`;
  document.querySelector("#conn-kind").onchange = (e) => {
    document.querySelector("#base").value =
      e.target.value === "anthropic"
        ? "https://api.anthropic.com/v1"
        : e.target.value === "agent_endpoint"
          ? ""
          : "https://api.openai.com/v1";
  };
  document.querySelector("#local-preset").onclick = () => {
    document.querySelector("#conn-name").value = "Local Qwen · development";
    document.querySelector("#conn-kind").value = "openai_chat";
    document.querySelector("#base").value = "http://127.0.0.1:8087/v1";
    document.querySelector("#model").value = "qwen3-4b-local";
    document.querySelector("#local").checked = true;
  };
  bindForm("#connection-form", async (f) => {
    await send("/connections", {
      name: f.get("name"),
      kind: f.get("kind"),
      base_url: f.get("base_url"),
      model: f.get("model"),
      api_key: f.get("api_key"),
      local_endpoint: f.has("local_endpoint"),
    });
    toast("Connection added. Unassigned agents use this connection.");
    await connections();
  });
  bindForm("#search-form", async (f) => {
    await send(
      "/search",
      { provider: f.get("provider"), api_key: f.get("api_key") },
      "PUT",
    );
    toast("Search settings saved");
  });
  document.querySelectorAll("[data-test]").forEach(
    (button) =>
      (button.onclick = async () => {
        button.disabled = true;
        button.textContent = "Testing…";
        try {
          const result = await send(
            "/connections/" + button.dataset.test + "/test",
            {},
          );
          toast(
            "Connected · " + (result.elapsed_ms / 1000).toFixed(1) + " seconds",
          );
        } catch (e) {
          toast(e.message);
        } finally {
          button.disabled = false;
          button.textContent = "Test connection";
        }
      }),
  );
}
async function integrations() {
  const tokens = await api("/tokens");
  if (state.route !== "integrations") return;
  document.querySelector("#view").innerHTML =
    head(
      "Platform integrations",
      "Feed authorized content into the same verification pipeline.",
    ) +
    `<div class="grid2"><section class="panel"><h2>Integration tokens</h2><p class="muted">Tokens can submit events. They cannot view cases, change policy, or manage model keys.</p><form id="token-form"><div class="field"><label for="token-name">Integration name</label><input id="token-name" name="name" required placeholder="e.g. Platform staging feed"></div><button type="submit">Create token</button></form><div id="new-token"></div><div class="table-wrap"><table><thead><tr><th>Name</th><th>Created</th><th></th></tr></thead><tbody>${tokens.map((t) => `<tr><td>${esc(t.name)}</td><td>${stamp(t.created)}</td><td><button class="secondary small" data-revoke="${t.id}">Revoke</button></td></tr>`).join("")}</tbody></table></div></section><section class="panel"><div class="eyebrow">Partner API</div><h2>One event contract</h2><p>Send a bearer-authenticated request to <code>POST /api/content-events</code>.</p><pre>${esc(JSON.stringify({ event_id: "unique-event-id", platform: "partner_feed", content_id: "post-123", revision: 1, text: "The original post text", author_ref: "verified-platform-id", author_verified: true, evidence_urls: [], allow_external_processing: false, allow_web_search: false }, null, 2))}</pre><p class="muted">Reusing an event ID with the same payload is safe. Edits and deletions require an increasing revision. Set event_type to edited or deleted.</p><a href="/api/openapi.json" target="_blank">Open API specification ↗</a><div class="notice">The intake contract supports X, Facebook, Instagram, WhatsApp and partner feeds. Access to a platform's content still requires its authorization. An X filtered-stream worker and RSS monitor are included. Facebook, Instagram and WhatsApp need a customer-authorized adapter to submit this event contract. Account actions are not connected.</div></section></div>`;
  bindForm("#token-form", async (f) => {
    const r = await send("/tokens", { name: f.get("name") });
    document.querySelector("#new-token").innerHTML =
      `<div class="notice success">Copy this token now. It is only shown once.</div><pre>${esc(r.token)}</pre>`;
  });
  document.querySelectorAll("[data-revoke]").forEach(
    (button) =>
      (button.onclick = async () => {
        await api("/tokens/" + button.dataset.revoke, { method: "DELETE" });
        toast("Integration token revoked");
        integrations();
      }),
  );
}
async function policy() {
  const d = await api("/dashboard");
  if (state.route !== "policy") return;
  document.querySelector("#view").innerHTML =
    head(
      "Review and escalation policy",
      "Make repeat-incident rules explicit and reversible.",
    ) +
    `<div class="grid2"><section class="panel"><h2>Confirmed incidents</h2><form id="policy-form"><div class="field"><label>Incident window (days)</label><input name="window_days" type="number" min="1" max="730" value="${d.policy.window_days}" required></div><div class="form-grid"><div class="field"><label>Admin escalation at</label><input name="admin_threshold" type="number" min="2" max="10" value="${d.policy.admin_threshold}" required></div><div class="field"><label>Senior review at</label><input name="senior_threshold" type="number" min="3" max="20" value="${d.policy.senior_threshold}" required></div></div><button type="submit">Save policy</button></form></section><section class="panel"><h2>Every strike has a record</h2><p>Only a reviewer-confirmed finding with cited evidence, a policy rule, a verified author and a distinct incident key is eligible.</p><p>Duplicates count once. Appeals remove a contested incident from escalation. Overturned decisions stay out of the count.</p><div class="notice">Account disabling and external enforcement are disabled in this release. Escalations appear in this workspace for a platform administrator to review.</div></section></div>`;
  bindForm("#policy-form", async (f) => {
    await send(
      "/policy",
      Object.fromEntries([...f.entries()].map(([k, v]) => [k, Number(v)])),
      "PUT",
    );
    toast("Policy saved");
  });
}
async function audit() {
  const entries = await api("/audit");
  if (state.route !== "audit") return;
  document.querySelector("#view").innerHTML =
    head(
      "Audit trail",
      "A durable history of configuration, investigations and reviewer decisions.",
    ) +
    `<section class="panel table-wrap"><table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Details</th></tr></thead><tbody>${entries.map((e) => `<tr><td>${stamp(e.created)}</td><td>${esc(e.actor)}</td><td>${esc(e.action)}</td><td><code>${esc(e.subject.slice(0, 12))}</code><details><summary>Inspect event</summary><pre>${esc(JSON.stringify(e.details, null, 2))}</pre></details></td></tr>`).join("")}</tbody></table></section>`;
}
async function detail(id, repeat = false) {
  const c = await api("/cases/" + id);
  const view = document.querySelector("#view");
  if (!view) return;
  if (location.hash !== "#case/" + id) return;
  const r = c.result;
  view.innerHTML =
    head(
      "Investigation",
      "Claims, original evidence, and every agent’s contribution.",
      `<a href="/api/cases/${c.id}/export" class="tag">Export case JSON ↓</a>`,
    ) +
    `<section class="detail-head"><div class="detail-meta">${tag(c.status)}<span>${esc(c.platform)}</span><span>${stamp(c.created)}</span><span>Revision ${c.revision}</span>${c.input.source_url ? `<a ${external(c.input.source_url)}>Original post ↗</a>` : ""}</div><div class="detail-post">${esc(c.input.text || "Content deleted")}</div><div class="detail-meta">${c.author_ref ? `<span>Author: ${esc(c.author_ref)}</span><span>${c.author_verified ? "Platform-verified identity" : "Unverified reference"}</span>` : ""}<span>${esc(c.stage)}</span></div>${c.error ? `<div class="notice error">${esc(c.error)}</div><button id="retry" class="secondary">Retry investigation</button>` : ""}</section><div class="grid2"><div><section class="panel"><h2>Claim assessments</h2>${
      r
        ? r.judgments
            .map((j) => {
              const cl = r.claims.find((x) => x.id === j.claim_id);
              return `<div class="claim-block"><div class="claim-line"><strong>${esc(cl?.text || j.claim_id)}</strong>${tag(j.verdict)}</div><p>${esc(j.rationale)}</p>${j.citations.map((cite) => `<div class="citation"><strong>${esc(cite.evidence_id)}</strong> · “${esc(cite.quote)}”</div>`).join("")}<small>${esc(j.citation_check?.replaceAll("_", " ") || "")}</small></div>`;
            })
            .join("") || "<p>No checkable claim was extracted.</p>"
        : `<div class="empty"><div class="empty-icon">◇</div><h3>${c.status === "blocked" ? "Investigation needs attention" : "Your agents are investigating"}</h3><p>${esc(c.stage)}. Results will appear here automatically.</p></div>`
    }</section>${r ? `<section class="panel"><h2>Evidence library</h2>${r.evidence.length ? r.evidence.map((e) => `<div class="source"><div class="claim-line"><a ${external(e.url)}>${esc(e.id)} · ${esc(e.title || e.url)} ↗</a>${tag(e.status)}</div><small>${esc(e.host || "")} · Retrieved ${stamp(e.retrieved_at)}${e.published_at ? " · Published " + esc(e.published_at) : ""}</small>${e.error ? `<div class="notice error">${esc(e.error)}</div>` : `<details><summary>Read captured source text</summary><pre>${esc(e.text)}</pre></details><small>SHA-256: ${esc(e.sha256.slice(0, 18))}… ${e.duplicate_content ? "· Duplicate source content" : ""}</small>`}</div>`).join("") : '<p class="muted">No sources were supplied or retrieved.</p>'}</section><section class="panel"><h2>Limits and unresolved questions</h2>${r.limitations.map((l) => `<p class="muted">• ${esc(l)}</p>`).join("")}</section>` : ""}</div><div><section class="panel"><h2>Agent activity</h2><div class="timeline">${c.runs.length ? c.runs.map((run) => `<div class="run ${esc(run.status)}"><strong>${esc(roles[run.role]?.[0] || run.role)}</strong><p>${tag(run.status)} ${run.elapsed_ms ? (run.elapsed_ms / 1000).toFixed(1) + "s" : ""}</p><small>${esc(run.model || "")}</small>${run.error ? `<p>${esc(run.error)}</p>` : ""}${run.output ? `<details><summary>View structured output</summary><pre>${esc(JSON.stringify(run.output, null, 2))}</pre></details>` : ""}</div>`).join("") : '<p class="muted">Waiting for a worker.</p>'}</div></section>${r ? `<section class="panel"><h2>Reviewer decision</h2>${c.review ? `<div class="notice">${tag(c.review.decision)}<p>${esc(c.review.reason)}</p><small>${esc(c.review.reviewer)} · ${stamp(c.review.updated)}</small></div>` : ""}${["needs_review", "reviewed"].includes(c.status) && !["dismissed", "overturned"].includes(c.review?.decision) ? `<form id="review-form"><div class="field"><label>Decision</label><select name="decision">${(!c.review ? ["dismissed", ...(c.can_confirm ? ["confirmed"] : [])] : c.review.decision === "confirmed" ? ["appealed", "overturned"] : ["overturned", ...(c.can_confirm ? ["confirmed"] : [])]).map((v) => `<option value="${v}">${{ dismissed: "Dismiss / no eligible violation", confirmed: "Confirm eligible policy violation", appealed: "Open appeal", overturned: "Overturn decision" }[v]}</option>`).join("")}</select></div><div class="field"><label>Reason</label><textarea name="reason" minlength="15" required placeholder="Explain your decision with the evidence and context…"></textarea></div>${c.can_confirm ? `<div class="field"><label>Policy rule (for confirmation)</label><input name="policy_rule" value="${esc(c.review?.policy_rule || "")}" placeholder="Applicable platform rule"></div><div class="field"><label>Distinct incident key (for confirmation)</label><input name="incident_key" value="${esc(c.review?.incident_key || "")}" placeholder="Group duplicates under the same key"></div>` : ""}<button type="submit">Record decision</button></form>` : '<p class="muted">This decision or content version is closed.</p>'}${!c.can_confirm ? "<small>This case cannot create a strike: it needs a verified platform author and a cited adverse finding.</small>" : ""}</section>` : ""}${c.account ? `<section class="panel"><h3>Account history</h3><p>${c.account.eligible_incidents} eligible incident(s) ${tag(c.account.escalation)}</p><small>No external account action is issued.</small></section>` : ""}</div></div>`;
  const retry = document.querySelector("#retry");
  if (retry)
    retry.onclick = async () => {
      await send("/cases/" + id + "/retry", {});
      detail(id);
    };
  bindForm("#review-form", async (f) => {
    await send("/cases/" + id + "/decisions", {
      decision: f.get("decision"),
      reason: f.get("reason"),
      policy_rule: f.get("policy_rule") || "",
      incident_key: f.get("incident_key") || "",
    });
    toast("Decision recorded");
    detail(id);
  });
  if (["queued", "processing"].includes(c.status) && !repeat) {
    clearInterval(state.poll);
    state.poll = setInterval(() => {
      if (!document.querySelector("#review-form"))
        detail(id, true).catch(() => {});
    }, 3000);
  } else if (!["queued", "processing"].includes(c.status)) {
    clearInterval(state.poll);
  }
}
function auth(setup) {
  app.innerHTML = `<div class="auth"><section class="auth-story"><div class="brand"><span class="logo">cv</span>Claim Verifier</div><div class="eyebrow">Evidence, before action.</div><h1>Better decisions.<br>Built on evidence.</h1><p>A connected team of AI agents helps your moderation team see what a claim is really supported by.</p></section><section class="auth-form"><div class="inner"><h2>${setup ? "Create your workspace" : "Welcome back"}</h2><p class="muted">${setup ? "Set up the first administrator to connect your agents and start investigating." : "Sign in to your private verification workspace."}</p><form id="auth-form"><div class="field"><label for="username">Username</label><input name="username" id="username" autocomplete="username" minlength="3" required></div><div class="field"><label for="password">Password</label><input name="password" id="password" type="password" minlength="12" autocomplete="${setup ? "new-password" : "current-password"}" required></div><button type="submit">${setup ? "Create workspace" : "Sign in"} →</button></form><p class="muted">Private deployment · Evidence-backed review</p></div></section></div>`;
  bindForm("#auth-form", async (f) => {
    state.user = await send(
      "/auth/" + (setup ? "setup" : "login"),
      Object.fromEntries(f),
    );
    await route();
  });
}
async function route() {
  if (!state.user) return;
  clearInterval(state.poll);
  const value = location.hash.slice(1) || "overview";
  state.route = value.startsWith("case/") ? "queue" : value;
  shell();
  try {
    if (value.startsWith("case/")) await detail(value.split("/")[1]);
    else
      await (
        {
          overview,
          queue,
          investigate,
          agents,
          connections,
          integrations,
          policy,
          audit,
        }[value] || overview
      )();
  } catch (e) {
    document.querySelector("#view").innerHTML =
      `<div class="notice error">${esc(e.message)}</div>`;
  }
}
window.addEventListener("hashchange", route);
async function start() {
  try {
    const status = await api("/auth/status");
    state.user = status.user;
    if (state.user) await route();
    else auth(status.setup_required);
  } catch (e) {
    app.innerHTML = `<div class="boot">${esc(e.message)}</div>`;
  }
}
start();
