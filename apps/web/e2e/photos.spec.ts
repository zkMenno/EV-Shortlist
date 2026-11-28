import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { HAS_PHOTOS, NO_PHOTOS_REASON } from "./release";

// T-135: catalogue cards and generation pages show the release photo with its credit line, or a
// same-size neutral placeholder. Photos come from our own origin (/photos/…, Decision 081/086).

test.beforeEach(() => {
  test.skip(!HAS_PHOTOS, NO_PHOTOS_REASON);
});

test("catalogue cards: photo with srcset, lazy, alt, and a credit line under it", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/nl/en/cars");
  const fig = page.getByTestId("explore-card").first().getByTestId("car-photo");
  await expect(fig).toBeVisible();
  const img = fig.locator("img");
  await expect(img).toHaveAttribute("src", /^\/photos\/[a-z0-9-]+-[0-9a-f]{8}-400\.webp$/);
  await expect(img).toHaveAttribute("srcset", /800w/);
  await expect(img).toHaveAttribute("loading", "lazy");
  await expect(img).toHaveAttribute("alt", /\S+ \S+/);
  // T-135 review S1: alt text never repeats the model ("Tesla Model Y Model Y (2021-2024)").
  const alts = await page.getByTestId("explore-card").locator("[data-testid=car-photo] img").evaluateAll((els) => els.map((e) => e.getAttribute("alt") ?? ""));
  expect(alts.length).toBeGreaterThan(10);
  expect(alts.filter((a) => /\b(\S+(?: \S+)?) \1\b/.test(a))).toEqual([]);
  const credit = fig.getByTestId("photo-caption");
  await expect(credit).toContainText(/^Photo: .+/);
  // T-169: the caption has two links now (file page first, then the licence deed).
  const link = credit.getByRole("link").first();
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", /noopener/);
  await expect(link).toHaveAttribute("href", /^https:\/\//);
  await img.scrollIntoViewIfNeeded();
  await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth)).toBeGreaterThan(0);
});

test("catalogue cards: the photo box has a fixed 16:9 shape before and after loading (no layout shift)", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/nl/en/cars");
  const boxes = page.locator('[data-testid="explore-card"] .evs-photo');
  await expect(boxes.first()).toBeVisible();
  const ratios = await boxes.evaluateAll((els) => els.slice(0, 12).map((e) => e.getBoundingClientRect().width / e.getBoundingClientRect().height));
  for (const r of ratios) expect(r).toBeCloseTo(16 / 9, 1);
});

test("a card without a photo shows the placeholder; its generation page does too", async ({ page }) => {
  await page.goto("/nl/en/cars");
  // Show every card, then find a generation without a photo.
  const cards = page.getByTestId("explore-card");
  await expect(cards.first()).toBeVisible();
  const none = page.getByTestId("car-photo-none").first();
  const more = page.getByTestId("show-more");
  // The server renders the first cards; "Show more" arrives once the full list has loaded.
  await expect(more).toBeVisible();
  for (let i = 0; i < 10 && (await none.count()) === 0 && (await more.isVisible()); i++) {
    const before = await cards.count();
    await more.click();
    await expect.poll(() => cards.count()).toBeGreaterThan(before);
  }
  await expect(none).toBeVisible();
  await expect(none).toContainText("No photo yet");
  const card = page.getByTestId("explore-card").filter({ has: page.getByTestId("car-photo-none") }).first();
  await card.getByRole("heading").getByRole("link").click();
  await expect(page.getByTestId("gen-photo-none")).toBeVisible();
  await expect(page.getByTestId("gen-photo")).toHaveCount(0);
});

test("generation page: the main photo loads straight away with its credit line", async ({ page }) => {
  await page.goto("/nl/en/cars");
  const card = page.getByTestId("explore-card").filter({ has: page.getByTestId("car-photo") }).first();
  await card.getByRole("heading").getByRole("link").click();
  const fig = page.getByTestId("gen-photo");
  await expect(fig).toBeVisible();
  const img = fig.locator("img");
  await expect(img).toHaveAttribute("loading", "eager");
  await expect(img).toHaveAttribute("alt", await page.locator("h1").innerText());
  await expect(fig.getByTestId("photo-caption")).toContainText(/^Photo: .+/);
  await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth)).toBeGreaterThan(0);
});

for (const scheme of ["light", "dark"] as const) {
  test(`photos, credit lines and placeholders have no critical or serious axe findings (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/nl/en/cars");
    await expect(page.getByTestId("car-photo").first()).toBeVisible();
    const r = await new AxeBuilder({ page })
      .include('[data-testid="car-photo"]')
      .include('[data-testid="car-photo-none"]')
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
      .analyze();
    const blocking = r.violations.filter((v) => v.impact === "critical" || v.impact === "serious").map((v) => `${v.id}: ${v.nodes.length}`);
    expect(blocking).toEqual([]);
  });
}
