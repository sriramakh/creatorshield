import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

// Synthetic sample owned by this project (samples/generate_samples.py).
const SAMPLE = path.resolve(__dirname, "../../samples/sample_promo_en.mp4");
const SHOTS = path.resolve(__dirname, "../../var/e2e-results");

test("upload a video, review timestamped findings, seek, and export the report", async ({ page }) => {
  // 1. Upload
  await page.goto("/analyses/new");
  await expect(page.getByRole("heading", { name: "New analysis" })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles(SAMPLE);
  await expect(page.getByText("sample_promo_en.mp4")).toBeVisible();
  await expect(page.getByText(/27\.0s/)).toBeVisible();
  await page.getByRole("button", { name: /YouTube Shorts/ }).click();
  await page.getByRole("button", { name: "English", exact: true }).click();
  await page.getByLabel("Caption / description").fill("My morning routine with FitFuel");
  await page.getByLabel("Hashtags").fill("#fitness #morningroutine #protein");

  const submit = page.getByRole("button", { name: "Analyse video" });
  await expect(submit).toBeDisabled(); // authorization checkbox not yet ticked
  await page.getByRole("checkbox").check();
  await submit.click();

  // 2. Processing -> completed dashboard
  await page.waitForURL(/\/analyses\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: /^Findings/ })).toBeVisible({ timeout: 200_000 });
  await page.screenshot({ path: `${SHOTS}/review-dashboard.png`, fullPage: true });

  // 3. A disclosure finding with an official policy reference. Titles differ between
  //    rule-only and AI-merged findings, so match on category + citation instead.
  const disclosure = page
    .locator("article", { hasText: "Sponsored-content disclosure" })
    .filter({ has: page.locator('a[href="https://support.google.com/youtube/answer/154235"]') })
    .first();
  await expect(disclosure).toBeVisible();

  // 4. Navigate from a finding to its timestamp (the synthetic music tail starts at 21s)
  const music = page.locator("article", { hasText: "Music & third-party licensing" }).first();
  await music.getByRole("button", { name: /^0:21\.0/ }).first().click();
  // The upload page stays mounted (hidden) under Cache Components, so scope to the review panel.
  const video = page.getByRole("complementary").locator("video");
  await expect
    .poll(async () => video.evaluate((v: HTMLVideoElement) => v.currentTime), { timeout: 10_000 })
    .toBeGreaterThanOrEqual(20.9);

  // 5. Export a readable report
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download report" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^creatorshield-report-.*\.html$/);
  const html = readFileSync(await download.path(), "utf-8");
  expect(html).toContain("Pre-publication compliance report");
  expect(html).toContain("support.google.com/youtube/answer/154235");
  expect(html).toContain("not a probability of removal");

  // 6. Dashboard lists the analysis
  await page.goto("/dashboard");
  await expect(page.getByText("My morning routine with FitFuel").first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/dashboard.png`, fullPage: true });
});

test("policy library lists verified official sources", async ({ page }) => {
  await page.goto("/policies");
  await expect(page.getByRole("heading", { name: "Policy library" })).toBeVisible();
  await expect(page.getByText("YT-DISC-PAID-PROMO")).toBeVisible();
  await expect(page.getByText("IN-ASCI-INFLUENCER")).toBeVisible();
});
