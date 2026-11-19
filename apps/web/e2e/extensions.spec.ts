import { test, expect } from "@playwright/test";
test("麦克风处于四栏正中，字号在顶部", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("nav a")).toHaveText([
    "首页",
    "技能广场",
    "陪练",
    "分享",
  ]);
  const mic = await page
      .getByRole("button", { name: "小伴语音助手" })
      .boundingBox(),
    left = await page.locator("nav a").nth(1).boundingBox(),
    right = await page.locator("nav a").nth(2).boundingBox(),
    font = await page.getByRole("button", { name: "放大字号" }).boundingBox();
  expect(mic!.x).toBeGreaterThan(left!.x + left!.width);
  expect(mic!.x + mic!.width).toBeLessThan(right!.x);
  expect(mic!.y).toBeGreaterThan(740);
  expect(font!.y).toBeLessThan(80);
  await page.screenshot({ path: "../../artifacts/ui/nav-example-home.png" });
});
