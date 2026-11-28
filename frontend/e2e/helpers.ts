import type { APIRequestContext, Page } from "@playwright/test";

/** The API the app under test talks to (server-side calls from the test runner, no CORS). */
export const API = (process.env.E2E_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

/** Mark the workspace onboarded so the first-run dialog does not cover the page. */
export async function ensureOnboarded(request: APIRequestContext) {
  await request.put(`${API}/api/settings`, { data: { onboarded: true } });
}

/** If the onboarding dialog is open anyway, skip it. */
export async function skipOnboarding(page: Page) {
  const dialog = page.getByRole("dialog", { name: "Set up your workspace" });
  if (await dialog.isVisible().catch(() => false)) await dialog.getByRole("button", { name: "Skip for now" }).click();
}
