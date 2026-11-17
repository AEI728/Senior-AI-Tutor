import { describe, it, expect } from "vitest";
import { encodeWav } from "./voice";
describe("WAV录音编码", () => {
  it("输出16kHz单声道PCM16并正确写入时长", async () => {
    const blob = encodeWav(new Float32Array(48000), 48000),
      data = new DataView(await blob.arrayBuffer());
    expect(data.getUint32(24, true)).toBe(16000);
    expect(data.getUint16(22, true)).toBe(1);
    expect(data.getUint16(34, true)).toBe(16);
    expect(data.getUint32(40, true)).toBe(32000);
    expect(blob.size).toBe(32044);
  });
});
