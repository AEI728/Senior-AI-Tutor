import { test, expect } from "@playwright/test";
test("真实ASR模型数据库导航和TTS（自制语音模拟麦克风）", async ({
  page,
  request,
}) => {
  const health = await request.get("/health/ready");
  expect((await health.json()).provider).toBe("deepseek");
  const auth = await request.post("/api/v1/auth/register", {
    data: {
      username: "live_browser_" + Date.now(),
      password: "synthetic-test-" + Date.now() + "-123",
    },
  });
  expect(auth.ok()).toBeTruthy();
  const { access_token } = await auth.json();
  await page.addInitScript(
    (t) => sessionStorage.setItem("xiaoban-token", t),
    access_token,
  );
  const audioResponses: number[] = [];
  page.on("response", (r) => {
    if (r.url().endsWith("/audio/speech")) audioResponses.push(r.status());
  });
  await page.goto("/practice?mode=voice");
  await page.getByRole("button", { name: "小伴语音助手" }).hover();
  await page.mouse.down();
  await expect.poll(() => page.locator('.voice-input[data-owner="assistant"]').getAttribute("data-samples").then(Number)).toBeGreaterThan(200000);
  await page.mouse.up();
  await expect(page.getByRole("dialog", { name: "小伴操作助手" })).toHaveCount(
    0,
  );
  await expect(
    page.locator('[data-course-ready="repotting-basics"]'),
  ).toBeVisible();
  await expect(page.locator(".direct-conversation .reply")).toHaveCount(0);
  await expect
    .poll(() => audioResponses.includes(200), { timeout: 45000 })
    .toBeTruthy();
  await expect(page.getByRole("button", { name: "小伴语音助手" })).toBeEnabled();
  await page.screenshot({
    path: "../../artifacts/ui/real-voice-navigation.png",
    fullPage: true,
  });
  const library = await request.get("/api/v1/library", {
    headers: { Authorization: "Bearer " + access_token },
  });
  expect((await library.json()).items).toHaveLength(1);
  await request.delete("/api/v1/me/data", {
    headers: { Authorization: "Bearer " + access_token },
    data: { confirmation: "DELETE_MY_DATA" },
  });
});

test("真实语音陪练使用独立录音和接口，不触发助手页面操作", async ({ page, request }) => {
  const auth = await request.post("/api/v1/auth/register", { data: { username: "live_coach_" + Date.now(), password: "real-coach-test-123456" } });
  const { access_token } = await auth.json();
  await page.addInitScript(t => sessionStorage.setItem("xiaoban-token", t), access_token);
  let assistantCalls = 0;
  page.on("request", r => { if (r.url().endsWith("/agent/turns")) assistantCalls++; });
  await page.goto("/practice?mode=voice");
  const coach = page.waitForResponse(r => r.url().endsWith("/voice/coach"), { timeout: 65000 });
  const speech = page.waitForResponse(r => r.url().endsWith("/audio/speech"), { timeout: 65000 });
  await page.getByRole("button", { name: "开始语音陪练", exact: true }).click();
  const response = await coach;
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(result.intent).toBe("VOICE_COACH"); expect(result.ui_actions).toEqual([]);
  expect((await speech).status()).toBe(200);
  expect(assistantCalls).toBe(0);
  await expect(page).toHaveURL(/\/practice\?mode=voice$/);
  await expect(page.getByRole("button", { name: "小伴语音助手" })).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByText(result.reply.display_text, { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "结束语音陪练", exact: true }).click();
  await request.delete("/api/v1/me/data", { headers: { Authorization: "Bearer " + access_token }, data: { confirmation: "DELETE_MY_DATA" } });
});
