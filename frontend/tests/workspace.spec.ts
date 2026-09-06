import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function login(page: Page, user = "owner") {
  await page.goto("/#demo");
  await page.getByLabel("Username", { exact: true }).fill(user);
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser-fixture-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Demo lab", exact: true }),
  ).toBeVisible();
}
async function route(page: Page, id: string, heading: string) {
  await page.goto("/#" + id);
  await expect(
    page.getByRole("heading", { name: heading, exact: true }),
  ).toBeVisible();
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
}

test("all workspace routes render without runtime errors or horizontal overflow", async ({
  page,
}) => {
  const failures: string[] = [];
  page.on("pageerror", (e) => failures.push(e.message));
  await login(page);
  for (const [id, title] of [
    ["overview", "The bigger picture."],
    ["demo", "Demo lab"],
    ["queue", "Review queue"],
    ["investigate", "Open an investigation"],
    ["agents", "An expert in every role."],
    ["deployment", "Make this workspace yours."],
    ["socialapps", "Your channels. Your credentials."],
    ["connections", "Connected intelligence."],
    ["integrations", "Built to connect."],
    ["policy", "A standard your team can trust."],
    ["audit", "A record of every decision."],
  ]) {
    await route(page, id, title);
    await noOverflow(page);
  }
  expect(failures).toEqual([]);
});

test("demo example submits actual intake and opens its investigation", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("button", { name: "Load the example" }).click();
  await expect(page.getByLabel("Post text or caption")).toHaveValue(
    /Apollo 11/,
  );
  await page
    .getByLabel("Post text or caption")
    .fill("Browser workflow: an original claim for investigation.");
  await page.getByLabel("Evidence URLs (optional)").fill("");
  const request = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/demo/investigate") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Fact-check this post" }).click();
  const response = await request;
  expect(response.status()).toBe(202);
  await expect(page).toHaveURL(/#case\//);
  await expect(
    page.getByText("Browser workflow: an original claim for investigation.", {
      exact: true,
    }),
  ).toBeVisible();
  expect(
    (
      await (
        await page.request.get("/api/cases/" + (await response.json()).case_id)
      ).json()
    ).is_demo,
  ).toBe(1);
});

