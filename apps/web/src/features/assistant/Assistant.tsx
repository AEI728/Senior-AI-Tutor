import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { LoaderCircle, Mic } from "lucide-react";
import { api, newId, friendly } from "../../lib/api";
import { VoiceInput, speak, stopAudio, type VoiceControl } from "../voice/VoiceInput";
import { audioReport } from "../voice/diagnostics";
import { sayLocal } from "../voice/media";
import { readPageContext } from "./pageContext";

function AssistantConversation({ user, voiceControl, onVoiceActive, onWaitingChange }: {
  user: any;
  voiceControl?: MutableRefObject<VoiceControl | null>;
  onVoiceActive?: (active: boolean) => void;
  onWaitingChange?: (waiting: boolean) => void;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [rate, setRate] = useState(1),
    [speaking, setSpeaking] = useState(false);
  useEffect(() => {
    onWaitingChange?.(busy && !speaking);
  }, [busy, speaking, onWaitingChange]);
  const location = useLocation(),
    navigate = useNavigate(),
    pendingRequest = useRef<any>(null),
    controller = useRef<AbortController | null>(null),
    alive = useRef(true),
    voiceTurn = useRef(0);
  const capturedContext = useRef<ReturnType<typeof readPageContext> | null>(null);
  useEffect(() => {
    if (error) {
      stopAudio(true, "assistant");
      window.dispatchEvent(new CustomEvent("xiaoban-voice-error", { detail: error }));
      void sayLocal(error).catch(() => {});
    }
  }, [error]);
  useEffect(() => {
    const clear = (e: Event) => {
      if ((e as CustomEvent).detail?.owner === "assistant") {
        setError("");
        capturedContext.current = readPageContext(window.location.pathname);
      }
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
    const uiContext = capturedContext.current || readPageContext(location.pathname);
    const request =
      pendingRequest.current?.message === input && JSON.stringify(pendingRequest.current.ui_context) === JSON.stringify(uiContext)
        ? pendingRequest.current
        : {
            agent_role: "companion",
            client_request_id: newId(),
            message: input,
            ui_context: uiContext,
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
          holdToTalk
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
  const [waiting, setWaiting] = useState(false);
  const [holding, setHolding] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const [inputLevel, setInputLevel] = useState(0);
  const control = useRef<VoiceControl | null>(null);
  const heldPointer = useRef<number | null>(null);
  const heldKey = useRef<string | null>(null);
  const cancelHold = () => {
    if (heldPointer.current === null && heldKey.current === null) return;
    heldPointer.current = null;
    heldKey.current = null;
    setHolding(false);
    control.current?.cancel();
  };
  useEffect(() => {
    const hidden = () => { if (document.hidden) cancelHold(); };
    window.addEventListener("blur", cancelHold);
    document.addEventListener("visibilitychange", hidden);
    return () => {
      window.removeEventListener("blur", cancelHold);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, []);
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
        className={"bottom-mic " + (waiting ? "waiting" : holding ? "listening" : "")}
        title={waiting ? "小伴正在思考" : voiceError || "按住说话，松开发送"}
        style={{ boxShadow: holding && !waiting ? `0 0 0 ${3 + inputLevel / 10}px #52724f45` : undefined }}
        aria-label="小伴语音助手"
        aria-busy={waiting}
        disabled={waiting || (active && !holding)}
        aria-description={voiceError || undefined}
        aria-pressed={holding}
        onPointerDown={(event) => {
          if (event.button !== 0 || !event.isPrimary || heldPointer.current !== null || heldKey.current !== null) return;
          event.preventDefault();
          event.currentTarget.focus();
          event.currentTarget.setPointerCapture(event.pointerId);
          heldPointer.current = event.pointerId;
          setVoiceError("");
          setHolding(true);
          control.current?.start();
        }}
        onPointerUp={(event) => {
          if (heldPointer.current !== event.pointerId) return;
          heldPointer.current = null;
          setHolding(false);
          control.current?.submit();
          if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
        }}
        onPointerCancel={cancelHold}
        onLostPointerCapture={cancelHold}
        onContextMenu={(event) => event.preventDefault()}
        onKeyDown={(event) => {
          if (![" ", "Enter"].includes(event.key)) return;
          event.preventDefault();
          if (event.repeat || heldKey.current !== null || heldPointer.current !== null) return;
          heldKey.current = event.key;
          setVoiceError("");
          setHolding(true);
          control.current?.start();
        }}
        onKeyUp={(event) => {
          if (heldKey.current !== event.key) return;
          event.preventDefault();
          heldKey.current = null;
          setHolding(false);
          control.current?.submit();
        }}
        onBlur={cancelHold}
      >
        {waiting ? <LoaderCircle className="mic-waiting-spinner" size={27} aria-hidden="true" /> : <Mic size={27} />}
      </button>
      <AssistantConversation
        user={user}
        voiceControl={control}
        onVoiceActive={setActive}
        onWaitingChange={setWaiting}
      />
    </aside>
  );
}
