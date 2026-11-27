import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { HAS_PHOTOS, HAS_SCORES, NO_PHOTOS_REASON, NO_SCORES_REASON } from "./release";

// T-146: on phones the answers sidebar opens as a bottom sheet from the results; on desktop it stays
// a sidebar. Answers and refine filters stay in the URL whichever way the sheet closes.
const RESULTS = "/nl/en?role=main&trips=monthly&charge=home&budget=40000";

async function openSheet(page: Page) {
  await page.getByTestId("hero-refine-open").click();
  const dialog = page.getByRole("dialog", { name: "Your answers" });
  await expect(dialog).toBeVisible();
  return dialog;
}

test.describe("hero results on a phone (360 px)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_SCORES, NO_SCORES_REASON);
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto(RESULTS);
    await expect(page.getByTestId("hero-shortlist").getByTestId("hero-card").first()).toBeVisible();
  });

  test("the sidebar is hidden until 'Answers & refine' opens it as a sheet with the same controls", async ({ page }) => {
    await expect(page.getByTestId("hero-side")).toBeHidden();
    const dialog = await openSheet(page);
    // The same controls as the desktop sidebar: every answer with its change button, presets, refine.
    await expect(dialog.getByTestId("hero-answers")).toBeVisible();
    await expect(dialog.getByTestId("hero-answer-trips")).toBeVisible();
    await expect(dialog.getByTestId("hero-refine")).toBeVisible();
    await expect(page.getByTestId("hero-sheet-close")).toBeFocused();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test("focus stays inside the open sheet", async ({ page }) => {
    await openSheet(page);
    const sheet = page.getByTestId("hero-sheet");
    for (let i = 0; i < 30; i++) {
      await page.keyboard.press("Tab");
      expect(await sheet.evaluate((el) => el.contains(document.activeElement)), `Tab ${i + 1} left the sheet`).toBe(true);
    }
    await page.keyboard.press("Shift+Tab");
    expect(await sheet.evaluate((el) => el.contains(document.activeElement))).toBe(true);
  });

  test("a refine change made in the sheet stays in the URL after Escape; focus returns to the button", async ({ page }) => {
    const dialog = await openSheet(page);
    await dialog.getByTestId("hero-refine").locator("summary").click();
    await dialog.getByTestId("hero-seats").selectOption("7");
    await expect(page).toHaveURL(/seats=7/);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByTestId("hero-refine-open")).toBeFocused();
    await expect(page).toHaveURL(/seats=7/);
    await expect(page).toHaveURL(/role=main/);
    await expect(page.getByTestId("hero-refine-open")).toContainText("· 1");
  });

  test("the phone's Back button closes the sheet and keeps the answers and filters", async ({ page }) => {
    const dialog = await openSheet(page);
    await dialog.getByTestId("hero-refine").locator("summary").click();
    await dialog.getByTestId("hero-seats").selectOption("5");
    await expect(page).toHaveURL(/seats=5/);
    await page.goBack();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page).toHaveURL(/seats=5/);
    await expect(page).toHaveURL(/budget=40000/);
    // Still the results (5+ seats leaves plenty of cars), not a question.
    await expect(page.getByTestId("hero-card").first()).toBeVisible();
    await expect(page.getByTestId("hero-refine-open")).toContainText("· 1");
  });

  test("close, 'Show my top 10' and a swipe down on the top bar all close it", async ({ page }) => {
    await openSheet(page);
    await page.getByTestId("hero-sheet-close").click();
    await expect(page.getByRole("dialog")).toHaveCount(0);

    await openSheet(page);
    await page.getByTestId("hero-sheet-done").click();
    await expect(page.getByRole("dialog")).toHaveCount(0);

    await openSheet(page);
    const bar = page.getByTestId("hero-sheet-bar");
    const box = (await bar.boundingBox())!;
    const x = box.x + box.width / 2;
    const y = box.y + 10;
    await bar.dispatchEvent("touchstart", { touches: [{ identifier: 1, clientX: x, clientY: y }] });
    await bar.dispatchEvent("touchmove", { touches: [{ identifier: 1, clientX: x, clientY: y + 160 }] });
    await bar.dispatchEvent("touchend", { touches: [] });
    await expect(page.getByRole("dialog")).toHaveCount(0);
    // Every close went through Back: no sheet entries are left in the history.
    await expect(page).toHaveURL(/role=main/);
  });

  test("a short swipe snaps back and the sheet stays open", async ({ page }) => {
    await openSheet(page);
    const bar = page.getByTestId("hero-sheet-bar");
    const box = (await bar.boundingBox())!;
    const x = box.x + box.width / 2;
    const y = box.y + 10;
    await bar.dispatchEvent("touchstart", { touches: [{ identifier: 1, clientX: x, clientY: y }] });
    await bar.dispatchEvent("touchmove", { touches: [{ identifier: 1, clientX: x, clientY: y + 30 }] });
    await bar.dispatchEvent("touchend", { touches: [] });
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByTestId("hero-sheet")).toHaveAttribute("style", /^(?!.*translateY)/);
  });

  test("a change button in the sheet opens that question; Back returns to the results", async ({ page }) => {
    const dialog = await openSheet(page);
    await dialog.getByTestId("hero-answer-trips").click();
    await expect(page).toHaveURL(/q=trips/);
    await expect(page.getByTestId("hero-q-trips")).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.goBack();
    await expect(page.getByTestId("hero-shortlist").getByTestId("hero-card").first()).toBeVisible();
  });

  for (const scheme of ["light", "dark"] as const) {
    test(`the open sheet has no critical or serious axe findings (${scheme})`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await openSheet(page);
      const r = await new AxeBuilder({ page }).include('[data-testid="hero-sheet"]').withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]).analyze();
      const blocking = r.violations.filter((v) => v.impact === "critical" || v.impact === "serious").map((v) => `${v.id}: ${v.nodes.length}`);
      expect(blocking).toEqual([]);
    });
  }

  test("widening past 640 px closes the sheet and shows the sidebar", async ({ page }) => {
    await openSheet(page);
    await page.setViewportSize({ width: 800, height: 900 });
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByTestId("hero-side")).toBeVisible();
    await expect(page.getByTestId("hero-refine-open")).toBeHidden();
  });
});

