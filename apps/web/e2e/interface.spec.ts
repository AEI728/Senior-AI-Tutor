import { test, expect } from "@playwright/test";
test("字号加减保留并在顶部，刷新仍记住", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#skill-library")).toBeVisible();
  for (let i = 0; i < 4; i++)
    await page.getByRole("button", { name: "放大字号" }).click();
  await expect(page.getByLabel("当前字号")).toHaveText("140%");
  await page.reload();
  await expect(page.getByLabel("当前字号")).toHaveText("140%");
  await page.getByRole("button", { name: "缩小字号" }).click();
  await expect(page.getByLabel("当前字号")).toHaveText("130%");
});
test("大字号下手机及桌面不横向溢出", async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("xiaoban-font-level", "4"),
  );
  for (const width of [320, 390, 640]) {
    await page.setViewportSize({ width, height: 844 });
    for (const route of ["/", "/skills", "/share", "/practice?mode=voice"]) {
      await page.goto(route);
      await expect(page.locator("nav")).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        route + " " + width,
      ).toBeTruthy();
    }
  }
});
