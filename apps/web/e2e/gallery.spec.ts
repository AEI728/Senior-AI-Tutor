import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
test("历史作品方块卡、全屏查看、上传按钮仅我的列表右下角", async ({
  page,
  request,
}) => {
  const auth = await request.post("/api/v1/auth/register", {
    data: {
      username: "gallery_" + Date.now(),
      password: "gallery-test-123456",
    },
  });
  const { access_token } = await auth.json();
  const headers = { Authorization: "Bearer " + access_token };
  for (const [title, kind, file, type] of [
    ["我的视频", "video", "../../media/repotting-basics.mp4", "video/mp4"],
    ["我的照片", "image", "public/images/calligraphy.jpg", "image/jpeg"],
  ]) {
    const created = await request.post("/api/v1/community/works", {
      headers,
      data: {
        title,
        description: "学习记录",
        course_id: "repotting-basics",
        publish_confirmation: "SHARE_THIS_WORK",
      },
    });
    const w = await created.json();
    expect(
      (
        await request.put("/api/v1/community/works/" + w.id + "/" + kind, {
          headers,
          multipart: {
            file: {
              name: path.basename(file),
              mimeType: type,
              buffer: fs.readFileSync(path.resolve(file)),
            },
          },
        })
      ).ok(),
    ).toBeTruthy();
  }
  await page.addInitScript(
    (t) => sessionStorage.setItem("xiaoban-token", t),
    access_token,
  );
  await page.goto("/share");
  await expect(
    page.getByRole("button", { name: "上传", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "我的", exact: true }).click();
  await expect(page.locator(".my-work-card")).toHaveCount(2);
  const box = await page.locator(".my-work-card").first().boundingBox();
  expect(Math.abs(box!.width - box!.height)).toBeLessThan(2);
  await expect(page.locator(".my-work-card img")).toHaveCount(2);
  await expect.poll(() => page.locator(".my-work-card img").evaluateAll(
    (images) => images.every((img) => (img as HTMLImageElement).naturalWidth > 0),
  )).toBeTruthy();
  const upload = page.getByRole("button", { name: "上传", exact: true });
  await expect(upload).toBeVisible();
  const button = await upload.boundingBox();
  expect(button!.x).toBeGreaterThan(200);
  expect(button!.y).toBeGreaterThan(600);
  await page.screenshot({ path: "../../artifacts/ui/my-gallery.png" });
  await page.getByRole("button", { name: "查看作品：我的视频" }).click();
  await expect(
    page.getByRole("dialog", { name: "查看作品" }).locator("video"),
  ).toBeVisible();
  await expect(upload).toHaveCount(0);
  await expect.poll(() => page.getByRole("dialog", { name: "查看作品" }).locator("video").evaluate(
    (video) => (video as HTMLVideoElement).readyState,
  )).toBeGreaterThanOrEqual(2);
  await expect.poll(() => page.getByRole("dialog", { name: "查看作品" }).locator("video").evaluate(
    (video) => (video as HTMLVideoElement).currentTime,
  )).toBeGreaterThan(0.5);
  await page.screenshot({ path: "../../artifacts/ui/my-work-fullscreen.png" });
  await page.getByRole("button", { name: "返回我的作品" }).click();
  await expect(upload).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "我的", exact: true }).click();
  await expect(page.locator(".my-work-card")).toHaveCount(2);
  await request.delete("/api/v1/me/data", {
    headers,
    data: { confirmation: "DELETE_MY_DATA" },
  });
});
test("精简首页、字号仅首页、返回图标和三节教程", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "放大字号" })).toBeVisible();
  await expect(page.locator(".featured-copy")).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "进入技能广场", exact: true }),
  ).toHaveCount(0);
  await page.locator(".featured-skill").click();
  await expect(
    page.getByRole("link", { name: "返回首页" }).locator("svg"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "放大字号" })).toBeHidden();
  await page.getByRole("link", { name: "返回首页" }).click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "技能广场", exact: true })
    .click();
  await page.locator(".plaza-skill").first().click();
  await expect(page.locator(".lesson-row")).toHaveCount(3);
  await expect(page.getByText("把平常日子，拍出一点光")).toHaveCount(0);
  await page.locator(".lesson-row").nth(1).click();
  await expect(
    page.getByRole("dialog", { name: "课程学习" }).locator("video"),
  ).toBeVisible();
  await page.screenshot({ path: "../../artifacts/ui/multiple-lessons.png" });
});
