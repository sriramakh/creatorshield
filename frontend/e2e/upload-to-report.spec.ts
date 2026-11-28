import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { API, ensureOnboarded } from "./helpers";

// Synthetic sample owned by this project (samples/generate_samples.py).
const SAMPLE = path.resolve(__dirname, "../../samples/sample_promo_en.mp4");
const SHOTS = path.resolve(__dirname, "../../var/e2e-results");

let briefId = "";
let briefName = "";

test.beforeAll(async ({ request }) => {
  await ensureOnboarded(request);
  briefName = `E2E upload brief ${Date.now()}`;
  const res = await request.post(`${API}/api/briefs`, {
    data: {
      name: briefName,
      brand: "GlowUp",
      must_say: ["patch test first"],
      must_not_say: [],
      required_hashtags: ["GlowUpPartner"],
      required_mentions: [],
      competitors: [],
      required_disclosure: null,
      notes: "",
    },
  });
  briefId = (await res.json()).id;
});

test.afterAll(async ({ request }) => {
  if (briefId) await request.delete(`${API}/api/briefs/${briefId}`);
});

test("upload with markets and a brief, live caption feedback, verdict banner, findings, export", async ({ page }) => {
  // 1. Upload form
  await page.goto("/analyses/new");
  await expect(page.getByRole("heading", { name: "New review" })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles(SAMPLE);
  await expect(page.getByText("sample_promo_en.mp4")).toBeVisible();
  await expect(page.getByText(/27\.0s/)).toBeVisible();
  await page.getByRole("radio", { name: /Instagram Reels/ }).click();
  await page.getByRole("radio", { name: "English", exact: true }).click();

  // Markets: India is the workspace default here; add the UK.
  const markets = page.getByRole("group", { name: "Audience markets" });
  const india = markets.getByRole("button", { name: /India/ });
  if ((await india.getAttribute("aria-pressed")) !== "true") await india.click();
  await markets.getByRole("button", { name: /United Kingdom/ }).click();
  await expect(markets.getByRole("button", { name: /United Kingdom/ })).toHaveAttribute("aria-pressed", "true");

  // Live caption feedback (advisory) with a suggested caption.
  await page.getByLabel("Caption", { exact: true }).fill("Sponsored by GlowUp. Use code GLOW20 for 20% off");
  await page.getByLabel("Hashtags").fill("#skincare #glowup");
  await expect(page.getByRole("button", { name: "Use suggested caption" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("list", { name: "Disclosure by market" })).toContainText("United Kingdom");

  // Brief
  await page.getByLabel("Brand brief").selectOption(briefId);
  await expect(page.getByText("patch test first")).toBeVisible();

  const submit = page.getByRole("button", { name: "Start review" });
  await expect(submit).toBeDisabled(); // authorisation checkbox not yet ticked
  await page.getByRole("checkbox", { name: /authorised to have it reviewed/ }).check();
  await submit.click();

  // 2. Processing -> completed review with a verdict banner
  await page.waitForURL(/\/analyses\/[0-9a-f-]{36}$/);
  const verdict = page.getByRole("region", { name: "Verdict" });
  await expect(verdict).toBeVisible({ timeout: 200_000 });
  await expect(verdict.getByRole("heading", { level: 2 })).toHaveText(/posting|No issues found/);
  await expect(verdict.getByRole("button", { name: /Brand brief/ })).toBeVisible();
  await expect(page.getByText("IN", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("UK", { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/review-verdict.png`, fullPage: true });

  // 3. A checklist row jumps to its findings; brief findings carry no policy reference.
  await verdict.getByRole("button", { name: /Brand brief/ }).click();
  const briefFinding = page.getByRole("article", { name: /Brand brief/ }).first();
  await expect(briefFinding).toBeVisible();
  await expect(briefFinding.getByText("Policy reference")).toHaveCount(0);
  await expect(page.getByRole("table", { name: "Brand brief requirements" })).toContainText("patch test first");

  // 4. Caption tab: labels per market and the suggested caption.
  await page.getByRole("tab", { name: "Caption" }).click();
  await expect(page.getByRole("table", { name: "Disclosure labels found, by market" })).toContainText("Sponsored");
  await expect(page.getByRole("button", { name: "Copy suggested caption" })).toBeVisible();

  // 5. Navigate from a finding to its timestamp (the synthetic music tail starts at 21s)
  await page.getByRole("tab", { name: /^Findings/ }).click();
  const music = page.locator("article", { hasText: "Music & third-party licensing" }).first();
  await music.getByRole("button", { name: /^0:21\.0/ }).first().click();
  // The upload page stays mounted (hidden) under Cache Components, so scope to the review panel.
  const video = page.getByRole("complementary").locator("video");
  await expect.poll(async () => video.evaluate((v: HTMLVideoElement) => v.currentTime), { timeout: 10_000 }).toBeGreaterThanOrEqual(20.9);

  // 6. Export a readable report
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download report" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^creatorshield-report-.*\.html$/);
  const html = readFileSync(await download.path(), "utf-8");
  expect(html).toContain("not a probability of removal");

  // 7. The Reviews list shows it with its verdict and markets
  await page.goto("/reviews");
  const row = page.getByRole("row", { name: /Sponsored by GlowUp\. Use code GLOW20/ }).first();
  await expect(row).toBeVisible();
  await expect(row).toContainText(/Fix first|Review|No issues found/);
  await expect(row).toContainText("UK");
  await page.screenshot({ path: `${SHOTS}/reviews.png`, fullPage: true });
});

test("policy library groups regulator packs under their market", async ({ page }) => {
  await page.goto("/policies");
  await expect(page.getByRole("heading", { name: "Policy library" })).toBeVisible();
  await expect(page.getByText("YT-DISC-PAID-PROMO")).toBeVisible();
  await expect(page.getByRole("heading", { name: /United States — FTC/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /India — ASCI/ })).toBeVisible();
});
