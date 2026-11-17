import { useEffect, useRef, useState } from "react";
import { api, token, friendly } from "./api";
export function LessonVideo({
  courseId,
  step,
}: {
  courseId: string;
  step: number;
}) {
  const [url, setUrl] = useState(""),
    [error, setError] = useState(""),
    video = useRef<HTMLVideoElement>(null),
    saved = useRef(0),
    currentStep = useRef(step);
  currentStep.current = step;
  useEffect(() => {
    let blobUrl = "",
      alive = true;
    const c = new AbortController();
    async function load() {
      try {
        const r = await fetch(
          "/api/v1/catalog/courses/" +
            encodeURIComponent(courseId) +
            "/demo-video",
          { headers: { Authorization: "Bearer " + token() }, signal: c.signal },
        );
        if (!r.ok) throw new Error("VIDEO_UNAVAILABLE");
        blobUrl = URL.createObjectURL(await r.blob());
        if (alive) setUrl(blobUrl);
      } catch (e) {
        if (alive) setError(friendly(e));
      }
    }
    void load();
    return () => {
      alive = false;
      c.abort();
      const seconds = Math.floor(video.current?.currentTime || 0);
      void fetch("/api/v1/progress/" + encodeURIComponent(courseId), {
        method: "PUT",
        keepalive: true,
        headers: {
          Authorization: "Bearer " + token(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          position_seconds: seconds,
          current_step: currentStep.current,
        }),
      });
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [courseId]);
  async function restore() {
    try {
      const p = (await api("/progress/recent")).items.find(
        (p: any) => p.course_id === courseId,
      );
      if (p && video.current)
        video.current.currentTime = Math.min(
          p.position_seconds,
          video.current.duration || 0,
        );
    } catch {
      setError("视频进度暂时无法恢复，文字步骤仍可学习。");
    }
  }
  async function progress() {
    const position = Math.floor(video.current?.currentTime || 0);
    if (Date.now() - saved.current < 10000) return;
    saved.current = Date.now();
    try {
      await api("/progress/" + courseId, "PUT", {
        position_seconds: position,
        current_step: currentStep.current,
      });
    } catch {
      setError("暂时无法保存视频进度。");
    }
  }
  return (
    <section className="panel">
      <h2>原创流程示意</h2>
      <p className="muted">
        合成步骤卡片，非真人授课；内部测试，未经专业审核。
      </p>
      {url && (
        <video
          ref={video}
          data-lesson-player
          controls
          playsInline
          src={url}
          onLoadedMetadata={() => void restore()}
          onTimeUpdate={() => void progress()}
          onError={() => setError("视频暂时无法播放，请阅读文字步骤。")}
          className="lesson-player"
        />
      )}
      {!url && !error && <p role="status">正在加载流程示意…</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
