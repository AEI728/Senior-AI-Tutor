import { useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { api, friendly } from "./api";

let playback: HTMLAudioElement | null = null;
let captureCancel: (() => void) | null = null;
let speechRequest: AbortController | null = null;
export function stopAudio() {
  playback?.pause();
  playback = null;
  speechRequest?.abort();
  speechRequest = null;
  captureCancel?.();
  captureCancel = null;
  window.speechSynthesis?.cancel();
}
export async function speak(replyId: string, rate: number) {
  playback?.pause();
  speechRequest?.abort();
  speechRequest = new AbortController();
  const r = await fetch("/api/v1/audio/speech", {
    method: "POST",
    signal: speechRequest.signal,
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + sessionStorage.getItem("xiaoban-token"),
    },
    body: JSON.stringify({ reply_id: replyId }),
  });
  if (!r.ok) throw new Error("TTS_UNAVAILABLE");
  const url = URL.createObjectURL(await r.blob());
  const audio = new Audio(url);
  playback = audio;
  audio.playbackRate = rate;
  await new Promise<void>((resolve, reject) => {
    audio.onended = () => {
      URL.revokeObjectURL(url);
      resolve();
    };
    audio.onpause = () => {
      URL.revokeObjectURL(url);
      resolve();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("TTS_PLAYBACK_FAILED"));
    };
    audio.play().catch(reject);
  });
}
export function encodeWav(samples: Float32Array, inputRate: number) {
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
        samples[
          Math.min(samples.length - 1, Math.floor((i * inputRate) / rate))
        ],
      ),
    );
    view.setInt16(44 + i * 2, s < 0 ? s * 32768 : s * 32767, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}
export function VoiceInput({
  onText,
  onError,
  enabled,
  busy = false,
  suspend = false,
}: {
  onText: (s: string) => void;
  onError: (s: string) => void;
  enabled: boolean;
  busy?: boolean;
  suspend?: boolean;
}) {
  const [active, setActive] = useState(false),
    [recording, setRecording] = useState(false),
    [uploading, setUploading] = useState(false);
  const [transcript, setTranscript] = useState(""),
    [correction, setCorrection] = useState("");
  const alive = useRef(true),
    callbacks = useRef({ onText, onError }),
    stop = useRef<((send: boolean) => void) | null>(null);
  callbacks.current = { onText, onError };
  useEffect(() => {
    if (suspend) {
      setActive(false);
      stop.current?.(false);
      callbacks.current.onError(
        "连续两次未能理解，语音已暂停。请使用按钮或文字继续。",
      );
    }
  }, [suspend]);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      stop.current?.(false);
    };
  }, []);
  useEffect(() => {
    if (!active || busy || uploading) return;
    let cancelled = false;
    async function begin() {
      let stream: MediaStream | null = null,
        context: AudioContext | null = null;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true },
          video: false,
        });
        if (cancelled || !alive.current) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        context = new AudioContext();
        await context.resume();
        await context.audioWorklet.addModule("/pcm-capture.worklet.js");
        const source = context.createMediaStreamSource(stream),
          processor = new AudioWorkletNode(context, "pcm-capture");
        source.connect(processor);
        processor.connect(context.destination);
        const chunks: Float32Array[] = [];
        let finished = false,
          heard = false,
          lastVoice = Date.now();
        const started = Date.now();
        const finish = async (send: boolean) => {
          if (finished) return;
          finished = true;
          processor.port.onmessage = null;
          clearInterval(watchdog);
          source.disconnect();
          processor.disconnect();

          stream?.getTracks().forEach((t) => t.stop());
          const rate = context!.sampleRate;
          await context?.close();
          if (!alive.current) return;
          setRecording(false);
          if (!send || !heard) {
            if (send) {
              setActive(false);
              callbacks.current.onError(
                "没有识别到说话，已停止监听。可以重新开始或打字。",
              );
            }
            return;
          }
          const total = chunks.reduce((n, c) => n + c.length, 0),
            samples = new Float32Array(total);
          let offset = 0;
          for (const c of chunks) {
            samples.set(c, offset);
            offset += c.length;
          }
          setUploading(true);
          try {
            const form = new FormData();
            form.append("file", encodeWav(samples, rate), "recording.wav");
            const r = await api("/audio/transcriptions", "POST", form);
            if (alive.current) {
              if (!r.text?.trim()) throw new Error("ASR_EMPTY");
              setTranscript(r.text);
              setCorrection(
                (r.corrections || [])
                  .map(
                    (c: { heard: string; catalog_term: string }) =>
                      c.heard + " → " + c.catalog_term,
                  )
                  .join("、"),
              );
              callbacks.current.onText(r.text);
            }
          } catch (e) {
            if (alive.current) {
              setActive(false);
              callbacks.current.onError(friendly(e));
            }
          } finally {
            if (alive.current) setUploading(false);
          }
        };
        stop.current = (send) => {
          void finish(send);
        };
        captureCancel = () => {
          void finish(false);
        };
        setRecording(true);
        const watchdog = setInterval(() => {
          if (
            (heard && Date.now() - lastVoice > 1100) ||
            Date.now() - started > 19000 ||
            (!heard && Date.now() - started > 8000)
          )
            void finish(true);
        }, 150);
        processor.port.onmessage = (e: MessageEvent<Float32Array>) => {
          const data = e.data;
          chunks.push(data);
          let sum = 0;
          for (const s of data) sum += s * s;
          if (Math.sqrt(sum / data.length) > 0.014) {
            heard = true;
            lastVoice = Date.now();
          }
        };
      } catch (e) {
        stream?.getTracks().forEach((t) => t.stop());
        void context?.close();
        if (alive.current) {
          setActive(false);
          setRecording(false);
          callbacks.current.onError(
            e instanceof DOMException && e.name === "NotAllowedError"
              ? "麦克风未获授权，可以继续打字。"
              : "无法使用麦克风，请使用文字输入。",
          );
        }
      }
    }
    void begin();
    return () => {
      cancelled = true;
      stop.current?.(false);
    };
  }, [active, busy, uploading]);
  function toggle() {
    if (active) {
      setActive(false);
      stop.current?.(false);
    } else if (!enabled) onError("当前为模拟语音模式，请使用文字输入。");
    else setActive(true);
  }
  return (
    <div>
      <button
        type="button"
        className={"voice " + (recording ? "recording" : "")}
        onClick={toggle}
      >
        {active ? <Square size={22} /> : <Mic size={22} />}{" "}
        {active ? "结束语音对话" : "开始语音对话"}
      </button>
      <span role="status" className="voice-status">
        {recording
          ? " 正在听，停顿后自动发送"
          : uploading
            ? " 正在识别"
            : active
              ? " 处理完成后继续听"
              : ""}
      </span>
      {recording && (
        <button type="button" onClick={() => stop.current?.(true)}>
          说完了
        </button>
      )}
      {transcript && <p className="privacy-note">刚才听到：{transcript}</p>}
      {correction && (
        <p className="privacy-note">按现有课程目录纠正同音词：{correction}</p>
      )}
    </div>
  );
}
