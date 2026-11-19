import { test, expect } from "@playwright/test";
test.use({
  permissions: ["camera"],
  launchOptions: {
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
    ],
  },
});
test("点击才开启摄像头，三帧分析只播报，离页释放摄像头", async ({ page }) => {
  await page.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    (window as any).cameraRequests = 0;
    navigator.mediaDevices.getUserMedia = (constraints) => {
      (window as any).cameraRequests++;
      return original(constraints);
    };
  });
  let frames = 0;
  await page.route("**/api/v1/camera/feedback", async (route) => {
    frames = (
      route
        .request()
        .postDataBuffer()
        ?.toString("latin1")
        .match(/name="files"/g) || []
    ).length;
    await route.fulfill({
      json: { feedback: "请把物品放近一点，我再帮您看看。", frame_count: 3 },
    });
  });
  await page.goto("/practice");
  await expect(page.getByRole("button", { name: "开始视频陪练", exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as any).cameraRequests)).toBe(0);
  await expect(page.locator("select")).toHaveCount(0);
  await page.screenshot({ path: "../../artifacts/ui/practice-idle-mobile-2026-11-19.png" });
  await page.getByRole("button", { name: "开始视频陪练", exact: true }).click();
  await expect
    .poll(() =>
      page
        .locator("video")
        .evaluate(
          (v: HTMLVideoElement) =>
            v.srcObject instanceof MediaStream && v.srcObject.active,
        ),
    )
    .toBeTruthy();
  await expect.poll(() => frames, { timeout: 20000 }).toBe(3);
  await expect(page.getByText("请把物品放近一点，我再帮您看看。")).toHaveCount(0);
  expect(frames).toBe(3);
  await expect(page.locator(".skill-picker")).toHaveCount(0);
  await page.evaluate(() => {
    (window as any).cameraTestStream = (
      document.querySelector("video") as HTMLVideoElement
    ).srcObject;
  });
  await page.screenshot({ path: "../../artifacts/ui/camera-mobile-2026-11-19.png" });
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "首页", exact: true })
    .click();
  await expect
    .poll(() =>
      page.evaluate(() =>
        (window as any).cameraTestStream
          .getTracks()
          .every((t: MediaStreamTrack) => t.readyState === "ended"),
      ),
    )
    .toBeTruthy();
});

test("前后摄像头切换先释放旧轨道，双向发送 facingMode", async ({ page }) => {
  await page.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    (window as any).switchRequests = [];
    (window as any).switchStreams = [];
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      (window as any).switchRequests.push(constraints);
      // Chromium's synthetic camera has no physical facingMode. Exercise the UI request and lifecycle.
      const stream = await original({ ...constraints, video: true });
      (window as any).switchStreams.push(stream);
      return stream;
    };
  });
  await page.goto("/practice");
  await page.getByRole("button", { name: "开始视频陪练", exact: true }).click();
  await page.getByRole("button", { name: "切换前置摄像头" }).click();
  await expect(page.locator("video")).toHaveAttribute("data-facing", "user");
  expect(await page.evaluate(() => (window as any).switchRequests[1].video.facingMode.exact)).toBe("user");
  expect(await page.evaluate(() => (window as any).switchStreams[0].getTracks().every((t: MediaStreamTrack) => t.readyState === "ended"))).toBeTruthy();
  await page.getByRole("button", { name: "切换后置摄像头" }).click();
  await expect(page.locator("video")).toHaveAttribute("data-facing", "environment");
  expect(await page.evaluate(() => (window as any).switchRequests[2].video.facingMode.exact)).toBe("environment");
  await page.getByRole("button", { name: "结束陪练", exact: true }).click();
  await expect(page.getByRole("button", { name: "开始视频陪练", exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as any).switchStreams.every((s: MediaStream) => s.getTracks().every(t => t.readyState === "ended")))).toBeTruthy();
});
