import { expect, test } from "@playwright/test";

test("add and delete a rights-ledger record", async ({ page }) => {
  const name = `E2E Brand ${Date.now()}`;
  await page.goto("/rights");
  await expect(page.getByRole("heading", { name: "Rights ledger" })).toBeVisible();

  await page.getByLabel("Type", { exact: true }).selectOption("brand_agreement");
  await expect(page.getByText(/high-severity disclosure finding/)).toBeVisible();
  await page.getByLabel("Account, brand, label or licensor").fill(name);
  await page.getByLabel("Match terms").fill(`${name}, e2ebrand.example`);
  await page.getByLabel("Instagram", { exact: true }).check();
  await page.getByLabel("Valid until").fill("2030-12-31");
  await page.getByLabel("Reference", { exact: true }).fill("Contract E2E-1");
  await page.getByRole("button", { name: "Add record" }).click();

  const card = page.getByLabel(`Paid brand agreement: ${name}`);
  await expect(card).toBeVisible();
  await expect(card.getByText("e2ebrand.example")).toBeVisible();
  await expect(card.getByText("Instagram", { exact: true })).toBeVisible();
  await expect(card.getByText("Active", { exact: true })).toBeVisible();
  await expect(card.getByText("Contract E2E-1")).toBeVisible();

  // Inline confirmation, no browser dialog.
  await card.getByRole("button", { name: "Delete" }).click();
  await expect(card.getByText("Delete this record?")).toBeVisible();
  await card.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(card).toHaveCount(0);
});
