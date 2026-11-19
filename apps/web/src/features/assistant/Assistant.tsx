import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Mic } from "lucide-react";
import { api, newId, friendly } from "../../lib/api";
import { VoiceInput, speak, stopAudio, type VoiceControl } from "../voice/VoiceInput";
import { audioReport } from "../voice/diagnostics";
import { sayLocal } from "../voice/media";

function AssistantConversation({ user, voiceControl, onVoiceActive }: {
  user: any;
  voiceControl?: MutableRefObject<VoiceControl | null>;
  onVoiceActive?: (active: boolean) => void;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [rate, setRate] = useState(1),
    [speaking, setSpeaking] = useState(false);
  const location = useLocation(),
    navigate = useNavigate(),
    pendingRequest = useRef<any>(null),
    controller = useRef<AbortController | null>(null),
    alive = useRef(true),
    voiceTurn = useRef(0);
  useEffect(() => {
    if (error) {
      stopAudio(true, "assistant");
      window.dispatchEvent(new CustomEvent("xiaoban-voice-error", { detail: error }));
      void sayLocal(error).catch(() => {});
    }
  }, [error]);
  useEffect(() => {
    const clear = (e: Event) => {
      if ((e as CustomEvent).detail?.owner === "assistant") setError("");
    };
    window.addEventListener("xiaoban-voice-start", clear);
    return () => window.removeEventListener("xiaoban-voice-start", clear);
  }, []);
  useEffect(() => {
    alive.current = true;
    const stopped = (e: Event) => {
      if ((e as CustomEvent).detail?.owner !== "assistant") return;
      voiceTurn.current++;
      controller.current?.abort();
      pendingRequest.current = null;
      if (alive.current) { setBusy(false); setSpeaking(false); }
    };
    window.addEventListener("xiaoban-audio-stop", stopped);
    return () => {
      alive.current = false;
      window.removeEventListener("xiaoban-audio-stop", stopped);
      controller.current?.abort();
      stopAudio(true, "assistant");
    };
  }, []);
  async function send(value: string) {
    const input = value.trim();
    if (!input || busy) return;
    const currentTurn = ++voiceTurn.current;
    const valid = () => alive.current && currentTurn === voiceTurn.current;
    stopAudio(false, "assistant");
    setBusy(true);
    audioReport("assistant", { phase: "thinking" });
    setError("");
    if (input.includes("慢")) setRate(0.75);
    const page =
      location.pathname.startsWith("/lessons")
          ? "lesson"
          : location.pathname.includes("skills")
            ? "skills"
            : ["/share", "/community"].includes(location.pathname)
              ? "community"
              : location.pathname.startsWith("/practice")
                ? "practice"
                : "home";
    const request =
      pendingRequest.current?.message === input
        ? pendingRequest.current
        : {
            agent_role: "companion",
            client_request_id: newId(),
            message: input,
            ui_context: {
              page,
              focused_skill_id: location.pathname.startsWith("/skills/")
                ? decodeURIComponent(location.pathname.split("/")[2])
                : null,
              course_id:
                page === "lesson"
                  ? decodeURIComponent(location.pathname.split("/")[2])
                  : null,
            },
            practice_session_id: null,
          };
    pendingRequest.current = request;
    controller.current = new AbortController();
    try {
      let r = await api(
        "/agent/turns",
        "POST",
        request,
        controller.current.signal,
      );
      if (!valid()) return;
      pendingRequest.current = null;
      for (const action of r.ui_actions) {
        if (!valid()) return;
        let applied = false;
        try {
          if (
            action.type === "OPEN_LESSON" &&
            typeof action.payload.course_id === "string"
          ) {
            navigate(
              "/lessons/" + encodeURIComponent(action.payload.course_id),
            );
            for (let i = 0; i < 50; i++) {
              await new Promise((resolve) => setTimeout(resolve, 100));
              if (
                document.querySelector(
                  `[data-course-ready="${CSS.escape(action.payload.course_id)}"]`,
                )
              ) {
                applied = true;
                break;
              }
            }
          } else if (
            action.type === "PAUSE_PLAYER" ||
            action.type === "RESUME_PLAYER"
          ) {
            const video =
              document.querySelector<HTMLVideoElement>(
                '.feed-card[data-visible="true"] video',
              ) ||
              document.querySelector<HTMLVideoElement>("[data-lesson-player]");
            if (!video) throw new Error("PLAYER_NOT_READY");
            if (action.type === "PAUSE_PLAYER") {
              video.pause();
              applied = video.paused;
            } else {
              await video.play();
              applied = !video.paused;
            }
          } else if (action.type === "OPEN_PAGE") {
            const pages: Record<string, string> = {
              home: "/",
              skills: "/skills",
              settings: "/settings",
              community: "/community",
              practice: "/practice",
            };
            const target = pages[action.payload.page];
            if (!target) throw new Error("INVALID_NAVIGATION");
            navigate(
              action.payload.page === "skills" && action.payload.skill_id
                ? "/skills/" + encodeURIComponent(action.payload.skill_id)
                : target,
            );
            for (let i = 0; i < 80; i++) {
              await new Promise((resolve) => setTimeout(resolve, 100));
              if (
                document.querySelector(
                  '[data-page="' + action.payload.page + '"]',
                )
              ) {
                applied = true;
                break;
              }
            }
          } else if (
            action.type === "START_PRACTICE" &&
            typeof action.payload.session_id === "string"
          ) {
            // The destination page acknowledges only after loading its session.
            sessionStorage.setItem("practice-action", action.id);
            navigate(
              "/practice/" + encodeURIComponent(action.payload.session_id),
            );
            return;
          }
        } finally {
          if (action.type !== "START_PRACTICE")
            r = await api("/agent/ui-actions/" + action.id + "/ack", "POST", {
              result: applied ? "applied" : "failed",
              error_code: applied ? null : "PAGE_LOAD_FAILED",
            });
        }
      }
      if (valid()) {
        if (r.error_code) setError(friendly(new Error(r.error_code)));
        window.dispatchEvent(new Event("learning-changed"));
        if (user && user.audio_provider !== "mock") {
          setSpeaking(true);
          audioReport("assistant", { phase: "speaking" });
          try {
            await speak(r.reply.id, rate, "assistant");
          } catch {
            if (!valid()) return;
            try { await sayLocal(r.reply.speech_text || r.reply.display_text, rate); }
            catch { setError("语音播放未成功，请检查浏览器声音权限和扬声器。"); }
          } finally {
            if (valid()) setSpeaking(false);
          }
        }
        audioReport("assistant", { phase: "done" });
      }
    } catch (e) {
      if (
        valid() &&
        !(e instanceof DOMException && e.name === "AbortError")
      ) {
        setError(friendly(e));
        audioReport("assistant", { phase: "error", code: e instanceof Error ? e.message : "ASSISTANT_FAILED" });
      }
    } finally {
      if (valid()) setBusy(false);
    }
  }
  return (
      <div
        className="direct-conversation voice-without-text"
        aria-live="polite"
      >
        <VoiceInput
          owner="assistant"
          control={voiceControl}
          compact
          onActiveChange={onVoiceActive}
          enabled={!!user && user.audio_provider !== "mock"}
          busy={busy || speaking}
          onText={(text) => void send(text)}
          onError={setError}
        />
      </div>
    );
}

export function Assistant({ user }: { user: any }) {
  const [active, setActive] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const [inputLevel, setInputLevel] = useState(0);
  const control = useRef<VoiceControl | null>(null);
  useEffect(() => {
    const error = (e: Event) => setVoiceError((e as CustomEvent).detail);
    const meter = (e: Event) => {
      const data = (e as CustomEvent).detail;
      if (data?.owner === "assistant") setInputLevel(data.level);
    };
    window.addEventListener("xiaoban-voice-error", error);
    window.addEventListener("xiaoban-input-level", meter);
    return () => { window.removeEventListener("xiaoban-voice-error", error); window.removeEventListener("xiaoban-input-level", meter); };
  }, []);
  return (
    <aside
      data-testid="companion"
      className={"direct-assistant " + (active ? "is-active" : "")}
    >
      <button
        className={"bottom-mic " + (active ? "listening" : "") + (voiceError ? " voice-failed" : "")}
        title={voiceError || "点击开始对话"}
        style={{ boxShadow: active ? `0 0 0 ${3 + inputLevel / 10}px #52724f45` : undefined }}
        aria-label="小伴语音助手"
        aria-description={voiceError || undefined}
        aria-pressed={active}
        onClick={() => {
          setVoiceError("");
          control.current?.toggle();
        }}
      >
        <Mic size={27} />
      </button>
      <AssistantConversation
        user={user}
        voiceControl={control}
        onVoiceActive={setActive}
      />
    </aside>
  );
}
