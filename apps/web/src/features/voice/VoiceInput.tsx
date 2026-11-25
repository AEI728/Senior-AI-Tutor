import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { Mic, Square } from "lucide-react";
import { api, friendly } from "../../lib/api";
import { deviceError, stopLocalSpeech, openMicrophone, type AudioOwner } from "./media";
import { audioReport, readAudioReport } from "./diagnostics";

let playback: HTMLAudioElement | null = null;
const captureCancels = new Map<AudioOwner, () => void>();
const activeCaptures = new Set<AudioOwner>();
let playbackOwner: AudioOwner | null = null;
let speechRequest: AbortController | null = null;
export function stopAudio(stopCapture = true, owner?: AudioOwner) {
  if (!owner || owner === playbackOwner) {
    playback?.pause();
    playback = null;
    speechRequest?.abort();
    speechRequest = null;
    playbackOwner = null;
  }
  stopLocalSpeech(owner);
  if (stopCapture) {
    const owners = owner ? [owner] : [...captureCancels.keys()];
    for (const key of owners) {
      captureCancels.get(key)?.();
      window.dispatchEvent(new CustomEvent("xiaoban-audio-stop", { detail: { owner: key } }));
    }
  }
}
function claimAudio(owner: AudioOwner) {
  stopLocalSpeech();
  for (const key of [...captureCancels.keys()]) if (key !== owner) stopAudio(true, key);
  if (playbackOwner && playbackOwner !== owner) stopAudio(false, playbackOwner);
}
export async function speak(replyId: string, rate: number, owner: AudioOwner = "assistant") {
  playback?.pause();
  speechRequest?.abort();
  playbackOwner = owner;
  const controller = new AbortController();
  speechRequest = controller;
  const timeout = setTimeout(() => controller.abort(), 30000);
  let url = "";
  try {
    const r = await fetch("/api/v1/audio/speech", {
      method: "POST",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + sessionStorage.getItem("xiaoban-token"),
      },
      body: JSON.stringify({ reply_id: replyId }),
    });
    if (!r.ok) throw new Error("TTS_UNAVAILABLE");
    url = URL.createObjectURL(await r.blob());
    clearTimeout(timeout);
    const audio = new Audio(url);
    playback = audio;
    audio.playbackRate = rate;
    await new Promise<void>((resolve, reject) => {
      const guard = setTimeout(() => {
        audio.pause();
        reject(new Error("TTS_PLAYBACK_TIMEOUT"));
      }, 90000);
      const done = (error?: Error) => {
        clearTimeout(guard);
        if (error) reject(error);
        else resolve();
      };
      audio.onended = () => done();
      audio.onpause = () => done();
      audio.onerror = () => done(new Error("TTS_PLAYBACK_FAILED"));
      audio.play().catch(done);
    });
  } finally {
    clearTimeout(timeout);
    if (url) URL.revokeObjectURL(url);
    if (speechRequest === controller) { speechRequest = null; playback = null; playbackOwner = null; }
  }
}
export function encodeWav(samples: Float32Array, inputRate: number) {
  let peak = 0;
  for (const sample of samples) peak = Math.max(peak, Math.abs(sample));
  const gain = peak > 0 && peak < 0.08 ? Math.min(8, 0.2 / peak) : 1;
  const rate = 16000,
    length = Math.floor((samples.length * rate) / inputRate),
    buffer = new ArrayBuffer(44 + length * 2),
    view = new DataView(buffer);
  const str = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++)
      view.setUint8(offset + i, s.charCodeAt(i));
  };
  str(0, "RIFF");
  view.setUint32(4, 36 + length * 2, true);
  str(8, "WAVE");
  str(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  str(36, "data");
  view.setUint32(40, length * 2, true);
  for (let i = 0; i < length; i++) {
    const s = Math.max(
      -1,
      Math.min(
        1,
        gain * samples[
          Math.min(samples.length - 1, Math.floor((i * inputRate) / rate))
        ],
      ),
    );
    view.setInt16(44 + i * 2, s < 0 ? s * 32768 : s * 32767, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}
export function selectPcmChannel(channels: Float32Array[]): Float32Array {
  let selected = channels[0] || new Float32Array(0), largest = -1;
  for (const channel of channels) {
    let energy = 0;
    for (const sample of channel) energy += sample * sample;
    if (energy > largest) { largest = energy; selected = channel; }
  }
  return selected;
}
export type VoiceControl = { start: () => void; toggle: () => void; submit: () => void; cancel: () => void };
function within<T>(promise: Promise<T>, ms: number, code: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(code)), ms);
    promise.then(
      (v) => {
        clearTimeout(timer);
        resolve(v);
      },
      (e) => {
        clearTimeout(timer);
        reject(e);
      },
    );
  });
}
export function VoiceInput({
  owner = "assistant",
  onText,
  onError,
  enabled,
  busy = false,
  suspend = false,
  control,
  compact = false,
  onActiveChange,
  holdToTalk = false,
}: {
  owner?: AudioOwner;
  onText: (s: string) => void;
  onError: (s: string) => void;
  enabled: boolean;
  busy?: boolean;
  suspend?: boolean;
  control?: MutableRefObject<VoiceControl | null>;
  compact?: boolean;
  onActiveChange?: (active: boolean) => void;
  holdToTalk?: boolean;
}) {
  const [active, setActive] = useState(false),
    [recording, setRecording] = useState(false),
    [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState(""),
    [level, setLevel] = useState(0),
    [transcript, setTranscript] = useState("");
  const context = useRef<AudioContext | null>(null),
    unlocked = useRef<Promise<void> | null>(null);
  const captureElement = useRef<HTMLDivElement | null>(null);
  const endAfterSubmit = useRef(false);
  const stop = useRef<((send: boolean) => void) | null>(null),
    request = useRef<AbortController | null>(null);
  const generation = useRef(0),
    alive = useRef(true),
    callbacks = useRef({ onText, onError });
  callbacks.current = { onText, onError };
  function cancel() {
    const hadActivity = !!(context.current || request.current || stop.current);
    generation.current++;
    stop.current?.(false);
    request.current?.abort();
    request.current = null;
    const old = context.current;
    context.current = null;
    unlocked.current = null;
    if (old && old.state !== "closed") void old.close().catch(() => {});
    if (hadActivity && readAudioReport(owner)?.phase !== "error") audioReport(owner, { phase: "stopped" });
    if (alive.current) {
      setActive(false);
      setUploading(false);
      setRecording(false);
      setLevel(0);
      if (hadActivity) setStatus("语音已结束");
    }
  }
  useEffect(() => {
    alive.current = true;
    const handler = () => cancel();
    captureCancels.set(owner, handler);
    return () => {
      alive.current = false;
      cancel();
      if (captureCancels.get(owner) === handler) captureCancels.delete(owner);
    };
  }, [owner]);
  useEffect(() => {
    onActiveChange?.(active);
    if (active || busy) activeCaptures.add(owner); else activeCaptures.delete(owner);
    window.dispatchEvent(new CustomEvent("xiaoban-voice-active", { detail: activeCaptures.size > 0 }));
    return () => {
      activeCaptures.delete(owner);
      window.dispatchEvent(new CustomEvent("xiaoban-voice-active", { detail: activeCaptures.size > 0 }));
    };
  }, [active, busy, onActiveChange, owner]);
  useEffect(() => {
    if (suspend) cancel();
  }, [suspend]);
  useEffect(() => {
    window.dispatchEvent(new CustomEvent("xiaoban-input-level", { detail: { owner, level: active && recording ? level : 0 } }));
  }, [active, recording, level, owner]);
  useEffect(() => {
    if (!active || busy || uploading) return;
    let cancelled = false,
      stream: MediaStream | null = null,
      source: MediaStreamAudioSourceNode | null = null;
    let processor: AudioWorkletNode | ScriptProcessorNode | null = null,
      watchdog: ReturnType<typeof setInterval> | undefined;
    let finished = false;
    const turn = generation.current;
    const valid = () => alive.current && turn === generation.current;
    const cleanup = () => {
      clearInterval(watchdog);
      if (processor) {
        if ("port" in processor) processor.port.onmessage = null;
        else processor.onaudioprocess = null;
        processor.disconnect();
      }
      source?.disconnect();
      stream?.getTracks().forEach((t) => t.stop());
    };
    async function begin() {
      try {
        setStatus("正在等待麦克风授权…");
        audioReport(owner, { phase: "permission", samples: 0, peak: 0, characters: 0, code: "", device: "", avoidedDevice: "", channels: undefined });
        if (!navigator.mediaDevices?.getUserMedia)
          throw new Error("MIC_UNSUPPORTED");
        const desktop = !/Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
        const permission = openMicrophone(desktop, valid, label => audioReport(owner, { avoidedDevice: label }));
        // Stop a late-granted stream when the user has already cancelled or timed out.
        permission.then(
          (s) => {
            if (cancelled || finished || !valid())
              s.getTracks().forEach((t) => t.stop());
          },
          () => {},
        );
        stream = await within(permission, 15000, "MIC_PERMISSION_TIMEOUT");
        if (cancelled || !valid()) {
          cleanup();
          return;
        }
        const track = stream.getAudioTracks()[0];
        audioReport(owner, { device: track?.label || "系统默认输入", channels: track?.getSettings().channelCount,
          inputMode: desktop ? "电脑原始输入" : "手机语音输入", trackMuted: track?.muted });
        const audio = context.current;
        if (!audio) throw new Error("MIC_START");
        setStatus("正在开启收音…");
        await within(unlocked.current || audio.resume(), 5000, "MIC_START");
        if (audio.state !== "running") await within(audio.resume(), 5000, "MIC_START");
        try {
          await within(audio.audioWorklet.addModule("/pcm-capture.worklet.js"), 5000, "MIC_START");
          processor = new AudioWorkletNode(audio, "pcm-capture");
        } catch {
          // Compatibility for older mobile WebViews or a failed worklet download.
          processor = audio.createScriptProcessor(2048, 2, 1);
        }
        if (captureElement.current) {
          captureElement.current.dataset.engine = "port" in processor ? "worklet" : "compatible";
          captureElement.current.dataset.samples = "0";
          captureElement.current.dataset.peak = "0";
        }
        audioReport(owner, { phase: "recording", engine: "port" in processor ? "worklet" : "compatible" });
        if (cancelled || !valid()) {
          cleanup();
          return;
        }
        source = audio.createMediaStreamSource(stream);
        const chunks: Float32Array[] = [];
        let heard = false,
          lastVoice = Date.now(),
          lastPacket = Date.now(),
          lastMeter = 0,
          captured = 0,
          peak = 0;
        const started = Date.now(),
          rate = audio.sampleRate;
        const finish = async (send: boolean) => {
          if (finished) return;
          finished = true;
          cleanup();
          if (!valid()) return;
          setRecording(false);
          setLevel(0);
          if (!send) return;
          if (!heard && peak < 0.0001) {
            audioReport(owner, { phase: "error", code: "NO_INPUT_SIGNAL" });
            cancel();
            callbacks.current.onError(
              "没有听到声音，请靠近手机麦克风再说一次，并检查麦克风权限。",
            );
            return;
          }
          const total = chunks.reduce((n, c) => n + c.length, 0),
            samples = new Float32Array(total);
          let offset = 0;
          for (const chunk of chunks) {
            samples.set(chunk, offset);
            offset += chunk.length;
          }
          const controller = new AbortController();
          request.current = controller;
          setUploading(true);
          setStatus("正在识别您说的话…");
          audioReport(owner, { phase: "recognizing", samples: total, peak });
          try {
            const form = new FormData();
            form.append("file", encodeWav(samples, rate), "recording.wav");
            const result = await api(
              "/audio/transcriptions",
              "POST",
              form,
              controller.signal,
            );
            if (!valid() || controller.signal.aborted) return;
            if (!result.text?.trim()) throw new Error("ASR_EMPTY");
            audioReport(owner, { phase: "recognized", characters: result.text.trim().length });
            setTranscript(result.text);
            setStatus("听到了，正在回复您…");
            if (endAfterSubmit.current) {
              setActive(false);
              const old = context.current;
              context.current = null;
              unlocked.current = null;
              if (old && old.state !== "closed") void old.close().catch(() => {});
            }
            callbacks.current.onText(result.text);
          } catch (e) {
            if (valid() && !controller.signal.aborted) {
              cancel();
              audioReport(owner, { phase: "error", code: e instanceof Error ? e.message : "ASR_FAILED" });
              callbacks.current.onError(friendly(e));
            }
          } finally {
            if (request.current === controller) request.current = null;
            if (valid()) setUploading(false);
          }
        };
        stop.current = (send) => {
          void finish(send);
        };
        setRecording(true);
        setStatus(holdToTalk ? "正在听，松开发送" : "正在听，停顿后自动发送");
        watchdog = setInterval(() => {
          const now = Date.now();
          if (now - lastPacket > 3500) {
            void finish(false);
            cancel();
            audioReport(owner, { phase: "error", code: "NO_PCM_PACKETS" });
            callbacks.current.onError(
              "没有收到麦克风声音，请检查输入设备后再试。",
            );
          } else if (
            (!holdToTalk && heard && now - lastVoice > (owner === "coach" ? 1800 : 1200)) ||
            now - started > 19000 ||
            (!holdToTalk && !heard && now - started > 10000)
          )
            void finish(true);
        }, 150);
        const receive = (packet: Float32Array | Float32Array[]) => {
          const data = selectPcmChannel(Array.isArray(packet) ? packet : [packet]);
          chunks.push(data);
          captured += data.length;
          lastPacket = Date.now();
          let sum = 0;
          for (const sample of data) sum += sample * sample;
          const rms = Math.sqrt(sum / data.length);
          peak = Math.max(peak, rms);
          if (rms > 0.003) {
            heard = true;
            lastVoice = Date.now();
          }
          if (Date.now() - lastMeter > 120) {
            setLevel(Math.min(100, Math.round(rms * 900)));
            audioReport(owner, { samples: captured, peak });
            if (captureElement.current) {
              captureElement.current.dataset.samples = String(captured);
              captureElement.current.dataset.peak = String(peak);
            }
            lastMeter = Date.now();
          }
        };
        if ("port" in processor) processor.port.onmessage = (event: MessageEvent<Float32Array | Float32Array[]>) => receive(event.data);
        else processor.onaudioprocess = (event: AudioProcessingEvent) => {
          event.outputBuffer.getChannelData(0).fill(0);
          receive(Array.from({ length: event.inputBuffer.numberOfChannels }, (_, i) => new Float32Array(event.inputBuffer.getChannelData(i))));
        };
        source.connect(processor);
        processor.connect(audio.destination);
      } catch (e) {
        finished = true;
        cleanup();
        if (cancelled || !valid()) return;
        cancel();
        const code = e instanceof Error ? e.message : "";
        audioReport(owner, { phase: "error", code: code || "MIC_START" });
        callbacks.current.onError(
          code === "MIC_PERMISSION_TIMEOUT"
                  ? "还未获得麦克风权限，请在浏览器提示中选择允许，再重新开始。"
                  : code === "MIC_START"
                    ? "收音未能启动，请再次点击麦克风。"
                    : deviceError("audio", e),
        );
      }
    }
    void begin();
    return () => {
      cancelled = true;
      finished = true;
      cleanup();
      stop.current = null;
      setRecording(false);
    };
  }, [active, busy, uploading, owner, holdToTalk]);
  function toggle() {
    if (active) {
      if (recording && stop.current) { endAfterSubmit.current = true; stop.current(true); }
      else stopAudio(true, owner);
      return;
    }
    start();
  }
  function start() {
    if (active || uploading) return;
    if (!enabled) {
      callbacks.current.onError("语音服务未启用，请检查后端配置并刷新页面。");
      return;
    }
    try {
      if (busy) stopAudio(true, owner);
      claimAudio(owner);
      endAfterSubmit.current = holdToTalk;
      window.dispatchEvent(new CustomEvent("xiaoban-voice-start", { detail: { owner } }));
      // Resume inside the click gesture, before awaiting microphone permission.
      const audio = new AudioContext();
      context.current = audio;
      unlocked.current = audio.resume();
      unlocked.current.catch(() => {});
      generation.current++;
      setStatus("正在开启语音…");
      setActive(true);
    } catch {
      cancel();
      callbacks.current.onError(
        "浏览器未能开启收音，请用 Chrome 或 Edge 重试。",
      );
    }
  }
  if (control) control.current = {
    start, toggle,
    submit: () => {
      if (busy || uploading) return;
      endAfterSubmit.current = true;
      if (stop.current) stop.current(true);
      else cancel(); // Release during permission/setup must never start a late recording.
    },
    cancel: () => stopAudio(true, owner),
  };
  return (
    <div ref={captureElement} data-owner={owner} className={"voice-input " + (compact ? "compact-capture" : "")}>
      <button
        type="button"
        className={"voice " + (recording ? "recording" : "")}
        onClick={toggle}
      >
        {active ? <Square size={22} /> : <Mic size={22} />}{" "}
        {active ? "结束语音对话" : "开始语音对话"}
      </button>
      <span role="status" className="voice-status">
        {active && busy ? "小伴正在回复，结束后继续听…" : status}
      </span>
      {recording && (
        <>
          <div
            className="mic-meter"
            role="meter"
            aria-label="麦克风音量"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={level}
          >
            <span style={{ width: Math.max(3, level) + "%" }} />
          </div>
          {owner !== "coach" && <button type="button" onClick={() => stop.current?.(true)}>
            说完了
          </button>}
        </>
      )}
      {!compact && transcript && (
        <p className="privacy-note">刚才听到：{transcript}</p>
      )}
    </div>
  );
}
