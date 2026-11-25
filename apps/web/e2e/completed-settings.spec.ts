import { test, expect } from "@playwright/test";

test("完成技能持久保存，重新学习后移出已完成", async ({ page, request }) => {
  const auth = await request.post("/api/v1/auth/register", { data: { username: "completed_" + Date.now(), password: "completed-test-123456" } });
  const { access_token } = await auth.json();
  const headers = { Authorization: "Bearer " + access_token };
  await request.put("/api/v1/library/calligraphy", { headers });
  await page.addInitScript((t) => sessionStorage.setItem("xiaoban-token", t), access_token);
  await page.goto("/");
  await page.getByRole("button", { name: "完成学习", exact: true }).click();
  await expect(page.locator(".skill-card")).toHaveCount(0);
  await page.goto("/skills");
  await page.getByRole("button", { name: "已完成 1", exact: true }).click();
  await expect(page.locator(".plaza-skill")).toHaveCount(1);
  await page.reload();
  await page.getByRole("button", { name: "已完成 1", exact: true }).click();
  await page.screenshot({ path: "../../artifacts/ui/completed-skills-2026-11-19.png" });
  await page.locator(".plaza-skill").click();
  await page.getByRole("button", { name: "加入学习", exact: true }).click();
  await expect.poll(async () => (await (await request.get("/api/v1/library/completed", { headers })).json()).items.length).toBe(0);
  await request.delete("/api/v1/me/data", { headers, data: { confirmation: "DELETE_MY_DATA" } });
});

test("保护页面只保留删除模块", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "学习设置", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "学习设置", exact: true }).click();
  await expect(page.getByRole("link", { name: "学习设置", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "删除我的学习数据" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "学习设置" })).toHaveCount(0);
  await expect(page.getByText("我的与隐私", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "我的分享", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "删除我的学习记录" })).toBeDisabled();
  await page.screenshot({ path: "../../artifacts/ui/delete-only-2026-11-19.png" });
});

test("麦克风被拒绝会播报原因且不弹文字气泡", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: () => Promise.reject(new DOMException("Denied", "NotAllowedError")) });
    Object.defineProperty(speechSynthesis, "speak", { value: (speech: SpeechSynthesisUtterance) => { (window as any).spokenError = speech.text; speech.onend?.(new Event("end") as SpeechSynthesisEvent); } });
  });
  await page.route("**/api/v1/me", async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...(await response.json()), audio_provider: "test" } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "小伴语音助手" }).hover();
  await page.mouse.down();
  await expect(page.getByRole("button", { name: "小伴语音助手" })).toHaveAttribute("title", /未获授权/);
  await page.mouse.up();
  await expect.poll(() => page.evaluate(() => (window as any).spokenError || "")).toContain("未获授权");
  await expect(page.getByRole("button", { name: "小伴语音助手" })).toHaveAttribute("title", /未获授权/);
  await expect(page.locator(".direct-conversation p")).toHaveCount(0);
});
