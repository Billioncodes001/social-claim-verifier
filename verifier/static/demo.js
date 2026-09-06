"use strict";
const platformNames = {
  x: "X / Twitter",
  facebook: "Facebook",
  instagram: "Instagram",
  manual: "Pasted post",
};
const consentFields = (external = false, search = false) =>
  `<div class="checks"><label><input type="checkbox" name="external" ${external ? "checked" : ""}>Allow configured hosted AI to process this content</label><label><input type="checkbox" name="search" ${search ? "checked" : ""}>Allow evidence searches through the configured search provider</label></div>`;
const evidenceLines = (f) =>
  String(f.get("evidence") || "")
    .split("\n")
    .map((v) => v.trim())
    .filter(Boolean);
async function clicked(button, action) {
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "Working…";
  try {
    await action();
  } catch (e) {
    toast(e.message);
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}
async function demo() {
  const d = await api("/demo");
  if (state.route !== "demo") return;
  document.querySelector("#view").innerHTML =
    head(
      "Demo lab",
      "Try the complete evidence workflow with a post or an account you authorize.",
      `<span class="tag">${d.used_today} / ${d.daily_limit} checks today · UTC</span>`,
    ) +
    `<section class="demo-banner"><div><div class="eyebrow">A post. Four agents. The evidence.</div><h2>See what holds up.</h2><p>Paste a claim, add a source, and follow the investigation from the original words to a cited assessment.</p></div><div class="demo-steps"><span>01 · Submit</span><span>02 · Verify</span><span>03 · Review</span></div></section>
  <div class="grid2"><section class="panel"><div class="panelhead"><h2>Check a post</h2><button class="secondary small" id="demo-sample">Load example</button></div><form id="demo-form"><div class="field"><label>Platform</label><select name="platform">${Object.entries(
    platformNames,
  )
    .map(([id, name]) => `<option value="${id}">${name}</option>`)
    .join(
      "",
    )}</select></div><div class="field"><label>Post text or caption</label><textarea name="text" rows="6" maxlength="16000" required placeholder="Paste the exact wording, including quotations and context…"></textarea></div><div class="field"><label>Original post URL (optional)</label><input type="url" name="source_url" placeholder="https://…"><small>Attribution only. Paste the text above or retrieve a post from a connected account below.</small></div><div class="field"><label>Evidence URLs (optional)</label><textarea name="evidence" rows="2" placeholder="One public source URL per line, up to six"></textarea><small>Supply original sources, or enable configured search. Without evidence, a claim may remain unresolved.</small></div>${consentFields()}<button type="submit">Fact-check this post →</button></form></section>
  <div><section class="panel"><div class="eyebrow">Your accounts, with permission</div><h2>Connect a social account</h2>${d.platforms.map((p) => `<div class="social-choice"><div class="panelhead"><strong>${platformNames[p.provider]}</strong>${tag(!p.enabled ? "disabled" : p.configured ? "app configured" : "needs app setup")}</div><p class="muted">${esc(p.note)}</p>${p.configured && p.enabled ? `<button class="secondary small" data-connect="${p.provider}">Connect ${platformNames[p.provider]}</button>` : state.user.role === "admin" ? `<a href="#${p.enabled ? "socialapps" : "deployment"}">${p.enabled ? "Configure customer app" : "Enable platform"} →</a>` : "<small>Ask your workspace administrator to configure this platform.</small>"}</div>`).join("")}<small>Authorization requests read access. The app never asks for your social password.</small></section><div class="notice">Demo checks cannot create account strikes. Your account tokens and cached posts are private to your workspace login; administrators can review demo investigations. Text and captions only—images, audio and video are not analyzed.</div>${d.connection_notice ? `<div class="notice error">${esc(d.connection_notice)}</div>` : ""}</div></div>
  <section class="panel"><div class="panelhead"><div><h2>Connected accounts</h2><p class="muted">Fetch up to 10 recent posts, choose one, or opt into periodic checks.</p></div><button id="demo-refresh" class="secondary small">Refresh status</button></div>${d.accounts.length ? d.accounts.map((a) => `<article class="connected-account"><div class="panelhead"><div><strong>${esc(a.display_name)}</strong><div class="muted">${platformNames[a.provider]} · Last fetched ${stamp(a.last_sync)}</div></div>${tag(a.status)}</div>${a.error ? `<div class="notice error">${esc(a.error)}</div>` : ""}<form id="fetch-${a.id}"><div class="field"><label>Post URL (optional; leave blank for recent posts)</label><input type="url" name="source_url" placeholder="https://…"></div><button type="submit" class="secondary">Fetch posts</button></form><div id="posts-${a.id}"></div><details class="monitor-settings"><summary>${a.monitor.enabled ? "Monitoring is on" : "Automatic checks are off"} · Configure</summary><form id="monitor-${a.id}"><div class="checks"><label><input type="checkbox" name="enabled" ${a.monitor.enabled ? "checked" : ""}>Check this account’s latest posts automatically while the server is running</label></div><div class="form-grid"><div class="field"><label>Interval (minutes)</label><input name="interval" type="number" min="5" max="1440" value="${a.monitor.interval_minutes}" required></div><div class="field"><label>Latest posts per check</label><input name="limit" type="number" min="1" max="5" value="${a.monitor.batch_limit}" required></div></div>${consentFields(a.monitor.allow_external_processing, a.monitor.allow_web_search)}<small>Uses the daily demo allowance. Unchanged posts are skipped. This samples recent posts; it is not an archive or a platform-wide feed.</small><div class="actions"><button type="submit">Save monitoring</button></div></form></details><div class="account-footer"><button class="secondary small" data-disconnect="${a.id}">Disconnect account</button><small>Removes local tokens and cached posts. Existing checks can be deleted below.</small></div></article>`).join("") : '<div class="empty"><h3>No account connected yet</h3><p>The post demo above works without social app credentials.</p></div>'}</section>
  <section class="panel"><div class="panelhead"><h2>Your recent demo checks</h2><small>Connected post cache expires after 24 hours.</small></div>${d.cases.length ? d.cases.map((c) => `<div class="demo-case">${rows([c])}${c.status !== "deleted" ? `<button class="secondary small" data-delete-demo="${c.id}" aria-label="Delete demo check">Delete</button>` : ""}</div>`).join("") : '<p class="muted">Your submitted checks will appear here.</p>'}</section>`;
  document.querySelector("#demo-form select").value = "manual";
  document.querySelector("#demo-sample").onclick = () => {
    const form = document.querySelector("#demo-form");
    form.elements.platform.value = "manual";
    form.elements.text.value =
      "Apollo 11 first landed humans on the Moon in 1972.";
    form.elements.evidence.value = "https://www.nasa.gov/mission/apollo-11/";
  };
  bindForm("#demo-form", async (f) => {
    const r = await send("/demo/investigate", {
      platform: f.get("platform"),
      text: f.get("text"),
      source_url: f.get("source_url"),
      evidence_urls: evidenceLines(f),
      allow_external_processing: f.has("external"),
      allow_web_search: f.has("search"),
    });
    nav("case/" + r.case_id);
  });
  document.querySelector("#demo-refresh").onclick = () =>
    demo().catch((e) => toast(e.message));
  document.querySelectorAll("[data-connect]").forEach(
    (b) =>
      (b.onclick = () =>
        clicked(b, async () => {
          const result = await send("/social/connect/" + b.dataset.connect, {});
          location.assign(result.authorization_url);
        })),
  );
  for (const a of d.accounts) {
    bindForm("#fetch-" + a.id, async (f) => {
      const r = await send("/social/accounts/" + a.id + "/posts", {
        source_url: f.get("source_url"),
      });
      const target = document.querySelector("#posts-" + a.id);
      target.innerHTML = r.posts.length
        ? r.posts
            .map(
              (p) =>
                `<section class="post-candidate"><div class="panelhead"><a ${external(p.source_url)}>Original post ↗</a><small>${stamp(p.posted_at)}</small></div><p>${esc(p.text)}</p><form id="check-${p.id}"><div class="field"><label>Evidence URLs (optional)</label><textarea name="evidence" rows="2" placeholder="Original sources, one per line"></textarea></div>${consentFields()}<button type="submit" class="secondary small">Check this post</button></form></section>`,
            )
            .join("")
        : '<p class="muted">No text posts were returned. Try pasting a caption above.</p>';
      for (const p of r.posts)
        bindForm("#check-" + p.id, async (f) => {
          const result = await send("/demo/investigate", {
            post_id: p.id,
            evidence_urls: evidenceLines(f),
            allow_external_processing: f.has("external"),
            allow_web_search: f.has("search"),
          });
          nav("case/" + result.case_id);
        });
    });
    bindForm("#monitor-" + a.id, async (f) => {
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
      toast("Monitoring settings saved");
      await demo();
    });
  }
  document.querySelectorAll("[data-disconnect]").forEach(
    (b) =>
      (b.onclick = () =>
        clicked(b, async () => {
          const result = await api("/social/accounts/" + b.dataset.disconnect, {
            method: "DELETE",
          });
          toast(result.note);
          await demo();
        })),
  );
  document.querySelectorAll("[data-delete-demo]").forEach(
    (b) =>
      (b.onclick = () =>
        clicked(b, async () => {
          await api("/demo/cases/" + b.dataset.deleteDemo, {
            method: "DELETE",
          });
          toast("Demo content and agent outputs deleted");
          await demo();
        })),
  );
  const notice = new URLSearchParams(location.hash.split("?")[1] || "").get(
    "notice",
  );
  if (notice) {
    toast(
      notice === "connected"
        ? "Account connected. Fetch recent posts to begin."
        : "Account could not connect. Review the connection message and app settings.",
    );
    history.replaceState(null, "", "#demo");
  }
}

async function socialapps() {
  const apps = await api("/social/apps");
  if (state.route !== "socialapps") return;
  document.querySelector("#view").innerHTML =
    head(
      "Platform apps",
      "Use your organization’s developer apps to authorize read-only account access.",
    ) +
    `<div class="notice">Register each callback exactly as shown in your developer console. App configuration enables login; platform permissions and a successful authorization determine what posts are available.</div><div class="platform-app-grid">${apps.map((p) => `<section class="panel"><div class="panelhead"><h2>${platformNames[p.provider]}</h2>${tag(p.configured ? "configured" : "setup required")}</div><p class="muted">${esc(p.note)}</p><form id="social-app-${p.provider}"><div class="field"><label>Client / app ID</label><input name="client_id" value="${esc(p.client_id)}" required maxlength="300" autocomplete="off"></div><div class="field"><label>Client / app secret ${p.provider === "x" ? "(confidential apps)" : ""}</label><input name="client_secret" type="password" autocomplete="new-password" placeholder="${p.credential_configured ? "Stored encrypted; leave blank to keep" : "Enter the secret from your developer app"}"></div>${p.provider !== "x" ? `<div class="field"><label>Graph API version</label><input name="graph_version" value="${esc(p.graph_version)}" pattern="v[0-9]{1,3}\\.0" placeholder="Version enabled in your Meta app" required><small>Use the supported version selected in your developer console.</small></div>` : ""}<div class="field"><label>OAuth callback URL</label><input name="callback" value="${esc(p.callback_url)}" readonly></div><small class="break">Read permissions: ${esc(p.scopes)}</small><div class="actions"><button type="submit">Save app configuration</button></div></form><small>Changing credentials requires existing accounts to reconnect.</small></section>`).join("")}</div><div class="actions"><button data-go="demo" class="secondary">Open demo lab →</button></div>`;
  for (const p of apps)
    bindForm("#social-app-" + p.provider, async (f) => {
      await send(
        "/social/apps/" + p.provider,
        {
          client_id: f.get("client_id"),
          client_secret: f.get("client_secret"),
          graph_version: f.get("graph_version") || "",
        },
        "PUT",
      );
      toast("App configuration saved");
      await socialapps();
    });
  goButtons();
}

async function deployment() {
  const [config, d, dash] = await Promise.all([
    api("/workspace"),
    api("/deployment"),
    api("/dashboard"),
  ]);
  if (state.route !== "deployment") return;
  const w = config.workspace;
  document.querySelector("#view").innerHTML =
    head(
      "Workspace setup",
      "Brand your workspace, choose platform rules, and check the server configuration.",
    ) +
    `<div class="grid2"><section class="panel"><h2>Your organization</h2><form id="workspace-form"><div class="field"><label>Product name</label><input name="name" value="${esc(w.name)}" maxlength="70" required></div><div class="field"><label>Organization / workspace name</label><input name="organization" value="${esc(w.organization)}" maxlength="100" required></div><div class="field"><label>Daily demo checks per user</label><input name="demo_daily_limit" type="number" min="1" max="200" value="${w.demo_daily_limit}" required></div><button type="submit">Save workspace</button></form></section><section class="panel"><div class="panelhead"><h2>Server readiness</h2>${tag(d.ready ? "configured" : "setup needed")}</div>${d.checks.map((c) => `<div class="readiness-row"><span class="readiness-icon ${c.ok ? "ok" : ""}">${c.ok ? "✓" : "○"}</span><span>${esc(c.label)}${c.required ? "" : " · recommended"}</span></div>`).join("")}<p class="muted break">${esc(d.public_url)}<br>${d.worker_count} workers · ${d.queue_limit} queued or active cases</p><small>${esc(d.deployment_model)}. ${esc(d.assessment)}</small><div class="actions"><button class="secondary small" data-go="connections">Configure AI & search</button></div></section></div><section class="panel"><div class="panelhead"><div><h2>Platform profiles</h2><p class="muted">Control intake, hosted processing, evidence search and escalation independently.</p></div><a href="#policy">Workspace default policy →</a></div>${Object.entries(
      config.platforms,
    )
      .map(([key, p]) => {
        const policy = p.policy || dash.policy;
        return `<details class="platform-profile"><summary>${esc(p.display_name)} <span class="muted">· ${p.enabled ? "enabled" : "disabled"} · ${p.policy ? "custom policy" : "workspace policy"}</span></summary><form id="profile-${key}"><div class="field"><label>Display name</label><input name="display_name" value="${esc(p.display_name)}" maxlength="70" required></div><div class="checks"><label><input type="checkbox" name="enabled" ${p.enabled ? "checked" : ""}>Accept content from this platform</label><label><input type="checkbox" name="allow_hosted" ${p.allow_hosted ? "checked" : ""}>Permit hosted AI when the submission also allows it</label><label><input type="checkbox" name="allow_search" ${p.allow_search ? "checked" : ""}>Permit external evidence search when the submission also allows it</label><label><input type="checkbox" name="custom_policy" ${p.policy ? "checked" : ""}>Use these platform-specific escalation thresholds</label></div><div class="form-grid"><div class="field"><label>Incident window (days)</label><input name="window_days" type="number" min="1" max="730" value="${policy.window_days}" required></div><div class="field"><label>Admin review threshold</label><input name="admin_threshold" type="number" min="2" max="10" value="${policy.admin_threshold}" required></div><div class="field"><label>Senior review threshold</label><input name="senior_threshold" type="number" min="3" max="20" value="${policy.senior_threshold}" required></div></div><button type="submit" class="secondary">Save ${esc(p.display_name)}</button></form></details>`;
      })
      .join(
        "",
      )}</section><div class="notice">Only eligible, human-confirmed incidents enter escalation. Demo checks never create strikes. External account actions are not enabled.</div>`;
  bindForm("#workspace-form", async (f) => {
    await send(
      "/workspace",
      {
        name: f.get("name"),
        organization: f.get("organization"),
        demo_daily_limit: Number(f.get("demo_daily_limit")),
      },
      "PUT",
    );
    toast("Workspace updated");
    await route();
  });
  for (const key of Object.keys(config.platforms))
    bindForm("#profile-" + key, async (f) => {
      await send(
        "/platforms/" + key,
        {
          display_name: f.get("display_name"),
          enabled: f.has("enabled"),
          allow_hosted: f.has("allow_hosted"),
          allow_search: f.has("allow_search"),
          policy: f.has("custom_policy")
            ? {
                window_days: Number(f.get("window_days")),
                admin_threshold: Number(f.get("admin_threshold")),
                senior_threshold: Number(f.get("senior_threshold")),
              }
            : null,
        },
        "PUT",
      );
      toast("Platform profile saved");
      await deployment();
    });
  goButtons();
}
