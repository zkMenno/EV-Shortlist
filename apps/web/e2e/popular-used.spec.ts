import { readFileSync } from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// T-131: the landing's "Popular used EVs" section renders the editorial list as generation cards,
// in the list's order, skipping generations the release has no rows for.
const list = JSON.parse(readFileSync(path.resolve(process.cwd(), "src/config/popular-used.generated.json"), "utf8")) as {
  landing_count: number;
  generations: { generation_id: string; why: string }[];
};

test("landing: popular used EVs in the editorial order, each with a link, why line, used price and winter range", async ({ page }) => {
  await page.goto("/nl/en");
  const section = page.getByTestId("popular-used");
  await expect(section.getByRole("heading", { level: 2 })).toHaveText("Popular used EVs");
  await expect(page.getByTestId("popular-used-intro")).toContainText("one person's opinion");
  const cards = section.getByTestId("popular-card");
  const n = await cards.count();
  expect(n).toBeGreaterThan(0);
  expect(n).toBeLessThanOrEqual(list.landing_count);
  const ids = await cards.evaluateAll((els) => els.map((e) => e.getAttribute("data-generation")));
  // Same order as the list (a subsequence: generations without rows are skipped, never shown empty).
  const order = list.generations.map((g) => g.generation_id);
  const positions = ids.map((id) => order.indexOf(id!));
  expect(positions.every((p) => p >= 0)).toBe(true);
  expect([...positions].sort((a, b) => a - b)).toEqual(positions);
  for (let i = 0; i < n; i++) {
    const card = cards.nth(i);
    const why = list.generations.find((g) => g.generation_id === ids[i])!.why;
    await expect(card.getByTestId("popular-why")).toHaveText(why);
    await expect(card.getByRole("heading").getByRole("link")).toHaveAttribute("href", /^\/nl\/en\/ev\/[^/]+\/[^/]+\/[^/]+$/);
    await expect(card.getByTestId("popular-used-price")).toContainText(/€|not known/);
    await expect(card.getByTestId("popular-winter")).toContainText("km winter");
    // Photo with credit, or the same-size placeholder (T-135).
    expect((await card.getByTestId("car-photo").count()) + (await card.getByTestId("car-photo-none").count())).toBe(1);
  }
});

test("landing: the section follows the questions and hides on the results", async ({ page }) => {
  await page.goto("/nl/en?role=main&trips=monthly&charge=home&budget=40000");
  await expect(page.getByTestId("hero-card").first()).toBeVisible();
  await expect(page.getByTestId("popular-used")).toBeHidden();
});

test("landing: popular used EVs fit a 360 px phone (also with wider letters)", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/nl/en");
  await expect(page.getByTestId("popular-card").first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  await page.addStyleTag({ content: "* { letter-spacing: 0.06em !important; }" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
});

for (const scheme of ["light", "dark"] as const) {
  test(`landing: popular used EVs have no critical or serious axe findings (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/nl/en");
    await expect(page.getByTestId("popular-card").first()).toBeVisible();
    const r = await new AxeBuilder({ page })
      .include('[data-testid="popular-used"]')
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
      .analyze();
    expect(r.violations.filter((v) => v.impact === "critical" || v.impact === "serious").map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
  });
}

test("landing: 'How we pick these' explains this list's points, credits say they open a new tab and link the licence (T-169)", async ({ page }) => {
  await page.goto("/nl/en");
  const how = page.getByTestId("popular-how");
  await how.getByText("How we pick these").click();
  await expect(how).toContainText("top 40 most registered EVs");
  await expect(how).toContainText("+20 for a car on the shortlist");
  await expect(how).toContainText("-10 for one ruled out");
  await expect(page.getByTestId("popular-used-intro")).toContainText("the site owner's own picks");
  for (const why of await page.getByTestId("popular-why").allInnerTexts()) expect(why).not.toMatch(/\bthe owner\b/);
  const caption = page.getByTestId("popular-used").getByTestId("photo-caption").first();
  await expect(caption.getByRole("link").first()).toHaveAccessibleName(/\(opens in a new tab\)$/);
  await expect(caption.getByTestId("photo-licence")).toHaveAttribute("href", /^https:\/\/creativecommons\.org\/(licenses|publicdomain)\//);
  // Years once: a generation name that holds years gets no second "· 2021–2024".
  for (const line of await page.getByTestId("popular-card").locator("h3 + p").allInnerTexts()) {
    expect(line.match(/\b(19|20)\d{2}\b/g)?.length ?? 0, line).toBeLessThanOrEqual(2);
  }
});
