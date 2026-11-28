import { expect, test } from "@playwright/test";
import { ensureOnboarded } from "./helpers";

test.beforeAll(async ({ request }) => ensureOnboarded(request));

test("add and delete a rights-ledger record", async ({ page }) => {
  const name = `E2E Brand ${Date.now()}`;
  await page.goto("/rights");
  await expect(page.getByRole("heading", { name: "Rights ledger" })).toBeVisible();

  // The form opens in a drawer.
  await page.getByRole("button", { name: "Add record" }).first().click();
  const drawer = page.getByRole("dialog", { name: "Add a record" });
  await drawer.getByLabel("Type", { exact: true }).selectOption("brand_agreement");
  await expect(page.getByText(/high-severity disclosure finding/)).toBeVisible();
  await drawer.getByLabel("Account, brand, label or licensor").fill(name);
  await drawer.getByLabel("Match terms").fill(`${name}, e2ebrand.example`);
  await drawer.getByLabel("Instagram", { exact: true }).check();
  await drawer.getByLabel("Valid until").fill("2030-12-31");
  await drawer.getByLabel("Reference", { exact: true }).fill("Contract E2E-1");
  await drawer.getByRole("button", { name: "Save record" }).click();
  await expect(drawer).toHaveCount(0);

  const card = page.getByLabel(`Paid brand agreement: ${name}`);
  await expect(card).toBeVisible();
  await expect(card.getByText("e2ebrand.example")).toBeVisible();
  await expect(card.getByText("Instagram", { exact: true })).toBeVisible();
  await expect(card.getByText("Active", { exact: true })).toBeVisible();
  await expect(card.getByText("Contract E2E-1")).toBeVisible();

  // Destructive actions confirm in a dialog (not a browser prompt).
  await card.getByRole("button", { name: `Delete record for ${name}` }).click();
  const confirm = page.getByRole("dialog", { name: /Delete the record/ });
  await expect(confirm).toBeVisible();
  await confirm.getByRole("button", { name: "Delete record" }).click();
  await expect(card).toHaveCount(0);
});