test("hero results on desktop: no sheet button, the sidebar is a plain landmark", async ({ page }) => {
  test.skip(!HAS_SCORES, NO_SCORES_REASON);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(RESULTS);
  await expect(page.getByTestId("hero-side")).toBeVisible();
  await expect(page.getByTestId("hero-refine-open")).toBeHidden();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByTestId("hero-sheet-close")).toBeHidden();
});

test("shortlist rows show the generation's photo with its credit, at a fixed size", async ({ page }) => {
  test.skip(!HAS_SCORES, NO_SCORES_REASON);
  test.skip(!HAS_PHOTOS, NO_PHOTOS_REASON);
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(RESULTS);
  const thumbs = page.getByTestId("hero-shortlist").getByTestId("car-thumb");
  await expect(thumbs.first()).toBeVisible();
  const img = thumbs.first().locator("img");
  await expect(img).toHaveAttribute("src", /^\/photos\/[a-z0-9-]+-[0-9a-f]{8}-400\.webp$/);
  await expect(img).toHaveAttribute("loading", "lazy");
  await expect(img).toHaveAttribute("alt", /\S+ \S+/);
  // Fixed box: width and height are set before the file arrives, so the row doesn't jump.
  await expect(img).toHaveAttribute("width", "72");
  await expect(img).toHaveAttribute("height", "48");
  await img.scrollIntoViewIfNeeded();
  await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth)).toBeGreaterThan(0);
  // The credit is one tap away.
  await thumbs.first().getByRole("button").click();
  await expect(page.getByTestId("photo-credit").first()).toBeVisible();
  await expect(page.getByTestId("photo-credit").first()).not.toBeEmpty();
});

test("photo route serves release photos only", async ({ request }) => {
  test.skip(!HAS_PHOTOS, NO_PHOTOS_REASON);
  const bad = await request.get("/photos/..%2Fcatalogue.json");
  expect(bad.status()).toBe(404);
  const missing = await request.get("/photos/not-a-car-00000000-400.webp");
  expect(missing.status()).toBe(404);
});
