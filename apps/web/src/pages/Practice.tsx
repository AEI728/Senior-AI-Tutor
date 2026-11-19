import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Video, Square, Mic, SwitchCamera } from "lucide-react";
import { api, friendly, newId } from "../lib/api";
import { speak, stopAudio, VoiceInput, type VoiceControl } from "../features/voice/VoiceInput";
import { useLearning } from "../features/learning/LearningProvider";
import { audioReport } from "../features/voice/diagnostics";
import { deviceError, sayLocal } from "../features/voice/media";
export function CameraPractice() {
  const { sessionId } = useParams();
  const video = useRef<HTMLVideoElement | null>(null),
    stream = useRef<MediaStream | null>(null),
    request = useRef<AbortController | null>(null),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null),
    generation = useRef(0),
    voice = useRef(false);
  const [active, setActive] = useState(false),
    [starting, setStarting] = useState(false),
    [facing, setFacing] = useState<"user" | "environment">("environment"),
    [status, setStatus] = useState(""),
    [error, setError] = useState("");
  function stop() {
    generation.current++;
    if (timer.current) clearTimeout(timer.current);
    request.current?.abort();
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (video.current) video.current.srcObject = null;
    stopAudio(false, "camera");
    setActive(false);
    setStarting(false);
    setStatus("");
  }
  async function acknowledge() {
    const aid = sessionStorage.getItem("practice-action");
    if (!aid || !sessionId) return;
    await api("/practice/sessions/" + sessionId + "/commands", "POST", { command: "START" });
    await api("/agent/ui-actions/" + aid + "/ack", "POST", { result: "applied", error_code: null });
    sessionStorage.removeItem("practice-action");
  }
  async function start(nextFacing = facing, switching = false) {
    stop();
    const turn = generation.current;
    setError("");
    setStarting(true);
    setStatus("请允许使用摄像头");
    let timedOut = false;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("MEDIA_UNAVAILABLE");
      const pending = navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: switching ? { exact: nextFacing } : { ideal: nextFacing },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      pending.then(
        (s) => {
          if (turn !== generation.current || timedOut)
            s.getTracks().forEach((t) => t.stop());
        },
        () => {},
      );
      let timeout: ReturnType<typeof setTimeout> | undefined;
      const s = await Promise.race([pending, new Promise<MediaStream>((_, reject) => {
        timeout = setTimeout(() => { timedOut = true; reject(new Error("DEVICE_TIMEOUT")); }, 15000);
      })]).finally(() => clearTimeout(timeout));
      if (turn !== generation.current) return;
      stream.current = s;
      setFacing(nextFacing);
      setActive(true);
      setStatus("正在观察");
      if (video.current) {
        video.current.srcObject = s;
        await video.current.play();
      }
      if (turn !== generation.current) return;
      setStarting(false);
      void acknowledge().catch(() => {});
      const frames: Blob[] = [];
      let previous = "";
      async function tick() {
        if (turn !== generation.current) return;
        try {
          const v = video.current;
          if (v && v.readyState >= 2) {
            const canvas = document.createElement("canvas"),
              scale = Math.min(1, 960 / v.videoWidth);
            canvas.width = v.videoWidth * scale;
            canvas.height = v.videoHeight * scale;
            canvas
              .getContext("2d")!
              .drawImage(v, 0, 0, canvas.width, canvas.height);
            const frame = await new Promise<Blob | null>((resolve) =>
              canvas.toBlob(resolve, "image/jpeg", 0.7),
            );
            if (frame) {
              frames.push(frame);
              if (frames.length > 3) frames.shift();
            }
          }
          if (frames.length === 3) {
            const form = new FormData();
            frames.forEach((frame, i) =>
              form.append("files", frame, `frame-${i}.jpg`),
            );
            form.append("previous_feedback", previous);
            const controller = new AbortController();
            request.current = controller;
            setStatus("小伴正在看您的操作…");
            const result = await api(
              "/camera/feedback",
              "POST",
              form,
              controller.signal,
            );
            if (turn !== generation.current) return;
            previous = result.feedback;
            setStatus("正在观察");
            if (!voice.current && result.reply_id) {
              try {
                await speak(result.reply_id, 1, "camera");
              } catch {
                if (turn !== generation.current) return;
                try { await sayLocal(result.feedback, 1, "camera"); }
                catch { setError("请检查浏览器声音权限和扬声器。"); }
              }
            }
            frames.splice(0, frames.length);
          }
        } catch (e) {
          if (turn === generation.current) {
            setError(friendly(e));
            setStatus("观察暂停");
            return;
          }
        }
        if (turn === generation.current)
          timer.current = setTimeout(
            () => void tick(),
            frames.length ? 2000 : 6000,
          );
      }
      timer.current = setTimeout(() => void tick(), 1000);
    } catch (e) {
      if (turn !== generation.current) return;
      generation.current++;
      stream.current?.getTracks().forEach((t) => t.stop());
      stream.current = null;
      if (video.current) video.current.srcObject = null;
      setActive(false);
      setStarting(false);
      setStatus("摄像头未开启");
      const message = switching && e instanceof Error && e.name === "OverconstrainedError"
        ? "当前设备无法切换到另一侧摄像头。"
        : deviceError("video", e);
      setError(message);
      void sayLocal(message, 1, "camera").catch(() => {});
    }
  }
  useEffect(() => {
    const listener = (e: Event) => {
      voice.current = (e as CustomEvent).detail;
      if (voice.current) stopAudio(false, "camera");
    };
    window.addEventListener("xiaoban-voice-active", listener);
    const visibility = () => {
      if (document.hidden) stop();
    };
    document.addEventListener("visibilitychange", visibility);
    return () => {
      stop();
      window.removeEventListener("xiaoban-voice-active", listener);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  return (
    <div className={"camera-practice " + (active ? "is-running" : "is-idle")} data-page="practice">
      <video ref={video} hidden={!active} data-facing={facing} autoPlay muted playsInline aria-label="摄像头预览" />
      {!active && <div className="practice-idle">
        <div className={"practice-orb " + (starting ? "is-connecting" : "")}><Video size={50} strokeWidth={1.6} /></div>
        <h1>视频陪练</h1>
        <button className="practice-start" disabled={starting} onClick={() => void start()}>
          {starting ? "正在开启…" : "开始视频陪练"}
        </button>
      </div>}
      {active && <div className="camera-status" role="status">
        {status}
      </div>}
      {error && (
        <p role="alert" className="camera-error">
          {error}
        </p>
      )}
      {active && <button
        className="camera-toggle"
        onClick={stop}
      >
        <Square size={20} />结束陪练
      </button>}
      {active && <button className="camera-flip" aria-label={facing === "environment" ? "切换前置摄像头" : "切换后置摄像头"}
        onClick={() => void start(facing === "environment" ? "user" : "environment", true)}><SwitchCamera size={27} /></button>}
    </div>
  );
}

export function PracticePage() {
  const [params, setParams] = useSearchParams();
  const mode = params.get("mode") === "voice" ? "voice" : "video";
  function change(next: string) {
    stopAudio(true, "coach");
    stopAudio(false, "camera");
    setParams({ mode: next });
  }
  return (
    <div className="practice-modes" data-page="practice">
      <div className="practice-mode-switch" aria-label="陪练方式">
        <button
          className={mode === "video" ? "active" : ""}
          aria-pressed={mode === "video"}
          onClick={() => change("video")}
        >
          <Video size={20} />
          视频陪练
        </button>
        <button
          className={mode === "voice" ? "active" : ""}
          aria-pressed={mode === "voice"}
          onClick={() => change("voice")}
        >
          <Mic size={20} />
          语音陪练
        </button>
      </div>
      {mode === "video" ? <CameraPractice /> : <VoicePractice />}
    </div>
  );
}
function VoicePractice() {
  const [active, setActive] = useState(false);
  const [level, setLevel] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { user } = useLearning();
  const control = useRef<VoiceControl | null>(null);
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0), alive = useRef(true);
  function failed(message: string) {
    if (!alive.current) return;
    setError(message);
    stopAudio(true, "coach");
    void sayLocal(message, 1, "coach").catch(() => {});
  }
  async function respond(text: string) {
    const turn = ++generation.current;
    const valid = () => alive.current && turn === generation.current;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    audioReport("coach", { phase: "thinking" });
    try {
      const result = await api("/voice/coach", "POST", {
        agent_role: "tutor",
        client_request_id: newId(),
        message: text,
        ui_context: { page: "practice" },
      }, controller.signal);
      if (!valid()) return;
      audioReport("coach", { phase: "speaking" });
      try { await speak(result.reply.id, 1, "coach"); }
      catch {
        if (!valid()) return;
        await sayLocal(result.reply.speech_text || result.reply.display_text, 1, "coach");
      }
      if (valid()) audioReport("coach", { phase: "done" });
    } catch (e) {
      if (valid() && !controller.signal.aborted) {
        audioReport("coach", { phase: "error", code: e instanceof Error ? e.message : "COACH_FAILED" });
        failed(friendly(e));
      }
    } finally {
      if (valid()) setBusy(false);
    }
  }
  useEffect(() => {
    alive.current = true;
    const meter = (e: Event) => {
      const data = (e as CustomEvent).detail;
      if (data?.owner === "coach") setLevel(data.level);
    };
    const stopped = (e: Event) => {
      if ((e as CustomEvent).detail?.owner !== "coach") return;
      generation.current++;
      request.current?.abort();
      if (alive.current) { setActive(false); setBusy(false); }
    };
    const started = (e: Event) => {
      if ((e as CustomEvent).detail?.owner === "coach") setError("");
    };
    window.addEventListener("xiaoban-input-level", meter);
    window.addEventListener("xiaoban-audio-stop", stopped);
    window.addEventListener("xiaoban-voice-start", started);
    return () => {
      alive.current = false;
      generation.current++;
      request.current?.abort();
      window.removeEventListener("xiaoban-input-level", meter);
      window.removeEventListener("xiaoban-audio-stop", stopped);
      window.removeEventListener("xiaoban-voice-start", started);
      stopAudio(true, "coach");
    };
  }, []);
  return (
    <section className="voice-practice voice-without-text">
      <div className={"practice-orb " + (active ? "is-listening" : "")} style={{ boxShadow: active ? `0 0 0 ${8 + level / 4}px #52724f20` : undefined }}><Mic size={50} strokeWidth={1.6} /></div>
      <h1>语音陪练</h1>
      <button
        className={"practice-start " + (active ? "active" : "")}
        onClick={() => active ? control.current?.cancel() : control.current?.toggle()}
        title={error || undefined}
        aria-pressed={active}
      >
        {active ? "结束语音陪练" : "开始语音陪练"}
      </button>
      {error && <p role="alert" className="practice-error">{error}</p>}
      <VoiceInput owner="coach" compact control={control} onActiveChange={setActive}
        enabled={!!user && user.audio_provider !== "mock"} busy={busy}
        onText={(text) => void respond(text)} onError={failed} />
    </section>
  );
}
