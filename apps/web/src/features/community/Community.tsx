import { useEffect, useRef, useState } from "react";
import { api, friendly, token } from "../../lib/api";
import {
  ArrowLeft,
  Bookmark,
  Heart,
  MessageCircle,
  Upload,
  X,
  Video,
  FileText,
} from "lucide-react";
import { skillMeta, cleanTitle } from "../learning/skillCatalog";
import { useLearning } from "../learning/LearningProvider";

export function SharePage() {
  const { user } = useLearning();
  return (
    <div className="page global-share" data-page="community">
      <Community user={user} reels />
    </div>
  );
}

export function Community({
  user,
  skillId,
  reels = false,
}: {
  user: any;
  skillId?: string;
  reels?: boolean;
}) {
  const [items, setItems] = useState<any[]>([]),
    [mine, setMine] = useState(false),
    [compose, setCompose] = useState(false),
    [queue, setQueue] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  useEffect(() => {
    setSelected(null);
  }, [mine]);
  useEffect(() => {
    if (!selected) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", escape);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", escape);
    };
  }, [selected]);
  const [file, setFile] = useState<File | null>(null),
    [title, setTitle] = useState(""),
    [description, setDescription] = useState(""),
    [course, setCourse] = useState(
      skillMeta[skillId || "home-gardening"]?.course || "repotting-basics",
    ),
    [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const { courses: catalogCourses } = useLearning();
  const courses = Object.values(catalogCourses).flat();
  const formRef = useRef<HTMLFormElement>(null);
  const loadGeneration = useRef(0);
  async function load(own = mine) {
    try {
      const current = ++loadGeneration.current;
      const result = await api(
        "/community/works?mine=" + own + "&examples=true",
      );
      if (current !== loadGeneration.current) return;
      setItems(result.items);
      if (user?.is_admin) setQueue((await api("/community/moderation")).items);
    } catch (e) {
      setNotice(friendly(e));
    }
  }
  useEffect(() => {
    void load();
  }, [mine, user?.is_admin]);

  useEffect(() => {
    if (compose) {
      formRef.current?.querySelector<HTMLInputElement>("input")?.focus();
      const handler = (e: KeyboardEvent) => {
        if (e.key === "Escape" && !busy) setCompose(false);
      };
      window.addEventListener("keydown", handler);
      return () => window.removeEventListener("keydown", handler);
    }
  }, [compose, busy]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !confirmed) return;
    setBusy(true);
    setNotice("");
    let submitted: any = null;
    try {
      submitted = await api("/community/works", "POST", {
        title,
        description,
        course_id: course,
        publish_confirmation: "SHARE_THIS_WORK",
      });
      if (file) {
        const form = new FormData();
        form.append("file", file);
        await api(
          "/community/works/" +
            submitted.id +
            (file.type.startsWith("video/") ? "/video" : "/image"),
          "PUT",
          form,
        );
      }
      setFile(null);
      setTitle("");
      setDescription("");
      setConfirmed(false);
      setCompose(false);
      setMine(true);
      setNotice("已提交审核");
      await load(true);
    } catch (e) {
      if (submitted) {
        try {
          await api("/community/works/" + submitted.id, "DELETE");
        } catch {
          setNotice("上传未完成，已保存的文字可在“我的”中撤下。");
          setMine(true);
          await load(true);
          setBusy(false);
          return;
        }
      }
      setNotice(friendly(e));
    } finally {
      setBusy(false);
    }
  }
  async function remove(id: string) {
    try {
      await api("/community/works/" + id, "DELETE");
      await load();
    } catch (e) {
      setNotice(friendly(e));
    }
  }
  async function report(id: string) {
    try {
      await api("/community/works/" + id + "/report", "POST");
      setNotice("已举报");
      await load();
    } catch (e) {
      setNotice(friendly(e));
    }
  }
  async function moderate(id: string, decision: string) {
    try {
      await api("/community/moderation/" + id, "POST", { decision });
      await load();
    } catch (e) {
      setNotice(friendly(e));
    }
  }
  const feedRef = useRef<HTMLDivElement | null>(null),
    voiceActive = useRef(false);
  useEffect(() => {
    if (!reels || mine) return;
    const root = feedRef.current;
    if (!root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const card = entry.target as HTMLElement;
          card.dataset.visible = String(
            entry.isIntersecting && entry.intersectionRatio > 0.6,
          );
          card.querySelectorAll("video").forEach((v) => {
            if (card.dataset.visible === "true" && !voiceActive.current) {
              v.muted = true;
              void v.play().catch(() => {});
            } else v.pause();
          });
        }
      },
      { threshold: [0, 0.6, 1] },
    );
    root.querySelectorAll(".feed-card").forEach((c) => observer.observe(c));
    const mutation = new MutationObserver(() =>
      root.querySelectorAll(".feed-card").forEach((c) => {
        observer.observe(c);
        c.querySelectorAll("video").forEach((v) => {
          if (
            (c as HTMLElement).dataset.visible === "true" &&
            !voiceActive.current
          ) {
            v.muted = true;
            void v.play().catch(() => {});
          } else v.pause();
        });
      }),
    );
    mutation.observe(root, { childList: true, subtree: true });
    const voice = (e: Event) => {
      voiceActive.current = (e as CustomEvent).detail;
      root.querySelectorAll("video").forEach((v) => {
        if (voiceActive.current) v.pause();
        else if (
          v.closest<HTMLElement>(".feed-card")?.dataset.visible === "true"
        )
          void v.play().catch(() => {});
      });
    };
    window.addEventListener("xiaoban-voice-active", voice);
    return () => {
      observer.disconnect();
      mutation.disconnect();
      root.querySelectorAll("video").forEach((v) => v.pause());
      window.removeEventListener("xiaoban-voice-active", voice);
    };
  }, [reels, items, courses, mine]);
  const visible = items.filter(
    (w) =>
      (mine ? w.is_mine && !w.is_example : w.state === "APPROVED") &&
      (!skillId || w.course_id === skillMeta[skillId]?.course),
  );
  return (
    <div
      className={
        (reels ? "reels-community" : "skill-community") +
        (mine ? " mine-gallery" : "")
      }
    >
      {mine && !selected && !compose && (
        <div className="share-header">
          <button
            className="upload-button"
            onClick={() => {
              setNotice("");
              setCompose(true);
            }}
          >
            <Upload size={20} />
            上传
          </button>
        </div>
      )}
      <div className="feed-filters">
        <button aria-pressed={!mine} onClick={() => setMine(false)}>
          社区
        </button>
        <button aria-pressed={mine} onClick={() => setMine(true)}>
          我的
        </button>
      </div>
      {notice && !compose && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      {mine ? (
        <section className="my-work-grid" aria-label="我的历史作品">
          {visible.map((w) => (
            <button
              className="my-work-card"
              key={w.id}
              onClick={() => setSelected(w)}
              aria-label={"查看作品：" + w.title}
            >
              <GalleryCover work={w} />
              <strong>{w.title}</strong>
              <span>
                {
                  { PENDING: "待审核", APPROVED: "已发布", REJECTED: "未通过" }[
                    w.state as string
                  ]
                }
              </span>
            </button>
          ))}
        </section>
      ) : (
        <section className="feed-list" ref={feedRef}>
          {visible.map((w) => (
            <article className="feed-card" key={w.id} data-work-id={w.id}>
              {w.video_available ? (
                <WorkAsset id={w.id} kind="video" />
              ) : w.image_available ? (
                <WorkAsset id={w.id} kind="image" />
              ) : null}
              <div className="feed-info">
                <div className="feed-author">
                  <span className="author-dot">{mine ? "我" : "友"}</span>
                  <strong>
                    {mine
                      ? "我的"
                      : w.is_example
                        ? w.author + " · 示例分享"
                        : "学友分享"}
                  </strong>
                  <span>
                    {new Date(w.created_at).toLocaleDateString("zh-CN")}
                  </span>
                  {mine && (
                    <span className="work-state">
                      {
                        {
                          PENDING: "待审核",
                          APPROVED: "已发布",
                          REJECTED: "未通过",
                        }[w.state as string]
                      }
                    </span>
                  )}
                </div>
                <h3>{w.title}</h3>
                <p className="work-text">{w.description}</p>
                <FeedInteractions
                  target={(w.is_example ? "example:" : "work:") + w.id}
                />
                {!w.is_example && (
                  <button
                    className="work-action"
                    onClick={() =>
                      mine ? void remove(w.id) : void report(w.id)
                    }
                  >
                    {mine ? "撤下并删除" : "举报"}
                  </button>
                )}
              </div>
            </article>
          ))}
        </section>
      )}
      {selected && (
        <div
          className="work-fullscreen"
          data-work-id={selected.id}
          role="dialog"
          aria-modal="true"
          aria-label="查看作品"
        >
          <button
            className="work-back"
            aria-label="返回我的作品"
            onClick={() => setSelected(null)}
          >
            <ArrowLeft size={27} />
          </button>
          {selected.video_available ? (
            <WorkAsset id={selected.id} autoPlay />
          ) : selected.image_available ? (
            <WorkAsset id={selected.id} kind="image" />
          ) : null}
          <div className="work-fullscreen-caption">
            <h2>{selected.title}</h2>
            <p>{selected.description}</p>
            <button
              onClick={() => {
                void remove(selected.id).then(() => setSelected(null));
              }}
            >
              删除作品
            </button>
          </div>
        </div>
      )}
      {!mine && !visible.length && (
        <div className="community-empty">还没有分享</div>
      )}
      {mine && !visible.length && (
        <div className="empty-library">
          <Upload size={24} />
          <strong>暂无作品</strong>
        </div>
      )}
      {compose && (
        <div
          className="modal-backdrop"
          onClick={() => {
            if (!busy) setCompose(false);
          }}
        >
          <section
            className="share-composer"
            role="dialog"
            aria-modal="true"
            aria-label="上传作品"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="sheet-close"
              aria-label="关闭分享"
              disabled={busy}
              onClick={() => setCompose(false)}
            >
              <X size={24} />
            </button>
            <h2>上传作品</h2>
            <form ref={formRef} onSubmit={submit}>
              <label>
                标题
                <input
                  required
                  maxLength={80}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </label>
              <label>
                作品说明
                <textarea
                  required
                  maxLength={1000}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </label>
              <label>
                对应课程
                <select
                  value={course}
                  onChange={(e) => setCourse(e.target.value)}
                >
                  {courses.map((c) => (
                    <option value={c.id} key={c.id}>
                      {cleanTitle(c.title)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="upload-field">
                选择视频或照片
                <input
                  type="file"
                  accept="video/mp4,video/webm,image/jpeg,image/png,image/webp"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    const video = f.type.startsWith("video/"),
                      limit = (video ? 30 : 4) * 1024 * 1024;
                    if (f.size > limit) {
                      setFile(null);
                      e.target.value = "";
                      setNotice(video ? "视频请小于30MB。" : "照片请小于4MB。");
                      return;
                    }
                    setFile(f);
                    setNotice("");
                  }}
                />
              </label>
              <label className="voice-option">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                确认原创并分享
              </label>
              <button className="primary" disabled={!confirmed || busy}>
                {busy ? "正在上传…" : "发布分享"}
              </button>
              {notice && <p role="alert">{notice}</p>}
            </form>
          </section>
        </div>
      )}
      {user?.is_admin && !mine && queue.length > 0 && (
        <section className="moderation">
          <h2>待审核</h2>
          {queue.map((w) => (
            <article className="feed-card" key={w.id}>
              <div className="feed-info">
                <h3>{w.title}</h3>
                <p>{w.description}</p>
                {w.video_available ? (
                  <WorkAsset id={w.id} kind="video" />
                ) : w.image_available ? (
                  <WorkAsset id={w.id} kind="image" />
                ) : null}
                <div className="button-row">
                  <button onClick={() => void moderate(w.id, "approve")}>
                    通过审核
                  </button>
                  <button onClick={() => void moderate(w.id, "reject")}>
                    拒绝
                  </button>
                </div>
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
function GalleryCover({ work }: { work: any }) {
  const holder = useRef<HTMLDivElement | null>(null);
  const [near, setNear] = useState(false),
    [url, setUrl] = useState("");
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setNear(true);
          observer.disconnect();
        }
      },
      { rootMargin: "150px" },
    );
    if (holder.current) observer.observe(holder.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!near || (!work.video_available && !work.image_available)) return;
    let value = "";
    const c = new AbortController();
    fetch("/api/v1/community/works/" + work.id + "/thumbnail", {
      headers: { Authorization: "Bearer " + token() },
      signal: c.signal,
    })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.blob();
      })
      .then((b) => {
        if (!c.signal.aborted) {
          value = URL.createObjectURL(b);
          setUrl(value);
        }
      })
      .catch(() => {});
    return () => {
      c.abort();
      if (value) URL.revokeObjectURL(value);
    };
  }, [near, work.id, work.video_available, work.image_available]);
  return (
    <div className="my-work-cover" ref={holder}>
      {url ? (
        <img src={url} alt="" />
      ) : work.video_available ? (
        <Video size={34} />
      ) : (
        <FileText size={34} />
      )}
    </div>
  );
}
export function WorkAsset({
  id,
  kind = "video",
  preview = false,
  autoPlay = false,
  poster,
}: {
  id: string;
  kind?: "image" | "video";
  preview?: boolean;
  autoPlay?: boolean;
  poster?: string;
}) {
  const [url, setUrl] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    let value = "";
    const c = new AbortController(),
      timer = setTimeout(() => c.abort(), 30000);
    fetch(
      (id.startsWith("example-")
        ? "/api/v1/community/examples/"
        : "/api/v1/community/works/") +
        id +
        "/" +
        kind,
      {
        headers: { Authorization: "Bearer " + token() },
        signal: c.signal,
      },
    )
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.blob();
      })
      .then((b) => {
        if (!c.signal.aborted) {
          value = URL.createObjectURL(b);
          setUrl(value);
        }
      })
      .catch(() => {
        if (!c.signal.aborted) setError("作品未能加载，请重试。");
      })
      .finally(() => clearTimeout(timer));
    return () => {
      clearTimeout(timer);
      c.abort();
      if (value) URL.revokeObjectURL(value);
    };
  }, [id, kind]);
  return url ? (
    kind === "video" ? (
      <video
        poster={poster}
        controls={!preview}
        muted={preview || autoPlay}
        autoPlay={autoPlay}
        playsInline
        src={url}
        className="shared-video"
        preload="metadata"
      />
    ) : (
      <img src={url} alt="原创作品" className="work-image" />
    )
  ) : (
    <p role="status">{error || "正在加载作品…"}</p>
  );
}
function FeedInteractions({ target }: { target: string }) {
  const [state, setState] = useState<any>({
      liked: false,
      saved: false,
      likes: 0,
      comments: [],
    }),
    [open, setOpen] = useState(false),
    [body, setBody] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const path = "/community/threads/" + encodeURIComponent(target);
  useEffect(() => {
    const c = new AbortController();
    api(path, "GET", undefined, c.signal)
      .then(setState)
      .catch((e) => {
        if (!c.signal.aborted) setError(friendly(e));
      });
    return () => c.abort();
  }, [path]);
  async function react(key: "liked" | "saved") {
    if (busy) return;
    setBusy(true);
    try {
      setState(
        await api(path + "/reaction", "PUT", {
          liked: state.liked,
          saved: state.saved,
          [key]: !state[key],
        }),
      );
      setError("");
    } catch (e) {
      setError(friendly(e));
    } finally {
      setBusy(false);
    }
  }
  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim() || busy) return;
    setBusy(true);
    try {
      await api(path + "/comments", "POST", { body: body.trim() });
      setBody("");
      setState(await api(path));
      setError("");
    } catch (e) {
      setError(friendly(e));
    } finally {
      setBusy(false);
    }
  }
  async function remove(id: string) {
    try {
      await api("/community/comments/" + id, "DELETE");
      setState(await api(path));
    } catch (e) {
      setError(friendly(e));
    }
  }
  return (
    <>
      <div className="feed-actions">
        <button
          aria-label="点赞"
          aria-pressed={state.liked}
          className={state.liked ? "on" : ""}
          disabled={busy}
          onClick={() => void react("liked")}
        >
          <Heart size={23} fill={state.liked ? "currentColor" : "none"} />
          <span>{state.likes}</span>
        </button>
        <button
          aria-pressed={state.saved}
          className={state.saved ? "on" : ""}
          disabled={busy}
          onClick={() => void react("saved")}
        >
          <Bookmark size={22} fill={state.saved ? "currentColor" : "none"} />
          <span>{state.saved ? "已收藏" : "收藏"}</span>
        </button>
        <button aria-expanded={open} onClick={() => setOpen(!open)}>
          <MessageCircle size={22} />
          <span>
            交流{state.comments.length ? " " + state.comments.length : ""}
          </span>
        </button>
      </div>
      {open && (
        <section className="feed-comments">
          <h4>聊聊这份练习</h4>
          {state.comments.map((c: any) => (
            <div key={c.id}>
              <strong>{c.own ? "我" : "学友"}</strong>
              <p>{c.body}</p>
              {c.own && <button onClick={() => void remove(c.id)}>删除</button>}
            </div>
          ))}
          <form onSubmit={send}>
            <label>
              说点什么
              <input
                value={body}
                maxLength={500}
                onChange={(e) => setBody(e.target.value)}
                required
              />
            </label>
            <button disabled={busy || !body.trim()}>发送留言</button>
          </form>
        </section>
      )}
      {error && <p role="alert">{error}</p>}
    </>
  );
}
