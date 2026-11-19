import { test, expect } from "@playwright/test";
import path from "node:path";

test.use({ launchOptions: { args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--use-file-for-fake-audio-capture=" + path.resolve(import.meta.dirname, "fixtures/user-command.wav") + "%noloop"] } });

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(speechSynthesis, "speak", { value: (speech: SpeechSynthesisUtterance) => {
      (window as any).spokenReplies ??= [];
      (window as any).spokenReplies.push(speech.text);
      speech.onend?.(new Event("end") as SpeechSynthesisEvent);
    } });
  });
  await page.route("**/api/v1/me", async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...(await response.json()), audio_provider: "test" } });
  });
});

test("陪练页面点击助手仍执行页面操作，第二次点击提交录音而非丢弃", async ({ page }) => {
  let agents = 0, coaches = 0, wavHasSignal = false;
  await page.route("**/api/v1/audio/transcriptions", (route) => {
    const data = route.request().postDataBuffer()!, start = data.indexOf(Buffer.from("RIFF"));
    const pcm = data.subarray(start + 44, start + 44 + data.readUInt32LE(start + 40));
    wavHasSignal = pcm.some(b => b !== 0);
    return route.fulfill({ json: { text: "打开技能广场" } });
  });
  page.on("request", r => {
    if (r.url().endsWith("/agent/turns")) agents++;
    if (r.url().endsWith("/voice/coach")) coaches++;
  });
  await page.goto("/practice?mode=voice");
  const mic = page.getByRole("button", { name: "小伴语音助手" });
  await mic.click();
  const capture = page.locator('.voice-input[data-owner="assistant"]');
  await expect.poll(() => capture.getAttribute("data-peak").then(Number)).toBeGreaterThan(0.001);
  await expect(page.getByRole("button", { name: "开始语音陪练", exact: true })).toBeVisible();
  await expect(page.locator('.voice-input[data-owner="coach"] button.recording')).toHaveCount(0);
  const recognized = page.waitForResponse(r => r.url().endsWith("/audio/transcriptions"));
  await mic.click();
  expect((await recognized).status()).toBe(200);
  await expect(page).toHaveURL(/\/skills$/);
  expect(wavHasSignal).toBeTruthy();
  expect(agents).toBe(1); expect(coaches).toBe(0);
  await expect.poll(() => page.evaluate(() => JSON.parse(sessionStorage.getItem("xiaoban-audio-report-assistant") || "{}").characters || 0)).toBeGreaterThan(0);
  await expect(page.locator(".direct-conversation .reply")).toHaveCount(0);
});

test("语音进入陪练只导航，不自动打开摄像头或陪练录音", async ({ page }) => {
  await page.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    (window as any).mediaRequests = [];
    navigator.mediaDevices.getUserMedia = (constraints) => {
      (window as any).mediaRequests.push(constraints);
      return original(constraints);
    };
  });
  await page.route("**/api/v1/audio/transcriptions", route => route.fulfill({ json: { text: "打开陪练" } }));
  await page.goto("/");
  const mic = page.getByRole("button", { name: "小伴语音助手" });
  await mic.click();
  const capture = page.locator('.voice-input[data-owner="assistant"]');
  await expect.poll(() => capture.getAttribute("data-peak").then(Number)).toBeGreaterThan(0.001);
  await mic.click();
  await expect(page).toHaveURL(/\/practice$/);
  await expect(page.getByRole("button", { name: "开始视频陪练", exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as any).mediaRequests.some((c: MediaStreamConstraints) => c.video))).toBe(false);
  await expect(page.locator('.voice-input[data-owner="coach"] button.recording')).toHaveCount(0);
  await expect(page.locator('.direct-conversation .reply')).toHaveCount(0);
});

