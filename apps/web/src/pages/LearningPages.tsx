import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Clock3,
  CircleCheck,
  HeartOff,
  Play,
  Plus,
  Sparkles,
  X,
} from "lucide-react";
import { api, friendly } from "../lib/api";
import { skillArt } from "../features/learning/skillArtwork";
import { LessonVideo } from "../features/learning/LessonVideo";
import { WorkAsset as SharedRecommendationVideo } from "../features/community/Community";

import { skillMeta, skillStyle, cleanTitle } from "../features/learning/skillCatalog";
import { useLearning } from "../features/learning/LearningProvider";
function Days({ joined }: { joined?: string }) {
  const days = joined
    ? Math.max(
        1,
        Math.floor((Date.now() - new Date(joined).getTime()) / 86400000) + 1,
      )
    : 1;
  return (
    <span>
      <Clock3 size={16} />
      加入学习 {days} 天
    </span>
  );
}
export function HomePage() {
  const { library, loading, error, refresh } = useLearning();
  const [notice, setNotice] = useState("");
  const navigate = useNavigate();
  async function remove(id: string, complete = false) {
    try {
      await api("/library/" + id + (complete ? "/complete" : ""), complete ? "POST" : "DELETE");
      await refresh();
    } catch (e) {
      setNotice(friendly(e));
    }
  }
  const recommended = useRecommendation();
  return (
    <div className="page home-page" data-page="home">
      {recommended && (
        <Link to={"/recommend/" + recommended.id} className="featured-skill">
          <div className="featured-image">
            <SharedRecommendationVideo
              id={recommended.id}
              preview
              poster={
                recommended.is_example
                  ? skillArt[recommended.skill_id]?.image
                  : undefined
              }
            />
            <span className="featured-kicker">
              <Sparkles size={14} />
              今日推荐
            </span>
            <span className="featured-play">
              <Play size={23} fill="white" />
            </span>
          </div>
        </Link>
      )}
      <div className="section-heading">
        <h2>正在学习</h2>
      </div>
      <section id="skill-library" className="skill-grid">
        {library.map((item) => {
          const id = item.skill_id,
            meta = skillMeta[id];
          if (!meta) return null;
          return (
            <article className="skill-card" key={id} style={skillStyle(id)}>
              <button
                className="skill-card-main"
                onClick={() => navigate("/skills/" + id + "?tab=tutorial")}
              >
                <div className="skill-card-content">
                  <div>
                    <h3>{meta.name}</h3>
                  </div>
                  <ChevronRight className="skill-chevron" size={25} />
                </div>
                <div className="skill-checkin">
                  <Days joined={item.joined_at} />
                </div>
              </button>
              <div className="direct-skill-actions">
                <button onClick={() => void remove(id)}>
                  <HeartOff size={17} />
                  不感兴趣
                </button>
                <button onClick={() => void remove(id, true)}>
                  <CircleCheck size={17} />
                  完成学习
                </button>
              </div>
            </article>
          );
        })}
        {!loading && !library.length && (
          <div className="empty-library">暂无学习技能</div>
        )}
      </section>
      {loading && <p role="status">正在准备课程…</p>}
      {(error || notice) && <p role="alert">{notice || error}</p>}
    </div>
  );
}
export function SkillsPage() {
  const { skills, library, completed, loading, error } = useLearning();
  const [filter, setFilter] = useState("all");
  const joined = new Set(library.map((s) => s.skill_id));
  const finished = new Set(completed.map((s) => s.skill_id));
  const sorted = [...skills].sort(
    (a, b) => Number(joined.has(a.id)) - Number(joined.has(b.id)),
  );
  return (
    <div className="page plaza-page" data-page="skills">
      <div className="plaza-filters" aria-label="筛选技能">
        {[
          ["all", "全部 " + skills.length],
          ["new", "未学习 " + skills.filter((s) => !joined.has(s.id) && !finished.has(s.id)).length],
          ["learning", "学习中 " + joined.size],
          ["completed", "已完成 " + finished.size],
        ].map(([id, label]) => (
          <button
            key={id}
            className={id === filter ? "active" : ""}
            onClick={() => setFilter(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <section className="plaza-grid">
        {sorted
          .filter(
            (s) =>
              filter === "all" ||
              (filter === "learning" ? joined.has(s.id) : filter === "completed" ? finished.has(s.id) : !joined.has(s.id) && !finished.has(s.id)),
          )
          .map((s) => (
            <Link
              className="plaza-skill"
              to={"/skills/" + s.id + "?tab=tutorial"}
              key={s.id}
              style={skillStyle(s.id)}
            >
              <div
                className="plaza-media"
                style={{ backgroundImage: `url(${skillArt[s.id]?.image})` }}
              >
                <span className="plaza-play">
                  <Play size={24} fill="white" />
                </span>
                {joined.has(s.id) && (
                  <span className="plaza-learning">
                    <Check size={14} />
                    正在学习
                  </span>
                )}
                {finished.has(s.id) && <span className="plaza-learning"><Check size={14} />已完成</span>}
              </div>
              <div className="plaza-copy">
                <div>
                  <h2>{skillMeta[s.id]?.name || s.name}</h2>
                </div>
                <ChevronRight size={23} />
              </div>
            </Link>
          ))}
      </section>
      {loading && <p role="status">正在加载…</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
export function SkillPage({
  fixedSkill,
  children,
}: {
  fixedSkill?: string;
  children?: ReactNode;
}) {
  const { skillId } = useParams();
  const id = fixedSkill || skillId || "home-gardening",
    meta = skillMeta[id];
  const tab = "tutorial";
  const { library, courses, progress, refresh } = useLearning();
  const joined = library.find((s) => s.skill_id === id);
  const [error, setError] = useState(""),
    [saving, setSaving] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    if (meta) localStorage.setItem("xiaoban-last-skill", id);
  }, [id]);
  if (!meta)
    return (
      <div className="page">
        <h1>未找到这项技能</h1>
        <Link to="/skills">返回技能广场</Link>
      </div>
    );
  const lessons = courses[id] || [],
    recent = progress.find((p) => lessons.some((c) => c.id === p.course_id));
  async function toggle(remove = false, complete = false) {
    setSaving(true);
    try {
      await api("/library/" + id + (complete ? "/complete" : ""), complete ? "POST" : remove ? "DELETE" : "PUT");
      await refresh();
      if (remove) navigate("/");
    } catch (e) {
      setError(friendly(e));
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="page skill-page" data-page="skills" style={skillStyle(id)}>
      <header className="skill-header">
        <Link className="back-btn" to="/" aria-label="返回首页">
          <ArrowLeft size={27} />
        </Link>
        <div className="skill-title">
          <span className="mini-glyph">{skillArt[id].glyph}</span>
          <div>
            <h1 id="page-title" tabIndex={-1}>
              {meta.name}
            </h1>
          </div>
        </div>
        {!joined && (
          <button
            className="header-join"
            disabled={saving}
            onClick={() => void toggle()}
          >
            <Plus size={17} />
            加入学习
          </button>
        )}
      </header>
      {joined && (
        <div className="skill-learning-actions">
          <button onClick={() => void toggle(true)} disabled={saving}>
            <HeartOff size={18} />
            不感兴趣
          </button>
          <button onClick={() => void toggle(true, true)} disabled={saving}>
            <CircleCheck size={18} />
            完成学习
          </button>
        </div>
      )}
      <div className="skill-meta">
        {joined ? <Days joined={joined.joined_at} /> : <span />}
      </div>
      <div className="tab-content">
        {tab === "tutorial" && (
          <>
            {recent && (
              <Link
                className="continue-banner"
                to={"/lessons/" + recent.course_id}
              >
                <div
                  className="continue-thumb"
                  style={{ backgroundImage: `url(${skillArt[id].image})` }}
                >
                  <span className="play-mini">
                    <Play size={20} fill="white" />
                  </span>
                </div>
                <div className="continue-copy">
                  <span>接着练 · 第 {recent.current_step} 步</span>
                  <h2>
                    {cleanTitle(
                      lessons.find((c) => c.id === recent.course_id)?.title ||
                        "继续上次课程",
                    )}
                  </h2>
                  <div className="watch-progress">
                    <i
                      style={{
                        width:
                          (recent.current_step /
                            (lessons.find((c) => c.id === recent.course_id)
                              ?.steps?.length || 1)) *
                            100 +
                          "%",
                      }}
                    />
                  </div>
                </div>
                <ChevronRight className="continue-arrow" size={23} />
              </Link>
            )}
            <div className="list-heading">
              <div>
                <h2>教程</h2>
              </div>
              <span>共 {lessons.length} 节</span>
            </div>
            <section className="lesson-list">
              {lessons.map((lesson, index) => (
                <Link
                  className="lesson-row"
                  to={"/lessons/" + lesson.id}
                  key={lesson.id}
                >
                  <div className="lesson-index">
                    {String(index + 1).padStart(2, "0")}
                  </div>
                  <div
                    className="lesson-image"
                    style={{ backgroundImage: `url(${skillArt[id].image})` }}
                  >
                    <span>
                      <Play size={16} fill="white" />
                    </span>
                  </div>
                  <div className="lesson-copy">
                    <h3>{cleanTitle(lesson.title)}</h3>
                    <span className="level-chip">入门</span>
                  </div>
                  <ChevronRight size={23} />
                </Link>
              ))}
            </section>
          </>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      {children}
    </div>
  );
}
export function LessonPage() {
  const { courseId } = useParams();
  const [course, setCourse] = useState<any>(null),
    [step, setStep] = useState(1),
    [error, setError] = useState("");
  const navigate = useNavigate();
  useEffect(() => {
    const c = new AbortController();
    Promise.all([
      api("/catalog/courses/" + courseId, "GET", undefined, c.signal),
      api("/progress/recent", "GET", undefined, c.signal),
    ])
      .then(([course, p]) => {
        setCourse(course);
        setStep(
          p.items.find((i: any) => i.course_id === course.id)?.current_step ||
            1,
        );
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(friendly(e));
      });
    return () => c.abort();
  }, [courseId]);
  function close() {
    navigate(
      "/skills/" + (course?.skill_id || "home-gardening") + "?tab=tutorial",
    );
  }
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [course?.skill_id]);
  if (!course)
    return (
      <div className="page" role="status">
        {error || "课程加载中…"}
      </div>
    );
  return (
    <SkillPage fixedSkill={course.skill_id}>
      <div className="modal-backdrop" onClick={close}>
        <section
          className="lesson-modal"
          role="dialog"
          aria-modal="true"
          aria-label="课程学习"
          data-course-ready={course.id}
          data-page="lesson"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="modal-video">
            <LessonVideo
              courseId={course.id}
              step={step}
              compact
              poster={skillArt[course.skill_id].image}
            />
            <button
              className="modal-close"
              aria-label="关闭课程"
              onClick={close}
            >
              <X size={25} />
            </button>
          </div>
          <div className="modal-body">
            <span className="level-chip">入门</span>
            <h2>{cleanTitle(course.title)}</h2>
            <div className="lesson-step-control">
              <button
                aria-label="上一步"
                disabled={step === 1}
                onClick={() => setStep(step - 1)}
              >
                ←
              </button>
              <span>
                第 {step} / {course.steps.length} 步
              </span>
              <button
                aria-label="下一步"
                disabled={step === course.steps.length}
                onClick={() => setStep(step + 1)}
              >
                →
              </button>
            </div>
            <h3>{course.steps[step - 1].title}</h3>
            <p>{course.steps[step - 1].instruction}</p>
          </div>
        </section>
      </div>
    </SkillPage>
  );
}
function dismissKey(userId: string) {
  return "xiaoban-dismissed-work-" + userId;
}
function readDismissed(userId: string): string[] {
  try {
    return JSON.parse(localStorage.getItem(dismissKey(userId)) || "[]");
  } catch {
    return [];
  }
}
function useSharedWorks() {
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => {
    const c = new AbortController();
    api("/community/works?mine=false&examples=true", "GET", undefined, c.signal)
      .then((r) =>
        setItems(r.items.filter((w: any) => w.video_available && !w.is_mine)),
      )
      .catch(() => {});
    return () => c.abort();
  }, []);
  return items;
}
function useRecommendation() {
  const { library, user, loading } = useLearning();
  const items = useSharedWorks();
  if (loading) return null;
  const pool = items.filter((w) => !readDismissed(user.id).includes(w.id));
  const fresh = pool.filter(
    (w) => !library.some((s) => s.skill_id === w.skill_id),
  );
  const day = new Date().toISOString().slice(0, 10);
  const order = (id: string) =>
    Array.from(user.id + day + id).reduce(
      (n, c) => (n * 31 + c.charCodeAt(0)) >>> 0,
      0,
    );
  return (
    (fresh.length ? fresh : pool).sort(
      (a, b) => (b.likes || 0) - (a.likes || 0) || order(a.id) - order(b.id),
    )[0] || null
  );
}
export function RecommendationPage() {
  const { skillId: workId = "" } = useParams();
  const items = useSharedWorks();
  const work = items.find((w) => w.id === workId);
  const { refresh, user } = useLearning();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const navigate = useNavigate();
  async function join() {
    if (!work) return;
    setBusy(true);
    try {
      await api("/library/" + work.skill_id, "PUT");
      await refresh();
      navigate("/");
    } catch (e) {
      setError(friendly(e));
      setBusy(false);
    }
  }
  function dismiss() {
    localStorage.setItem(
      dismissKey(user.id),
      JSON.stringify([...readDismissed(user.id), workId]),
    );
    navigate("/");
  }
  return (
    <div className="recommendation-only">
      <Link className="recommend-back" to="/" aria-label="返回首页">
        <ArrowLeft size={26} />
      </Link>
      {work?.is_example && (
        <span className="recommendation-example">示例分享</span>
      )}
      {work ? (
        <SharedRecommendationVideo
          id={work.id}
          autoPlay
          poster={work.is_example ? skillArt[work.skill_id]?.image : undefined}
        />
      ) : (
        <p role="status">暂无可推荐的视频</p>
      )}
      <div className="recommendation-actions">
        <button disabled={busy || !work} onClick={() => void join()}>
          加入学习
        </button>
        <button disabled={busy || !work} onClick={dismiss}>
          不感兴趣
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
