import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/me", async route => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...await response.json(), audio_provider: "test" } });
  });
  await page.addInitScript(() => {
    (window as any).holdStreams = [];
    navigator.mediaDevices.getUserMedia = async () => {
      if ((window as any).delayPermission) await new Promise(resolve => { (window as any).grantMic = resolve; });
      const audio = new AudioContext();
      await audio.resume();
      const oscillator = audio.createOscillator(), volume = audio.createGain();
      const output = audio.createMediaStreamDestination();
      volume.gain.setValueAtTime(0.1, audio.currentTime);
      volume.gain.setValueAtTime(0, audio.currentTime + 0.7);
      oscillator.connect(volume).connect(output);
      oscillator.start();
      const track = output.stream.getTracks()[0], stop = track.stop.bind(track);
      track.stop = () => { stop(); void audio.close(); };
      (window as any).holdStreams.push(output.stream);
      return output.stream;
    };
    Object.defineProperty(speechSynthesis, "speak", { value: (speech: SpeechSynthesisUtterance) => speech.onend?.(new Event("end") as SpeechSynthesisEvent) });
  });
});

test("按住保持红色且停顿不提交，移出按钮松手仍只提交一次，思考禁用", async ({ page }) => {
  let submissions = 0, release = () => {};
  await page.route("**/api/v1/audio/transcriptions", route => { submissions++; return route.fulfill({ json: { text: "你好" } }); });
  await page.route("**/api/v1/agent/turns", async route => {
    await new Promise<void>(resolve => { release = resolve; });
    await route.fulfill({ status: 503, json: { error: { code: "PROVIDER_UNAVAILABLE" } } });
  });
  await page.goto("/");
  const mic = page.getByRole("button", { name: "小伴语音助手" });
  await expect(mic).toHaveCSS("background-color", "rgb(47, 73, 66)");
  await mic.hover(); await page.mouse.down();
  await expect(mic).toHaveCSS("background-color", "rgb(166, 60, 50)");
  await expect.poll(() => page.locator('.voice-input[data-owner="assistant"]').getAttribute("data-samples").then(Number)).toBeGreaterThan(120000);
  expect(submissions).toBe(0);
  await page.mouse.move(10, 10); await page.mouse.up();
  await expect(mic).toBeDisabled();
  await expect(mic.locator(".mic-waiting-spinner")).toBeVisible();
  expect(submissions).toBe(1);
  release();
  await expect(mic).toBeEnabled();
  await expect(mic).toHaveCSS("background-color", "rgb(47, 73, 66)");
});

test("授权前松手会取消，迟到的授权不继续收音或提交", async ({ page }) => {
  let submissions = 0;
  await page.route("**/api/v1/audio/transcriptions", route => { submissions++; return route.fulfill({ json: { text: "你好" } }); });
  await page.goto("/");
  await page.evaluate(() => { (window as any).delayPermission = true; });
  const mic = page.getByRole("button", { name: "小伴语音助手" });
  await mic.hover(); await page.mouse.down();
  await page.waitForFunction(() => !!(window as any).grantMic);
  await page.mouse.up();
  await page.evaluate(() => { (window as any).grantMic(); });
  await expect.poll(() => page.evaluate(() => (window as any).holdStreams.length)).toBe(1);
  await expect.poll(() => page.evaluate(() => (window as any).holdStreams[0].getTracks().every((track: MediaStreamTrack) => track.readyState === "ended"))).toBe(true);
  expect(submissions).toBe(0);
  await expect(mic).toHaveAttribute("aria-pressed", "false");
  await expect(mic).toBeEnabled();
});
