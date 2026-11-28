import { expect, test } from "@playwright/test";
import { ENGLISH_ONLY } from "./langs";

// T-130: the landing page links to the catalogue; the catalogue sorts by popularity by default.

test("landing has no full list, only a 'Show all cars' link to the catalogue", async ({ page }) => {
  await page.goto("/nl/en");
  await expect(page.getByTestId("explore-row")).toHaveCount(0);
  await expect(page.getByTestId("explore-card")).toHaveCount(0);
  const link = page.getByTestId("show-all-cars-link");
  await expect(link).toHaveText("Show all cars");
  await expect(link).toHaveAttribute("href", "/nl/en/cars");
  await link.click();
  await expect(page).toHaveURL(/\/nl\/en\/cars/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("All electric cars");
});

test("catalogue: Most popular first as cards, #n tags in order, How we rank explains the blend", async ({ page }) => {
  await page.goto("/nl/en/cars");
  await expect(page.getByTestId("result-count")).not.toContainText("…");
  await expect(page.getByTestId("sort-menu")).toHaveValue("popular");
  await expect(page.getByTestId("explore-cards")).toBeVisible();
  const tags = await page.getByTestId("popular-tag").allInnerTexts();
  expect(tags.length).toBeGreaterThan(3);
  expect(tags[0]).toBe("#1 in Most popular");
  const ranks = tags.map((t) => Number(t.match(/\d+/)![0]));
  expect(ranks, "ranks never go down the list").toEqual([...ranks].sort((a, b) => a - b));
  expect(new Set(ranks).size, "one tag per generation, not per variant").toBe(ranks.length);
  await expect(page.getByTestId("popular-why")).toContainText("Netherlands and the UK");
  await page.getByTestId("popular-why").getByRole("link", { name: "How we rank" }).click();
  await expect(page.getByTestId("how-we-rank")).toBeInViewport();
  await expect(page.getByTestId("how-we-rank")).toContainText("80 % comes from registrations");
  await expect(page.getByTestId("how-we-rank")).toContainText("one person's verdict");
  await expect(page.getByTestId("how-we-rank")).toContainText("CC0");
  await expect(page.getByTestId("how-we-rank")).toContainText("Open Government Licence v3");
});

test("catalogue Nerd level: the popularity tag shows its score, sources, licences and date", async ({ page }) => {
  await page.goto("/nl/en/cars?level=nerd");
  await expect(page.getByTestId("result-count")).not.toContainText("…");
  await expect(page.getByTestId("popular-nerd").first()).toContainText(/Score [\d.]+\/100 · registrations RDW \(CC0\) \+ DfT \(OGL v3\), \d{4}-\d{2}-\d{2}/);
});

test("catalogue: the sort menu writes the URL and survives a reload", async ({ page }) => {
  await page.goto("/nl/en/cars");
  await expect(page.getByTestId("result-count")).not.toContainText("…");
  await page.getByTestId("sort-menu").selectOption("used");
  await expect(page).toHaveURL(/[?&]sort=used(&|$)/);
  await expect(page.getByTestId("popular-why")).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId("sort-menu")).toHaveValue("used");
  await page.getByTestId("sort-menu").selectOption("winter");
  await expect(page).toHaveURL(/[?&]sort=-winter(&|$)/);
});

test("old Explore links on the landing page move to the catalogue with their state", async ({ page }) => {
  await page.goto("/nl/en?view=table&range=300");
  await expect(page).toHaveURL(/\/nl\/en\/cars\?view=table&range=300$/);
  await expect(page.locator("#f-rangeMin")).toHaveValue("300");
  // Old links with hero answers move too; /cars reads the answers (review #117).
  await page.goto("/nl/en?role=only&trips=monthly&sort=-suggested&view=table");
  await expect(page).toHaveURL(/\/nl\/en\/cars\?role=only&trips=monthly&sort=-suggested&view=table/);
  // Hero links stay on the landing page.
  await page.goto("/nl/en?role=second&budget=20000");
  await expect(page).toHaveURL(/\/nl\/en\?role=second&budget=20000$/);
});