test("陪练有自己的录音和接口，页面操作词也不走助手", async ({ page }) => {
  let agents = 0, coaches = 0;
  await page.route("**/api/v1/audio/transcriptions", r => r.fulfill({ json: { text: "打开首页" } }));
  page.on("request", r => {
    if (r.url().endsWith("/agent/turns")) agents++;
    if (r.url().endsWith("/voice/coach")) { coaches++; expect(r.postDataJSON().agent_role).toBe("tutor"); }
  });
  await page.goto("/practice?mode=voice");
  await page.getByRole("button", { name: "开始语音陪练", exact: true }).click();
  const coachCapture = page.locator('.voice-input[data-owner="coach"]');
  await expect.poll(() => coachCapture.getAttribute("data-peak").then(Number)).toBeGreaterThan(0.001);
  await expect(page.getByRole("button", { name: "小伴语音助手" })).toHaveAttribute("aria-pressed", "false");
  const answer = page.waitForResponse(r => r.url().endsWith("/voice/coach"));
  await expect(page.locator(".voice-practice").getByRole("button", { name: "说完了", exact: true, includeHidden: true })).toHaveCount(0);
  expect((await answer).status()).toBe(200);
  await expect.poll(() => coaches).toBe(1); expect(agents).toBe(0);
  await expect(page).toHaveURL(/\/practice\?mode=voice$/);
  await expect(page.getByText("我们慢慢来。您想练习什么？告诉我现在做到哪一步了。", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "结束语音陪练", exact: true }).click();
  await expect(page.getByRole("button", { name: "开始语音陪练", exact: true })).toBeVisible();
});

test("切换到助手会结束陪练收音并丢弃迟到的陪练回复", async ({ page }) => {
  let release: () => void = () => {};
  let requested = false;
  await page.route("**/api/v1/audio/transcriptions", r => r.fulfill({ json: { text: "练习写字" } }));
  await page.route("**/api/v1/voice/coach", async (route) => {
    requested = true;
    await new Promise<void>(resolve => { release = resolve; });
    await route.fulfill({ json: { reply: { id: "late-coach", speech_text: "迟到的陪练回复" }, ui_actions: [] } }).catch(() => {});
  });
  const ttsIds: string[] = [];
  page.on("request", r => { if (r.url().endsWith("/audio/speech")) ttsIds.push(r.postDataJSON().reply_id); });
  await page.goto("/practice?mode=voice");
  await page.getByRole("button", { name: "开始语音陪练", exact: true }).click();
  await expect.poll(() => page.locator('.voice-input[data-owner="coach"]').getAttribute("data-peak").then(Number)).toBeGreaterThan(0.001);
  await expect(page.locator(".voice-practice").getByRole("button", { name: "说完了", exact: true, includeHidden: true })).toHaveCount(0);
  await expect.poll(() => requested).toBeTruthy();
  await page.getByRole("button", { name: "小伴语音助手" }).click();
  await expect(page.getByRole("button", { name: "开始语音陪练", exact: true })).toBeVisible();
  await expect(page.locator('.voice-input[data-owner="coach"] button.recording')).toHaveCount(0);
  release();
  await expect(page.locator('.voice-input[data-owner="assistant"] button.recording')).toHaveCount(1);
  expect(ttsIds).not.toContain("late-coach");
  expect(await page.evaluate(() => (window as any).spokenReplies || [])).not.toContain("迟到的陪练回复");
});

