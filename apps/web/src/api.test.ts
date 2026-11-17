import { describe, expect, it } from "vitest";
import { friendly } from "./api";
describe("恢复提示", () => {
  it("权限失败有重新登录入口", () =>
    expect(friendly(new Error("AUTH_REQUIRED"))).toContain("重新登录"));
  it("语音失败可转文字", () =>
    expect(friendly(new Error("ASR_UNAVAILABLE"))).toContain("打字"));
});
