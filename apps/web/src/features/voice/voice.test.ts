import { describe, it, expect } from "vitest";
import { encodeWav, selectPcmChannel } from "./VoiceInput";
import { physicalMicrophone } from "./media";
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
describe("电脑多声道录音", () => {
  it("系统默认是虚拟设备时选择实体麦克风，不保留旧设备编号", () => {
    const devices = [
      { deviceId: "default", kind: "audioinput", label: "默认 - 麦克风阵列 (网易虚拟音频设备)" },
      { deviceId: "virtual", kind: "audioinput", label: "麦克风阵列 (网易虚拟音频设备)" },
      { deviceId: "physical", kind: "audioinput", label: "麦克风阵列 (Realtek Audio)" },
    ] as MediaDeviceInfo[];
    expect(physicalMicrophone(devices)?.deviceId).toBe("physical");
  });
  it("左声道静音时保留右声道语音", () => {
    expect([...selectPcmChannel([new Float32Array(3), new Float32Array([0.2, -0.3, 0.1])])]).toEqual([...new Float32Array([0.2, -0.3, 0.1])]);
  });
  it("相位相反的声道不会相加抵消成静音", () => {
    const result = selectPcmChannel([new Float32Array([0.4, -0.4]), new Float32Array([-0.4, 0.4])]);
    expect(result.some(sample => Math.abs(sample) > 0.3)).toBeTruthy();
  });
});