for (const engine of ["worklet", "compatible"]) {
  test(`电脑麦克风仅右声道有声仍可提交识别：${engine}`, async ({ page }) => {
    await page.addInitScript((mode) => {
      if (mode === "compatible") Object.defineProperty(window, "AudioWorkletNode", { value: function () { throw new Error("WORKLET_UNAVAILABLE"); } });
      navigator.mediaDevices.getUserMedia = async () => {
        const context = new AudioContext();
        await context.resume();
        const right = context.createOscillator(), volume = context.createGain();
        right.frequency.value = 260; volume.gain.value = 0.15;
        const silent = context.createConstantSource(), stereo = context.createChannelMerger(2);
        silent.offset.value = 0;
        silent.connect(stereo, 0, 0);
        right.connect(volume); volume.connect(stereo, 0, 1);
        const destination = context.createMediaStreamDestination();
        destination.channelCount = 2; destination.channelCountMode = "explicit";
        stereo.connect(destination); silent.start(); right.start();
        const stream = destination.stream, track = stream.getAudioTracks()[0], stop = track.stop.bind(track);
        track.stop = () => { stop(); void context.close(); };
        return stream;
      };
    }, engine);
    let signal = false;
    await page.route("**/api/v1/audio/transcriptions", (route) => {
      const data = route.request().postDataBuffer()!, start = data.indexOf(Buffer.from("RIFF"));
      const pcm = data.subarray(start + 44, start + 44 + data.readUInt32LE(start + 40));
      signal = pcm.some(b => b !== 0);
      return route.fulfill({ json: { text: "打开技能广场" } });
    });
    await page.goto("/");
    const mic = page.getByRole("button", { name: "小伴语音助手" });
    await mic.click();
    const capture = page.locator('.voice-input[data-owner="assistant"]');
    await expect(capture).toHaveAttribute("data-engine", engine);
    await expect.poll(() => capture.getAttribute("data-peak").then(Number)).toBeGreaterThan(0.01);
    await mic.click();
    await expect.poll(() => signal).toBeTruthy();
    await expect(page).toHaveURL(/\/skills$/);
  });
}

test("浏览器返回网易虚拟输入时自动重新连接 Realtek 实体麦克风", async ({ page }) => {
  await page.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    (window as any).micRequests = []; (window as any).micStreams = [];
    navigator.mediaDevices.enumerateDevices = async () => [
      { kind: "audioinput", deviceId: "default", label: "默认 - 麦克风阵列 (Realtek(R) Audio)" },
      { kind: "audioinput", deviceId: "communications", label: "通讯 - 麦克风阵列 (网易虚拟音频设备)" },
      { kind: "audioinput", deviceId: "virtual-device", label: "麦克风阵列 (网易虚拟音频设备)" },
      { kind: "audioinput", deviceId: "realtek-device", label: "麦克风阵列 (Realtek(R) Audio)" },
    ] as MediaDeviceInfo[];
    navigator.mediaDevices.getUserMedia = async constraints => {
      (window as any).micRequests.push(constraints);
      const physical = (constraints?.audio as MediaTrackConstraints)?.deviceId as ConstrainDOMStringParameters;
      const stream = await original({ audio: true });
      Object.defineProperty(stream.getAudioTracks()[0], "label", { value: physical?.exact === "realtek-device" ? "麦克风阵列 (Realtek(R) Audio)" : "麦克风阵列 (网易虚拟音频设备)" });
      (window as any).micStreams.push(stream);
      return stream;
    };
  });
  await page.route("**/api/v1/audio/transcriptions", route => route.fulfill({ json: { text: "打开技能广场" } }));
  await page.goto("/");
  const mic = page.getByRole("button", { name: "小伴语音助手" });
  await mic.click();
  const capture = page.locator('.voice-input[data-owner="assistant"]');
  await expect.poll(() => capture.getAttribute("data-peak").then(Number)).toBeGreaterThan(0.001);
  expect(await page.evaluate(() => (window as any).micRequests[1].audio.deviceId.exact)).toBe("realtek-device");
  expect(await page.evaluate(() => (window as any).micStreams[0].getTracks().every((t: MediaStreamTrack) => t.readyState === "ended"))).toBeTruthy();
  const report = await page.evaluate(() => JSON.parse(sessionStorage.getItem("xiaoban-audio-report-assistant") || "{}"));
  expect(report.device).toContain("Realtek"); expect(report.avoidedDevice).toContain("网易");
  await mic.click();
  await expect(page).toHaveURL(/\/skills$/);
});
