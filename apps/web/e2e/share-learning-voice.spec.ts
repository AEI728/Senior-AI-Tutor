import { test, expect } from "@playwright/test";
import path from "node:path";

test.use({ launchOptions: { args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--use-file-for-fake-audio-capture=" + path.resolve(import.meta.dirname, "fixtures/user-command.wav") + "%noloop"] } });

test("分享页按当前作品加入技能，页面变化不串目标，语音移除更新首页", async ({ page, request }) => {
  const auth = await request.post("/api/v1/auth/register", { data: { username: "share_voice_" + Date.now(), password: "synthetic-share-test-123" } });
  const { access_token } = await auth.json();
  const headers = { Authorization: "Bearer " + access_token };
  await page.addInitScript(t => {
    sessionStorage.setItem("xiaoban-token", t);
    Object.defineProperty(speechSynthesis, "speak", { value: (speech: SpeechSynthesisUtterance) => speech.onend?.(new Event("end") as SpeechSynthesisEvent) });
  }, access_token);
  await page.route("**/api/v1/me", async route => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...await response.json(), audio_provider: "test" } });
  });
  let phrase = "我想学这个";
  await page.route("**/api/v1/audio/transcriptions", route => route.fulfill({ json: { text: phrase } }));
  await page.goto("/share");
  const writing = page.locator('.feed-list [data-work-id="example-writing"]');
  await writing.scrollIntoViewIfNeeded();
  await expect.poll(() => writing.evaluate(card => {
    const box = card.getBoundingClientRect();
    return (Math.min(box.bottom, innerHeight) - Math.max(box.top, 0)) / box.height;
  })).toBeGreaterThan(0.6);
  const mic = page.getByRole("button", { name: "小伴语音助手" });
  await mic.hover(); await page.mouse.down();
  await page.waitForFunction(() => {
    const report = JSON.parse(sessionStorage.getItem("xiaoban-audio-report-assistant") || "{}");
    return report.phase === "recording" && report.samples > 16000;
  });
  await page.locator('.feed-list [data-work-id="example-music"]').scrollIntoViewIfNeeded();
  const sent = page.waitForRequest(r => r.url().endsWith("/agent/turns"));
  const done = page.waitForResponse(r => r.url().endsWith("/agent/turns"));
  await page.mouse.up();
  expect((await sent).postDataJSON().ui_context.focused_work_id).toBe("example-writing");
  expect((await done).status()).toBe(200);
  expect((await (await request.get("/api/v1/library", { headers })).json()).items.map((s: any) => s.skill_id)).toEqual(["calligraphy"]);
  await expect(mic).toBeEnabled();
  await page.goto("/");
  await expect(page.locator("#skill-library .skill-card")).toHaveCount(1);
  phrase = "我不想学书法了";
  await mic.hover(); await page.mouse.down();
  await page.waitForFunction(() => {
    const report = JSON.parse(sessionStorage.getItem("xiaoban-audio-report-assistant") || "{}");
    return report.phase === "recording" && report.samples > 16000;
  });
  await page.mouse.up();
  await expect(page.locator("#skill-library .skill-card")).toHaveCount(0);
  expect((await (await request.get("/api/v1/library", { headers })).json()).items).toEqual([]);
});
