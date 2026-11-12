import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

// Runs only via scripts/e2e-connections.sh, which points the backend at the fake
// Instagram/YouTube server (backend/tests/fake_platforms.py) and uses mock AI.
test.skip(!process.env.E2E_FAKE_PLATFORMS, "requires scripts/e2e-connections.sh");

const SHOTS = path.resolve(__dirname, "../../var/e2e-results");

async function connect(page: Page, name: "Instagram" | "YouTube") {
  await page.goto("/connections");
  await page.getByRole("button", { name: new RegExp(`^Connect (another )?${name}`) }).click();
  await page.waitForURL(/\/connections\?connected=/);
  await expect(page.getByText(`${name} connected`)).toBeVisible();
}

async function importPost(page: Page, account: RegExp, pick: { title?: string; link?: string }) {
  await page.goto("/analyses/new");
  await page.getByRole("tab", { name: /From your account/ }).click();
  const select = page.getByLabel("Connected account");
  const option = await select.locator("option", { hasText: account }).getAttribute("value");
  await select.selectOption(option!);
  if (pick.title) await page.getByRole("button", { name: new RegExp(pick.title) }).click();
  if (pick.link) await page.getByLabel("…or paste a link").fill(pick.link);
  await page.getByText("I am authorized to analyse this post").click();
  await page.getByRole("button", { name: "Analyse post" }).click();
}

test("connect accounts, import own posts, enforce ownership, disconnect", async ({ page }) => {
  await connect(page, "Instagram");
  await connect(page, "YouTube");
  await expect(page.getByText("@creator_demo")).toBeVisible();
  await expect(page.getByText("Demo Creator")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/connections.png`, fullPage: true });

  // Instagram Reel with a downloadable file -> full video analysis
  await importPost(page, /Instagram/, { title: "Morning routine with FitFuel" });
  await page.waitForURL(/\/analyses\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: /^Findings/ })).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText("Instagram import · Full video analysis")).toBeVisible();
  await expect(page.getByRole("complementary").locator("video")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/import-instagram-full.png`, fullPage: true });

  // Reel with licensed audio -> Instagram withholds the file -> caption + thumbnail
  await importPost(page, /Instagram/, { title: "Glow up in 7 days" });
  await expect(page.getByText("Caption + thumbnail review only — Instagram did not provide the video file")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByRole("img", { name: "Post thumbnail" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/import-instagram-thumbnail.png`, fullPage: true });

  // YouTube: someone else's video is refused
  await importPost(page, /YouTube/, { link: "https://youtu.be/vidOther001" });
  await expect(page.getByText(/does not belong to Demo Creator/)).toBeVisible();

  // YouTube: own private video via Shorts link -> metadata + captions audit
  await page.getByLabel("…or paste a link").fill("https://youtube.com/shorts/vidOwn00001");
  await page.getByRole("button", { name: "Analyse post" }).click();
  await expect(page.getByText("Metadata review only — the video itself was not analysed")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByRole("tab", { name: "Transcript (3)" }).or(page.getByRole("button", { name: "Transcript (3)" }))).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/import-youtube-metadata.png`, fullPage: true });

  // Disconnect YouTube -> its imported analysis is deleted
  await page.goto("/connections");
  const ytCard = page.getByLabel("YouTube account");
  await ytCard.getByRole("button", { name: "Disconnect" }).click();
  await ytCard.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.getByText("Demo Creator")).toHaveCount(0);
  await page.goto("/dashboard");
  await expect(page.getByText("My morning routine 💪 #shorts")).toHaveCount(0);
  await expect(page.getByText("Morning routine with FitFuel").first()).toBeVisible();
});
