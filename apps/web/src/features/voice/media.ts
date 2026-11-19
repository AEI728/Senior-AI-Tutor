const virtualInput = /虚拟|virtual|网易|loopback|立体声混音|stereo mix|voicemeeter|vb.audio|cable (input|output)|blackhole|obs/i;
export function physicalMicrophone(devices: MediaDeviceInfo[]) {
  const candidates = devices.filter(d => d.kind === "audioinput" && d.label && !["default", "communications"].includes(d.deviceId) && !virtualInput.test(d.label));
  const communications = devices.find(d => d.deviceId === "communications" && !virtualInput.test(d.label));
  return candidates.find(d => communications?.label.includes(d.label)) || candidates[0];
}
export async function openMicrophone(desktop: boolean, current: () => boolean, avoided: (label: string) => void): Promise<MediaStream> {
  const devices = navigator.mediaDevices;
  const constraints: MediaTrackConstraints = { channelCount: { ideal: desktop ? 2 : 1 }, echoCancellation: !desktop, noiseSuppression: !desktop, autoGainControl: true };
  async function open(id?: string) {
    if (!current()) throw new DOMException("Capture cancelled", "AbortError");
    return devices.getUserMedia({ audio: { ...constraints, ...(id ? { deviceId: { exact: id } } : desktop ? { deviceId: { ideal: "default" } } : {}) }, video: false });
  }
  if (desktop) {
    const known = await devices.enumerateDevices().catch(() => [] as MediaDeviceInfo[]);
    const selected = known.find(d => d.deviceId === "default");
    const physical = physicalMicrophone(known);
    if (selected && virtualInput.test(selected.label) && physical) { avoided(selected.label); return open(physical.deviceId); }
  }
  const stream = await open();
  if (!desktop || !virtualInput.test(stream.getAudioTracks()[0]?.label || "")) return stream;
  try {
    const physical = physicalMicrophone(await devices.enumerateDevices());
    if (!physical) return stream;
    avoided(stream.getAudioTracks()[0].label);
    stream.getTracks().forEach(t => t.stop());
    return await open(physical.deviceId);
  } catch (error) { stream.getTracks().forEach(t => t.stop()); throw error; }
}

export function deviceError(kind: "audio" | "video", error: unknown) {
  const name = kind === "audio" ? "麦克风" : "摄像头";
  const code = error instanceof Error ? error.name : "";
  if (!window.isSecureContext || !navigator.mediaDevices) return "请用 localhost 或 HTTPS 地址打开项目。";
  if (code === "NotAllowedError" || code === "SecurityError") return name + "未获授权。请在系统或浏览器设置中允许使用后重试。";
  if (code === "NotFoundError") return "没有找到" + name + "，请连接设备后重试。";
  if (code === "NotReadableError") return name + "无法读取，请检查系统权限，并关闭占用设备的其他应用。";
  if (code === "OverconstrainedError") return "当前设备不支持这侧摄像头，请使用原来的摄像头。";
  if (error instanceof Error && error.message === "DEVICE_TIMEOUT") return "请在浏览器提示中允许" + name + "，然后重试。";
  return name + "启动失败，请检查系统权限后重试。";
}

export type AudioOwner = "assistant" | "coach" | "camera";
let localOwner: AudioOwner | null = null;
let cancelLocal: (() => void) | null = null;
export function stopLocalSpeech(owner?: AudioOwner) {
  if (owner && localOwner !== owner) return;
  cancelLocal?.();
}
export function sayLocal(text: string, rate = 1, owner: AudioOwner = "assistant"): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!text?.trim()) { reject(new Error("EMPTY_SPEECH")); return; }
    if (!window.speechSynthesis) { reject(new Error("LOCAL_SPEECH_UNAVAILABLE")); return; }
    stopLocalSpeech();
    speechSynthesis.cancel();
    localOwner = owner;
    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = "zh-CN"; speech.rate = rate;
    const voice = speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith("zh"));
    if (voice) speech.voice = voice;
    const settle = (error?: Error) => {
      clearTimeout(timer);
      if (cancelLocal === cancel) { cancelLocal = null; localOwner = null; }
      if (error) reject(error); else resolve();
    };
    const cancel = () => { speechSynthesis.cancel(); settle(); };
    const timer = setTimeout(() => { speechSynthesis.cancel(); settle(new Error("LOCAL_SPEECH_TIMEOUT")); }, 60000);
    cancelLocal = cancel;
    speech.onend = () => settle();
    speech.onerror = () => settle(new Error("LOCAL_SPEECH_FAILED"));
    speechSynthesis.speak(speech);
  });
}
