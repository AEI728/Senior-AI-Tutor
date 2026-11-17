// Legacy MediaRecorder implementation, retained for reference. Active app uses voice.tsx.
import { useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { api, friendly } from "./api";

let playing: HTMLAudioElement | null = null;
let stream: MediaStream | null = null;
let recorder: MediaRecorder | null = null;
let pending: AbortController | null = null;
export function stopAudio() {
  playing?.pause();
  playing = null;
  pending?.abort();
  pending = null;
  if (recorder?.state === "recording") recorder.stop();
  stream?.getTracks().forEach((t) => t.stop());
  stream = null;
}
export async function speak(replyId: string, rate: number) {
  stopAudio();
  pending = new AbortController();
  const r = await fetch("/api/v1/audio/speech", {
    method: "POST",
    signal: pending.signal,
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + sessionStorage.getItem("xiaoban-token"),
    },
    body: JSON.stringify({ reply_id: replyId }),
  });
  if (!r.ok) throw new Error("TTS_UNAVAILABLE");
  const url = URL.createObjectURL(await r.blob());
  playing = new Audio(url);
  playing.playbackRate = rate;
  playing.onended = () => URL.revokeObjectURL(url);
  await playing.play();
}
export function VoiceInput({
  onText,
  onError,
  enabled,
}: {
  onText: (s: string) => void;
  onError: (s: string) => void;
  enabled: boolean;
}) {
  const [recording, setRecording] = useState(false),
    alive = useRef(true),
    timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      clearTimeout(timer.current);
      stopAudio();
    };
  }, []);
  async function record() {
    if (recording) {
      recorder?.stop();
      setRecording(false);
      return;
    }
    if (!enabled) {
      onError("当前为模拟语音模式，请使用文字输入。");
      return;
    }
    try {
      stopAudio();
      if (!window.MediaRecorder) throw new Error("AUDIO_UNSUPPORTED");
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!alive.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg"].find(
        (m) => MediaRecorder.isTypeSupported(m),
      );
      if (!mime) throw new Error("AUDIO_UNSUPPORTED");
      recorder = new MediaRecorder(stream, { mimeType: mime });
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        clearTimeout(timer.current);
        stream?.getTracks().forEach((t) => t.stop());
        if (!alive.current) return;
        setRecording(false);
        const form = new FormData();
        form.append(
          "file",
          new Blob(chunks, { type: mime }),
          "recording." + (mime.includes("mp4") ? "mp4" : "webm"),
        );
        try {
          const r = await api("/audio/transcriptions", "POST", form);
          if (alive.current) onText(r.text);
        } catch (e) {
          if (alive.current) onError(friendly(e));
        }
      };
      recorder.start();
      setRecording(true);
      timer.current = setTimeout(() => {
        if (recorder?.state === "recording") recorder.stop();
      }, 19000);
    } catch (e) {
      stream?.getTracks().forEach((t) => t.stop());
      onError(
        e instanceof DOMException && e.name === "NotAllowedError"
          ? "麦克风未获授权，仍可在下方打字。"
          : friendly(e),
      );
    }
  }
  return (
    <button
      type="button"
      className={"voice " + (recording ? "recording" : "")}
      onClick={record}
    >
      {recording ? <Square size={22} /> : <Mic size={22} />}{" "}
      {recording ? "结束录音" : "点击说话"}
    </button>
  );
}
