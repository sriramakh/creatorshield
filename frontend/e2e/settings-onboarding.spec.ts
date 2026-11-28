import { expect, test } from "@playwright/test";
import { API } from "./helpers";

let original: Record<string, unknown> = {};

test.beforeAll(async ({ request }) => {
  original = await (await request.get(`${API}/api/settings`)).json();
});

test.afterAll(async ({ request }) => {
  // Put the workspace back the way the run found it (and leave it onboarded).
  const { mode, display_name, default_platform, default_markets, default_language } = original as Record<string, unknown>;
  await request.put(`${API}/api/settings`, {
    data: { mode, display_name, default_platform, default_markets, default_language, onboarded: true },
  });
});

test("first run: onboarding dialog saves mode, name, markets and platform", async ({ page, request }) => {
  await request.put(`${API}/api/settings`, { data: { onboarded: false } });
  await page.goto("/dashboard");
  const dialog = page.getByRole("dialog", { name: "Set up your workspace" });
  await expect(dialog).toBeVisible();

  await dialog.getByRole("radio", { name: /I manage creators or brands/ }).click();
  await dialog.getByLabel("Your name").fill("E2E Agency");
  await dialog.getByRole("button", { name: /United Kingdom/ }).click();
  await dialog.getByRole("radio", { name: /YouTube Shorts/ }).click();
  await dialog.getByRole("button", { name: "Save and continue" }).click();

  await expect(dialog).toHaveCount(0);
  await expect(page.getByText("Workspace set up")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("E2E Agency");

  const saved = await (await request.get(`${API}/api/settings`)).json();
  expect(saved).toMatchObject({ mode: "agency", display_name: "E2E Agency", default_platform: "youtube_shorts", onboarded: true });
  expect(saved.default_markets).toEqual(expect.arrayContaining(["UK"]));
});

test("onboarding can be skipped", async ({ page, request }) => {
  await request.put(`${API}/api/settings`, { data: { onboarded: false } });
  await page.goto("/dashboard");
  const dialog = page.getByRole("dialog", { name: "Set up your workspace" });
  await dialog.getByRole("button", { name: "Skip for now" }).click();
  await expect(dialog).toHaveCount(0);
  const saved = await (await request.get(`${API}/api/settings`)).json();
  expect(saved.onboarded).toBe(true);
});

test("settings: change the display name and mode, with a toast", async ({ page, request }) => {
  await request.put(`${API}/api/settings`, { data: { onboarded: true, mode: "creator" } });
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
  const save = page.getByRole("button", { name: "Save changes" });
  await expect(save).toBeDisabled();

  await page.getByLabel("Display name").fill("E2E Creator");
  await page.getByRole("radio", { name: /I manage creators or brands/ }).click();
  await expect(page.getByText(/Agency mode shows client labels/)).toBeVisible();
  await save.click();
  await expect(page.getByText("Settings saved")).toBeVisible();

  const saved = await (await request.get(`${API}/api/settings`)).json();
  expect(saved).toMatchObject({ display_name: "E2E Creator", mode: "agency" });

  // System facts are read-only and come from the API.
  await expect(page.getByText(/Policy library/).first()).toBeVisible();
  await expect(page.getByText(/rules$/).first()).toBeVisible();
});