// Every served language: long words and native <select> widths differ (FR and ES overflowed at first; T-097 lesson).
// English only at launch (Decision 082): every launch country in English, so currency and country labels still vary.
const PHONE_PATHS = ENGLISH_ONLY
  ? ["/nl/en", "/be/en", "/de/en", "/fr/en", "/es/en", "/it/en", "/uk/en"]
  : ["/nl/en", "/nl/nl", "/de/de", "/fr/fr", "/es/es", "/it/it"];
test("catalogue fits a 360 px phone without sideways scrolling, in every served language", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  for (const path of PHONE_PATHS) {
    await page.goto(`${path}/cars`);
    await expect(page.getByTestId("result-count")).not.toContainText("…");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${path}/cars is wider than the phone`).toBeLessThanOrEqual(0);
    const menu = await page.getByTestId("sort-menu").boundingBox();
    expect(menu!.x + menu!.width, `${path}: sort menu sticks out`).toBeLessThanOrEqual(360);
  }
});

// T-130 part 2: the design's visual layer.

test("catalogue cards: one card per generation with used price and the three facts; count says models", async ({ page }) => {
  await page.goto("/nl/en/cars");
  await expect(page.getByTestId("result-count")).not.toContainText("…");
  await expect(page.getByTestId("result-count")).toHaveText(/^\d+ models · used prices in the Netherlands$/);
  const gens = await page.getByTestId("explore-card").evaluateAll((els) => els.map((e) => e.getAttribute("data-generation")));
  expect(gens.length).toBeGreaterThan(10);
  expect(new Set(gens).size, "one card per generation").toBe(gens.length);
  const first = page.getByTestId("explore-card").first();
  await expect(first.getByTestId("card-used")).toContainText("used, in the Netherlands");
  await expect(first.getByTestId("fact-winter")).toContainText("km winter");
  await expect(first.getByTestId("fact-summer")).toContainText("km summer");
  await expect(first.getByTestId("fact-dc20")).toContainText("km / 20 min");
  // The card links to the generation page.
  await expect(first.getByRole("heading", { level: 3 }).getByRole("link")).toHaveAttribute("href", /^\/nl\/en\/ev\/[^/]+\/[^/]+\/[^/]+$/);
});

test("catalogue filters: used price, winter range and fast-charging tiles write the URL; pills remove them", async ({ page }) => {
  await page.goto("/nl/en/cars?umax=25000&winter=250");
  await expect(page.getByTestId("result-count")).not.toContainText("…");
  await expect(page.getByTestId("result-count")).toContainText(/^\d+ of \d+ models match/);
  const pills = page.getByTestId("filter-pill");
  await expect(pills).toHaveText([/^Up to €25,000 used/, /^250\+ km winter/]);
  await expect(page.locator("#f-usedMax")).toHaveValue("25000");
  await expect(page.locator("#f-winterMin")).toHaveValue("250");

  await page.getByTestId("fg-fast").getByRole("button", { name: "+150 km" }).click();
  await expect(page).toHaveURL(/[?&]dc=150(&|$)/);
  await expect(page.getByTestId("fg-fast").getByRole("button", { name: "+150 km" })).toHaveAttribute("aria-pressed", "true");
  await expect(pills).toHaveCount(3);

  await pills.filter({ hasText: "250+ km winter" }).click();
  await expect(page).not.toHaveURL(/winter=/);
  await page.getByTestId("filter-pills-clear").click();
  await expect(page).not.toHaveURL(/umax=|dc=/);
  await expect(page.getByTestId("filter-pills")).toHaveCount(0);
});

test("catalogue brand filter: search the list, tick a brand, the pill names it", async ({ page }) => {
  await page.goto("/nl/en/cars");
  await expect(page.getByTestId("result-count")).not.toContainText("…");
  await page.getByLabel("Find a brand").fill("kia");
  const list = page.getByTestId("brand-list");
  await expect(list.getByRole("checkbox")).toHaveCount(1);
  await list.getByRole("checkbox").check();
  await expect(page).toHaveURL(/[?&]make=kia(&|$)/);
  await expect(page.getByTestId("filter-pill")).toHaveText([/^Kia/]);
  for (const name of await page.getByTestId("explore-card").getByRole("heading", { level: 3 }).allInnerTexts()) expect(name).toMatch(/^Kia /);
});

test("catalogue on a phone: Filters · n opens a bottom sheet; Show n cars and Escape close it", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto("/nl/en/cars?body=suv");
  await expect(page.getByTestId("result-count")).not.toContainText("…");
  const open = page.getByTestId("filters-open");
  await expect(open).toHaveText(/Filters · 1/);
  await expect(page.locator("#filters-form")).toBeHidden();
  // The bar stays on screen while the list scrolls.
  await page.mouse.wheel(0, 1500);
  await expect(open).toBeInViewport();

  await open.click();
  const sheet = page.getByRole("dialog", { name: "Filters" });
  await expect(sheet).toBeVisible();
  await expect(page.getByRole("button", { name: "Close filters" })).toBeFocused();
  const show = page.getByTestId("filters-show");
  await expect(show).toHaveText(/^Show \d+ cars$/);
  await show.click();
  await expect(sheet).toBeHidden();
  await expect(open).toBeFocused();

  await open.click();
  await expect(sheet).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
});

// Review #126: the sheet re-focused "Close" after every change, so typed values lost all but one digit.
test("phone sheet: typing a value keeps focus in the field; Tab stays inside; widening closes it", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto("/nl/en/cars");
  await expect(page.getByTestId("result-count")).not.toContainText("…");
  await page.getByTestId("filters-open").click();
  const sheet = page.getByRole("dialog", { name: "Filters" });
  await page.locator("#f-usedMin").click();
  await page.keyboard.type("10000");
  await expect(page.locator("#f-usedMin")).toHaveValue("10000");
  await expect(page.locator("#f-usedMin")).toBeFocused();
  await expect(page).toHaveURL(/[?&]umin=10000(&|$)/);
  // A group that opened for its filter stays open when the value is cleared.
  const sbt = page.getByTestId("fg-sbt");
  await sbt.locator("summary").click();
  await page.locator("#f-seatsMin").fill("5");
  await page.locator("#f-seatsMin").press("Backspace");
  await expect(sbt).toHaveAttribute("open", "");
  await expect(page.locator("#f-seatsMin")).toBeFocused();
  // Tab from the last control wraps to the first one inside the sheet.
  await page.getByTestId("filters-show").focus();
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))).toBe(true);
  // "Clear all" removes itself: focus lands on the sheet's heading, not on the page body.
  await page.getByTestId("filters-clear-all").click();
  await expect(page.getByRole("heading", { name: "Filters" })).toBeFocused();
  await expect(sheet).toBeVisible();
  // Widening to the sidebar layout closes the sheet and unlocks the page.
  await page.setViewportSize({ width: 1280, height: 800 });
  await expect(sheet).toHaveCount(0);
  expect(await page.evaluate(() => document.body.style.overflow)).toBe("");
});

// Review #126 round 3: CI's fonts run wider than local ones, so a card that fits locally overflowed
// there. Widen every letter by 6 % (the T-097 "12 % wider text" lesson, halved for letter-spacing)
// and check every level still fits a 360 px phone.
test("catalogue cards fit 360 px at every level even with wider text (CI fonts)", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  for (const level of ["simple", "detailed", "nerd"]) {
    await page.goto(`/nl/en/cars?level=${level}`);
    await expect(page.getByTestId("result-count")).not.toContainText("…");
    await page.addStyleTag({ content: "*{letter-spacing:0.06em !important}" });
    const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(over, `level ${level}: page wider than the phone with wider text`).toBeLessThanOrEqual(0);
  }
});
