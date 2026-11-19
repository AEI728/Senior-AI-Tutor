import { test, expect } from "@playwright/test";
import path from "node:path";
test.use({
  launchOptions: {
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
      "--use-file-for-fake-audio-capture=" +
        path.resolve(import.meta.dirname, "fixtures/user-command.wav") +
        "%noloop",
    ],
  },
});
test("语音陪练单独进行语音指导且不弹气泡", async ({ page }) => {
  await page.route("**/api/v1/me", async (route) => {
    const r = await route.fetch();
    await route.fulfill({
      response: r,
      json: { ...(await r.json()), audio_provider: "test" },
    });
  });
  await page.route("**/api/v1/audio/transcriptions", (r) =>
    r.fulfill({ json: { text: "我在练习写字，接下来怎么练？" } }),
  );
  await page.goto("/practice?mode=voice");
  await expect(page.locator("select")).toHaveCount(0);
  const pending = page.waitForResponse((r) => r.url().endsWith("/voice/coach"), { timeout: 30000 });
  await page.getByRole("button", { name: "开始语音陪练" }).click();
  const r = await pending;
  expect(r.status()).toBe(200);
  expect((await r.json()).intent).toBe("VOICE_COACH");
  await expect(page.locator(".direct-conversation p")).toHaveCount(0);
  await page.getByRole("button", { name: "结束语音陪练" }).click();
});

test("旧设备编号失效、worklet失败仍可收音，播放失败读出真实回答且不显示文本", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("xiaoban-input-audio", "disconnected-old-device");
    Object.defineProperty(window, "AudioWorkletNode", { value: function () { throw new Error("WORKLET_UNAVAILABLE"); } });
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = (constraints) => {
      (window as any).requestedAudio = constraints?.audio;
      return original(constraints);
    };
    Object.defineProperty(speechSynthesis, "speak", { value: (speech: SpeechSynthesisUtterance) => {
      (window as any).localReply = speech.text;
      speech.onend?.(new Event("end") as SpeechSynthesisEvent);
    } });
  });
  await page.route("**/api/v1/me", async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...(await response.json()), audio_provider: "test" } });
  });
  let validWav = false;
  await page.route("**/api/v1/audio/transcriptions", (route) => {
    const data = route.request().postDataBuffer()!;
    const start = data.indexOf(Buffer.from("RIFF"));
    const pcm = data.subarray(start + 44, start + 44 + data.readUInt32LE(start + 40));
    validWav = start >= 0 && data.readUInt32LE(start + 24) === 16000 && pcm.some((b) => b !== 0);
    return route.fulfill({ json: { text: "我正在练习写字，请给我一个建议。" } });
  });
  await page.goto("/practice?mode=voice");
  await page.getByRole("button", { name: "开始语音陪练" }).click();
  await expect(page.locator('.voice-input[data-owner="coach"]')).toHaveAttribute("data-engine", "compatible");
  await expect.poll(() => validWav, { timeout: 30000 }).toBeTruthy();
  expect(await page.evaluate(() => (window as any).requestedAudio.deviceId.exact)).toBeUndefined();
  expect(await page.evaluate(() => (window as any).requestedAudio.deviceId.ideal)).toBe("default");
  await expect.poll(() => page.evaluate(() => (window as any).localReply || "")).toContain("我们慢慢来");
  await expect(page.locator(".direct-conversation p")).toHaveCount(0);
  await page.getByRole("button", { name: "结束语音陪练" }).click();
});
