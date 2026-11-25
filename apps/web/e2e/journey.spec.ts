import { test, expect } from "@playwright/test";
test("拒绝语音权限也不显示气泡或弹窗", async ({ page }) => {
  await page.route("**/api/v1/me", async (route) => {
    const r = await route.fetch();
    await route.fulfill({
      response: r,
      json: { ...(await r.json()), audio_provider: "real" },
    });
  });
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () =>
      Promise.reject(new DOMException("denied", "NotAllowedError"));
  });
  await page.goto("/");
  await page.getByRole("button", { name: "小伴语音助手" }).hover();
  await page.mouse.down();
  await expect(page.getByRole("button", { name: "小伴语音助手" })).toHaveAttribute("title", /未获授权/);
  await page.mouse.up();
  await expect(
    page.getByRole("button", { name: "小伴语音助手" }),
  ).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".voice-error-only")).toHaveCount(0);
});
