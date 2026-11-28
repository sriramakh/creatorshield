import { expect, test } from "@playwright/test";
import { ensureOnboarded } from "./helpers";

test.beforeAll(async ({ request }) => ensureOnboarded(request));

test("caption check: finding and suggested caption, apply clears it", async ({ page }) => {
  await page.goto("/check");
  await expect(page.getByRole("heading", { name: "Caption check" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Type or paste a caption" })).toBeVisible();

  const caption = page.getByLabel("Caption", { exact: true });
  await caption.fill("Loving my new GlowUp serum. Use code GLOW20 for 20% off");

  // Live result: verdict, the disclosure finding and a suggested caption.
  const verdict = page.getByRole("region", { name: "Verdict" });
  await expect(verdict.getByRole("heading", { name: "Fix before posting" })).toBeVisible();
  await expect(page.getByRole("article", { name: /Promotional language without a visible sponsorship disclosure/ })).toBeVisible();
  await expect(page.getByText("Suggested caption", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Replace my caption" }).click();
  await expect(caption).toHaveValue(/^Ad: /);
  await expect(page.getByText("Caption replaced")).toBeVisible();

  // The fixed caption no longer has an open disclosure finding.
  await expect(verdict.getByRole("heading", { name: "Fix before posting" })).toHaveCount(0);
  await expect(page.getByText("No issues found by these checks in the caption and hashtags.")).toBeVisible();
});

test("caption check hands its fields to the review form", async ({ page }) => {
  await page.goto("/check");
  await page.getByLabel("Caption", { exact: true }).fill("Morning stretch routine #ad");
  await page.getByRole("button", { name: "Start a full review with this caption" }).click();
  await expect(page).toHaveURL(/\/analyses\/new$/);
  // /check stays mounted (hidden) after navigation, so match the visible field only.
  await expect(page.getByLabel("Caption", { exact: true }).filter({ visible: true })).toHaveValue("Morning stretch routine #ad");
});
