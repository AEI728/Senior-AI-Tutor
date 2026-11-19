import { test, expect } from "@playwright/test";
test("首页内置随机用户示例分享可播放，点赞收藏真实保存", async ({ page, request }) => {
  const auth = await request.post("/api/v1/auth/register", { data: { username: "example_feed_" + Date.now(), password: "example-test-123456" } });
  const { access_token } = await auth.json();
  await page.addInitScript((t) => sessionStorage.setItem("xiaoban-token", t), access_token);
  await page.goto("/");
  await expect(page.locator(".featured-skill")).toBeVisible();
  await expect(page.locator(".featured-copy")).toHaveCount(0);
  await page.locator(".featured-skill").click();
  await expect(page.locator(".recommendation-only video")).toBeVisible();
  await page.getByRole("link", { name: "返回首页" }).click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "分享", exact: true })
    .click();
  await expect(page.locator(".feed-card")).toHaveCount(4);
  const first = page.locator(".feed-card").first();
  await first.getByRole("button", { name: "点赞", exact: true }).click();
  await expect(
    first.getByRole("button", { name: "点赞", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "放大字号" })).toBeHidden();
  await page.screenshot({ path: "../../artifacts/ui/nav-examples-share.png" });
  await request.delete("/api/v1/me/data", { headers: { Authorization: "Bearer " + access_token }, data: { confirmation: "DELETE_MY_DATA" } });
});
test("视频与语音陪练可切换", async ({ page }) => {
  await page.goto("/practice?mode=voice");
  await expect(page.locator(".camera-practice")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "开始语音陪练" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "视频陪练", exact: true }).click();
  await expect(page.locator(".camera-practice")).toBeVisible();
  await page.getByRole("button", { name: "语音陪练", exact: true }).click();
  await expect(page.locator(".camera-practice")).toHaveCount(0);
});
