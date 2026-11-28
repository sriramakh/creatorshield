import { expect, test } from "@playwright/test";
import { ensureOnboarded } from "./helpers";

test.beforeAll(async ({ request }) => ensureOnboarded(request));

test("brand brief: create, edit and delete", async ({ page }) => {
  const name = `E2E brief ${Date.now()}`;
  await page.goto("/briefs?new=1");
  const drawer = page.getByRole("dialog", { name: "New brief" });
  await expect(drawer).toBeVisible();

  await drawer.getByLabel("Name").fill(name);
  await drawer.getByLabel("Brand", { exact: true }).fill("GlowUp");
  const mustSay = drawer.getByLabel("Must say", { exact: true });
  await mustSay.fill("patch test first");
  await mustSay.press("Enter");
  await mustSay.fill("dermatologist tested,");
  await expect(drawer.getByRole("button", { name: "Remove dermatologist tested" })).toBeVisible();
  // Backspace on an empty input removes the last entry.
  await mustSay.press("Backspace");
  await expect(drawer.getByRole("button", { name: "Remove dermatologist tested" })).toHaveCount(0);
  const tags = drawer.getByLabel("Required hashtags");
  await tags.fill("#GlowUpPartner");
  await tags.press("Enter");
  await expect(drawer.getByRole("button", { name: "Remove #GlowUpPartner" })).toBeVisible();
  await drawer.getByRole("button", { name: "Save brief" }).click();

  await expect(page.getByText(`Saved “${name}”`)).toBeVisible();
  const row = page.getByRole("row", { name: new RegExp(name) });
  await expect(row).toContainText("1 must say");
  await expect(row).toContainText("1 hashtag");

  // Edit
  await row.getByRole("button", { name: `Edit ${name}` }).click();
  const edit = page.getByRole("dialog", { name: "Edit brief" });
  await edit.getByLabel("Competitors").fill("Lumina");
  await edit.getByLabel("Competitors").press("Enter");
  await edit.getByRole("button", { name: "Save brief" }).click();
  await expect(page.getByText(`Updated “${name}”`)).toBeVisible();
  await expect(page.getByRole("row", { name: new RegExp(name) })).toContainText("1 competitor");

  // Delete (confirms first)
  await page.getByRole("row", { name: new RegExp(name) }).getByRole("button", { name: `Delete ${name}` }).click();
  const confirm = page.getByRole("dialog", { name: /Delete “/ });
  await confirm.getByRole("button", { name: "Delete brief" }).click();
  await expect(page.getByRole("row", { name: new RegExp(name) })).toHaveCount(0);
});