test("connected account fetch, consent controls and monitoring settings persist", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("tab", { name: /Connected accounts/ }).click();
  await page.getByRole("button", { name: "Fetch posts", exact: true }).click();
  await expect(
    page.getByText("Browser fixture: a newly discovered claim for review.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByText("Automatic checks", { exact: true }).click();
  await page
    .getByLabel("Check this account’s latest posts while the server is running")
    .check();
  await page.getByLabel("Interval (minutes)").fill("10");
  await page.getByRole("button", { name: "Save monitoring" }).click();
  await expect(page.locator(".toast")).toContainText(
    "Monitoring settings saved",
  );
  const data = await (await page.request.get("/api/demo")).json();
  expect(data.accounts[0].monitor.enabled).toBe(true);
  expect(data.accounts[0].monitor.interval_minutes).toBe(10);
  await page
    .getByLabel("Check this account’s latest posts while the server is running")
    .uncheck();
  await page.getByRole("button", { name: "Save monitoring" }).click();
});

test("branding, platform settings, model assignments and Meta app forms save", async ({
  page,
}) => {
  await login(page);
  await route(page, "deployment", "Make this workspace yours.");
  await page
    .getByLabel("Organization / workspace name")
    .fill("Browser validation team");
  await page
    .getByRole("button", { name: "Save workspace", exact: true })
    .click();
  await expect(page.locator(".workspace-switch")).toContainText(
    "Browser validation team",
  );
  await page
    .getByLabel("Organization / workspace name")
    .fill("Moderation workspace");
  await page
    .getByRole("button", { name: "Save workspace", exact: true })
    .click();
  await page
    .locator(".platform-profile")
    .filter({ hasText: "WhatsApp" })
    .locator("summary")
    .click();
  await page
    .getByLabel("Accept content from this platform")
    .filter({ visible: true })
    .uncheck();
  await page
    .getByRole("button", { name: "Save WhatsApp", exact: true })
    .click();
  expect(
    (await (await page.request.get("/api/workspace")).json()).platforms.whatsapp
      .enabled,
  ).toBe(false);
  await route(page, "connections", "Connected intelligence.");
  await page.getByRole("button", { name: "Use local preset" }).click();
  await page
    .getByRole("button", { name: "Add connection", exact: true })
    .click();
  await expect(page.locator(".toast")).toContainText("Connection added");
  await route(page, "agents", "An expert in every role.");
  await page.getByRole("button", { name: "Save assignment" }).first().click();
  await expect(page.locator(".toast")).toContainText("Agent assignment saved");
  await route(page, "socialapps", "Your channels. Your credentials.");
  const facebook = page
    .locator(".social-app-card")
    .filter({
      has: page.getByRole("heading", { name: "Facebook", exact: true }),
    });
  await facebook.getByLabel("Client / app ID").fill("fixture-facebook-app");
  await facebook
    .getByLabel("App secret", { exact: true })
    .fill("fixture-facebook-secret");
  await facebook.getByLabel("Graph API version").fill("v23.0");
  await facebook
    .getByRole("button", { name: "Save app configuration" })
    .click();
  await expect(page.locator(".toast")).toContainText(
    "Platform app configuration saved",
  );
  await expect(facebook.getByLabel("App secret", { exact: true })).toHaveValue(
    "",
  );
});

test("evidence inspection and human review work through the redesigned report", async ({
  page,
}) => {
  await login(page);
  const data = await (await page.request.get("/api/demo")).json();
  const sample = data.cases.find(
    (c: { text: string; status: string }) =>
      c.text.startsWith("Apollo 11") && c.status === "needs_review",
  );
  expect(sample).toBeTruthy();
  await route(page, "case/" + sample.id, "The evidence, in context.");
  await expect(page.getByText("Contradicted", { exact: true })).toBeVisible();
  await page.getByText("Read captured source", { exact: true }).click();
  await expect(page.locator(".source-text")).toContainText("July 20, 1969");
  await page
    .getByLabel("Reason", { exact: true })
    .fill(
      "This is a browser fixture check; no eligible policy violation is recorded.",
    );
  await page.getByRole("button", { name: "Record decision" }).click();
  await expect(page.locator(".toast")).toContainText(
    "Reviewer decision recorded",
  );
  expect(
    (await (await page.request.get("/api/cases/" + sample.id)).json()).review
      .decision,
  ).toBe("dismissed");
});

test("mobile navigation traps focus, dismisses with Escape and respects reduced motion", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await login(page);
  await expect(
    page.getByRole("link", { name: "Review queue", exact: true }),
  ).not.toBeVisible();
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Workspace navigation" }),
  ).toBeVisible();
  for (let i = 0; i < 20; i++) await page.keyboard.press("Tab");
  expect(
    await page.evaluate(() =>
      document
        .getElementById("workspace-navigation")
        ?.contains(document.activeElement),
    ),
  ).toBe(true);
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Open navigation", exact: true }),
  ).toBeFocused();
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await page.getByRole("link", { name: "Review queue", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Review queue", exact: true }),
  ).toBeVisible();
  await noOverflow(page);
  await route(page, "demo", "Demo lab");
  expect(
    await page.evaluate(
      () => getComputedStyle(document.documentElement).scrollBehavior,
    ),
  ).toBe("auto");
});

test("layouts and accessibility at desktop, tablet and phone widths", async ({
  page,
}) => {
  await login(page);
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/#demo");
    await expect(
      page.getByRole("heading", { name: "Demo lab", exact: true }),
    ).toBeVisible();
    await noOverflow(page);
    await page.screenshot({
      path: "artifacts/ui-demo-" + width + ".png",
      fullPage: true,
    });
    if (width === 1440) {
      const audit = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      expect(
        audit.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => n.failureSummary),
        })),
      ).toEqual([]);
    }
  }
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    results.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
});

test("reviewer cannot open administration and sign out clears the workspace", async ({
  page,
}) => {
  await login(page, "reviewer");
  await page.goto("/#socialapps");
  await expect(page.getByRole("alert")).toContainText(
    "Administrator access is required",
  );
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Demo lab TRY IT" }),
  ).not.toBeVisible();
});
