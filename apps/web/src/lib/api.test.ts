import { describe, expect, it } from "vitest";
import { friendly } from "./api";
describe("恢复提示", () => {
  it("会话失效提示刷新恢复", () =>
    expect(friendly(new Error("AUTH_REQUIRED"))).toContain("刷新页面"));
  it("语音失败提示重试", () =>
    expect(friendly(new Error("ASR_UNAVAILABLE"))).toContain("识别服务"));
});
