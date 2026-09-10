import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";

for (const width of [1440, 390])
  test(`local source warnings and human-review export at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    await page.getByLabel("Username", { exact: true }).fill("owner");
    await page
      .getByLabel("Password", { exact: true })
      .fill("browser-fixture-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("button", { name: /Sign out/ })).toBeVisible();
    const cases = await (await page.request.get("/api/cases")).json();
    const current = cases.find(
      (c: { text: string; status: string }) =>
        c.text === "Synthetic freshness review example." &&
        c.status === "needs_review",
    );
    await page.goto(`/#case/${current.id}`);
    await expect(
      page.getByRole("heading", { name: "Evidence freshness & revisions" }),
    ).toBeVisible();
    await expect(
      page.getByText(/Capture is at least 30 days old/),
    ).toBeVisible();
    await expect(
      page.getByText(/Different captured text exists/),
    ).toBeVisible();
    await expect(page.getByText("Unresolved", { exact: true })).toBeVisible();
    const download = page.waitForEvent("download");
    await page.getByRole("link", { name: "Human-review packet" }).click();
    const packet = JSON.parse(
      await readFile((await (await download).path())!, "utf8"),
    );
    expect(packet.payload.case.result.judgments[0].verdict).toBe("unresolved");
    expect(
      packet.payload.evidence_review.sources[0].source_changes[0].revision,
    ).toBe(1);
    expect(packet.integrity.sha256).toMatch(/^[0-9a-f]{64}$/);
    await page.screenshot({
      path: `docs/freshness-${width}.png`,
      fullPage: true,
      animations: "disabled",
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.getByRole("link", { name: "content revision 1, E1" }).click();
    await expect(
      page.getByText(/This content revision has been superseded/),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByText(/This content revision has been superseded/),
    ).toBeVisible();
  });
