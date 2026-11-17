import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  ArrowRight,
  ArrowLeft,
  Sprout,
  BookOpen,
  Home,
  MessageCircle,
  X,
  Volume2,
  Pause,
  Leaf,
  ShieldCheck,
  LogOut,
  Trash2,
} from "lucide-react";
import { api, newId, friendly, token } from "./api";
import { VoiceInput, speak, stopAudio } from "./voice";
import "./styles.css";
import { LessonVideo } from "./video";
import { PhotoFeedback } from "./photo";
import { AccountLogin, SkillCatalog, Community } from "./features";
import type { components } from "./generated/api";

type Course = components["schemas"]["CourseDetail"];
const COURSE = "repotting-basics";

function PlantArt({ small = false }: { small?: boolean }) {
  return (
    <div className={"plant-art " + (small ? "small" : "")} aria-hidden="true">
      <div className="sun" />
      <div className="orbit" />
      <div className="stem" />
      <div className="leaf l1" />
      <div className="leaf l2" />
      <div className="leaf l3" />
      <div className="leaf l4" />
      <div className="pot" />
      <div className="soil" />
      <span className="art-caption">一点绿意，一份从容</span>
    </div>
  );
}

function App() {
  const [authenticated, setAuthenticated] = useState(!!token()),
    [authMode, setAuthMode] = useState("dev"),
    [user, setUser] = useState<any>(null),
    [error, setError] = useState("");
  const location = useLocation(),
    navigate = useNavigate(),
    practice = location.pathname.startsWith("/practice/"),
    [size, setSize] = useState(false);
  useEffect(() => {
    stopAudio();
    document.getElementById("page-title")?.focus();
  }, [location.pathname]);
  useEffect(() => {
    if (authenticated)
      api("/me")
        .then(setUser)
        .catch((e) => setError(friendly(e)));
  }, [authenticated]);
  useEffect(() => {
    api("/auth/config")
      .then((c) => {
        setAuthMode(c.mode);
        if (c.mode === "oidc")
          api("/me")
            .then((u) => {
              setUser(u);
              setAuthenticated(true);
            })
            .catch(() => {});
      })
      .catch(() => {});
  }, []);
  async function login() {
    if (authMode === "oidc") {
      window.location.href = "/api/v1/auth/oidc/start";
      return;
    }
    try {
      const r = await api("/dev/session", "POST", {});
      sessionStorage.setItem("xiaoban-token", r.access_token);
      setAuthenticated(true);
      setError("");
    } catch (e) {
      setError(friendly(e));
    }
  }
  function logout() {
    stopAudio();
    void api("/auth/logout", "POST").catch(() => {});
    sessionStorage.removeItem("xiaoban-token");
    setAuthenticated(false);
    setUser(null);
    navigate("/");
  }
  return (
    <div className={"app " + (size ? "large-text" : "")}>
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">伴</span>
          <span>
            <b>小伴</b>
            <small>银发 AI 私教</small>
          </span>
        </Link>
        <div className="top-actions">
          <button onClick={() => setSize(!size)} aria-pressed={size}>
            大字 {size ? "开" : "关"}
          </button>
          {authenticated && (
            <button onClick={logout} aria-label="退出登录">
              <LogOut size={20} />
              <span className="desktop">退出</span>
            </button>
          )}
        </div>
      </header>
      {authenticated && user && (
        <div className="mode">
          <span className="status-dot" />
          {user.provider === "mock"
            ? "演示模式 · 规则助手"
            : "真实模型 · " + user.provider}
          <span>
            {" "}
            ·{" "}
            {user.audio_provider === "mock"
              ? "模拟语音 · 请用文字"
              : "语音由 AI 生成"}
          </span>
          {user.database === "sqlite" && (
            <span className="desktop"> · 本地 SQLite</span>
          )}
        </div>
      )}
      {!authenticated ? (
        <main className="login">
          <p className="eyebrow">把喜欢，慢慢学会</p>
          <h1>
            给生活，
            <br />
            添一点新喜欢。
          </h1>
          <PlantArt />
          <p>
            从一盆绿植开始，
            <br />
            跟着步骤学，遇到问题随时问。
          </p>
          <button className="primary" onClick={login}>
            {authMode === "oidc" ? "使用安全账号登录" : "进入本地测试"}{" "}
            <ArrowRight />
          </button>
          {authMode !== "oidc" && (
            <AccountLogin
              onLogin={(t) => {
                sessionStorage.setItem("xiaoban-token", t);
                setAuthenticated(true);
              }}
            />
          )}
          <p className="muted">
            开发账号，仅供本机内部测试。
            <br />
            课程尚未经过专业审核。
          </p>
          {error && <p role="alert">{error}</p>}
        </main>
      ) : (
        <>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <main className="main">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/skills" element={<Skills />} />
              <Route path="/community" element={<Community user={user} />} />
              <Route path="/skills/:skillId" element={<Skills />} />
              <Route path="/lessons/:courseId" element={<Lesson />} />
              <Route
                path="/practice/:sessionId"
                element={<PracticePage user={user} />}
              />
              <Route
                path="/settings"
                element={<SettingsPage logout={logout} />}
              />
              <Route
                path="*"
                element={
                  <p>
                    没有这个页面。<Link to="/">返回首页</Link>
                  </p>
                }
              />
            </Routes>
          </main>
          {!practice && (
            <>
              <Assistant user={user} />
              <nav className="bottom-nav" aria-label="主要导航">
                <Link
                  className={location.pathname === "/" ? "active" : ""}
                  to="/"
                >
                  <Home />
                  首页
                </Link>
                <Link
                  className={
                    location.pathname.includes("skills") ? "active" : ""
                  }
                  to="/skills"
                >
                  <Sprout />
                  技能广场
                </Link>
                <Link
                  className={location.pathname === "/settings" ? "active" : ""}
                  to="/settings"
                >
                  <ShieldCheck />
                  我的与隐私
                </Link>
              </nav>
            </>
          )}
        </>
      )}
    </div>
  );
}

function HomePage() {
  const [library, setLibrary] = useState<any[]>([]),
    [recent, setRecent] = useState<any[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    const load = () =>
      Promise.all([api("/library"), api("/progress/recent")])
        .then(([l, p]) => {
          setLibrary(l.items);
          setRecent(p.items);
        })
        .catch((e) => setError(friendly(e)));
    void load();
    window.addEventListener("learning-changed", load);
    return () => window.removeEventListener("learning-changed", load);
  }, []);
  return (
    <>
      <section className="welcome">
        <p className="eyebrow">每一点喜欢，都值得开始</p>
        <h1 id="page-title" tabIndex={-1} data-page="home">
          把喜欢，
          <br />
          <em>慢慢学会。</em>
        </h1>
        <p>不着急，今天也可以学一点新东西。</p>
      </section>
      <Link to={"/lessons/" + COURSE} className="hero-card">
        <div className="hero-copy">
          <span className="pill">从这里开始 · 园艺入门</span>
          <h2>
            给绿植
            <br />
            换一个新家
          </h2>
          <p>认识换盆的准备与顺序</p>
          <span className="hero-cta">
            看看这节课 <ArrowRight size={21} />
          </span>
        </div>
        <PlantArt />
      </Link>
      <div className="source-note">
        <ShieldCheck size={20} /> 平台自编 · 内部测试课程 · 未经专业审核
      </div>
      {recent.length > 0 && (
        <Link className="continue-card" to={"/lessons/" + recent[0].course_id}>
          <BookOpen />
          <div>
            <small>上次学到这里</small>
            <h3>上次课程 · 第 {recent[0].current_step} 步</h3>
            <span>继续上次的学习</span>
          </div>
          <ArrowRight />
        </Link>
      )}
      <div className="section-heading">
        <h2>我的技能库</h2>
        <Link to="/skills">
          发现新喜欢 <ArrowRight size={18} />
        </Link>
      </div>
      {library.length ? (
        library.map((item) => (
          <Link
            key={item.skill_id}
            className="library-card"
            to={"/skills/" + item.skill_id}
          >
            <span className="tile">
              <Sprout size={34} />
            </span>
            <div>
              <h3>{item.name}</h3>
              <p>继续这项兴趣的学习</p>
            </div>
            <ArrowRight />
          </Link>
        ))
      ) : (
        <div className="empty">
          <Sprout size={35} />
          <h3>从一个小小的喜欢开始</h3>
          <p>加入园艺，就能在这里找到课程。</p>
          <Link className="secondary" to="/skills">
            去看看园艺课程 <ArrowRight size={18} />
          </Link>
        </div>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <p className="footer-note">慢慢来，小伴陪您一步一步学。</p>
    </>
  );
}

function Skills() {
  const { skillId } = useParams();
  return <SkillCatalog skillId={skillId} />;
}

function Lesson() {
  const { courseId } = useParams(),
    [course, setCourse] = useState<Course | null>(null),
    [step, setStep] = useState(1),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    navigate = useNavigate();
  useEffect(() => {
    const c = new AbortController();
    Promise.all([
      api("/catalog/courses/" + courseId, "GET", undefined, c.signal),
      api("/progress/recent", "GET", undefined, c.signal),
    ])
      .then(([data, p]) => {
        setCourse(data);
        setStep(
          p.items.find((r: any) => r.course_id === courseId)?.current_step || 1,
        );
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(friendly(e));
      });
    return () => c.abort();
  }, [courseId]);
  async function choose(n: number) {
    try {
      await api("/progress/" + courseId, "PUT", {
        position_seconds: 0,
        current_step: n,
      });
      setStep(n);
    } catch (e) {
      setError(friendly(e));
    }
  }
  async function start() {
    setBusy(true);
    try {
      const r = await api("/practice/sessions", "POST", {
        course_id: courseId,
      });
      navigate("/practice/" + r.id);
    } catch (e) {
      setError(friendly(e));
      setBusy(false);
    }
  }
  if (!course)
    return (
      <div role="status">
        {error || "课程加载中…"}
        {error && <Link to="/skills">返回课程列表</Link>}
      </div>
    );
  const current = course.steps[step - 1];
  return (
    <>
      <Link className="back" to="/skills">
        <ArrowLeft size={20} /> 返回课程列表
      </Link>
      <p className="eyebrow">课程学习</p>
      <h1
        id="page-title"
        tabIndex={-1}
        data-course-ready={course.id}
        data-page="lesson"
      >
        {course.title}
      </h1>
      <p className="muted">内部测试 · 平台自编 · 未经专业审核</p>
      <div className="lesson-banner">
        <PlantArt small />
        <div>
          <Leaf />
          <h2>先了解，再动手</h2>
          <p>{course.learning_goal}</p>
        </div>
      </div>
      <section className="panel">
        <h2>开始之前</h2>
        <ul>
          {course.prerequisites.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
        <p className="notice">
          当前提供文字步骤和原创流程示意，摄像头实时分析暂未开放。
        </p>
      </section>
      <div className="section-heading">
        <h2>跟着步骤学</h2>
        <span>
          {step} / {course.steps.length}
        </span>
      </div>
      <LessonVideo courseId={course.id} step={step} />
      <div className="step-tabs">
        {course.steps.map((s) => (
          <button
            key={s.no}
            aria-pressed={step === s.no}
            className={step === s.no ? "selected" : ""}
            onClick={() => choose(s.no)}
          >
            <b>{s.no.toString().padStart(2, "0")}</b>
            {s.title}
          </button>
        ))}
      </div>
      <section className="instruction panel">
        <span className="eyebrow">第 {step} 步</span>
        <h2>{current.title}</h2>
        <p>{current.instruction}</p>
        <p className="muted">{current.explanation}</p>
        {current.safety_notes.map((s) => (
          <p className="notice" key={s}>
            {s}
          </p>
        ))}
      </section>
      <button className="primary wide" onClick={start} disabled={busy}>
        <MessageCircle size={23} />{" "}
        {busy ? "正在进入…" : "进入独立私教 · 边做边问"}{" "}
        <ArrowRight size={22} />
      </button>
      <p className="muted">无需摄像头。完成步骤时告诉私教，不会自动跳步。</p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </>
  );
}

function Chat({
  role,
  sessionId,
  user,
  onResult,
}: {
  role: "companion" | "tutor";
  sessionId?: string;
  user: any;
  onResult?: (r: any) => void;
}) {
  const [message, setMessage] = useState(""),
    [reply, setReply] = useState<any>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [rate, setRate] = useState(1),
    [speaking, setSpeaking] = useState(false),
    [autoVoice, setAutoVoice] = useState(true);
  const location = useLocation(),
    navigate = useNavigate(),
    pendingRequest = useRef<any>(null),
    controller = useRef<AbortController | null>(null),
    alive = useRef(true),
    failure = useRef(0);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      controller.current?.abort();
      stopAudio();
    };
  }, []);
  async function send(value?: string) {
    const input = (value ?? message).trim();
    if (!input || busy) return;
    stopAudio();
    setBusy(true);
    setError("");
    if (input.includes("慢")) setRate(0.75);
    const page =
      role === "tutor"
        ? "practice"
        : location.pathname.startsWith("/lessons")
          ? "lesson"
          : location.pathname.includes("skills")
            ? "skills"
            : "home";
    const request =
      pendingRequest.current?.message === input
        ? pendingRequest.current
        : {
            agent_role: role,
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
            practice_session_id: sessionId || null,
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
      if (!alive.current) return;
      setReply(r);
      setMessage("");
      pendingRequest.current = null;
      for (const action of r.ui_actions) {
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
            const video = document.querySelector<HTMLVideoElement>(
              "[data-lesson-player]",
            );
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
      if (alive.current) {
        setReply(r);
        if (r.error_code) setError(friendly(new Error(r.error_code)));
        onResult?.(r);
        window.dispatchEvent(new Event("learning-changed"));
        if (autoVoice && user && user.audio_provider !== "mock") {
          setSpeaking(true);
          try {
            await speak(r.reply.id, rate);
          } catch {
            setError("语音播放暂不可用，文字结果已保留。");
          } finally {
            if (alive.current) setSpeaking(false);
          }
        }
        failure.current = r.needs_clarification ? failure.current + 1 : 0;
      }
    } catch (e) {
      if (
        alive.current &&
        !(e instanceof DOMException && e.name === "AbortError")
      ) {
        setError(friendly(e));
        failure.current++;
      }
    } finally {
      if (alive.current) setBusy(false);
    }
  }
  return (
    <div className="chat">
      <div className="reply" role="status" aria-live="polite">
        {reply?.reply.display_text ||
          (role === "tutor"
            ? "围绕当前步骤，随时问我。做完后说“我完成了”。"
            : "可以说“我想学养花”，或“打开第一节课”。")}
        {busy && <p className="working">正在处理，请稍候…</p>}
      </div>
      {reply?.reply.id && (
        <div className="speech-controls">
          <button
            onClick={() =>
              speak(reply.reply.id, rate).catch(() =>
                setError("语音播放不可用，请阅读文字回复。"),
              )
            }
          >
            <Volume2 size={19} /> 播放回复
          </button>
          <button
            onClick={() => {
              stopAudio();
              setSpeaking(false);
            }}
          >
            <Pause size={19} /> 停止播报
          </button>
        </div>
      )}
      <div className="quick-actions">
        {reply?.choices?.map((c: any) => (
          <button
            key={c.message}
            disabled={busy}
            onClick={() => void send(c.message)}
          >
            {c.label}
          </button>
        ))}
        {(role === "tutor"
          ? ["再讲一次", "等等", "继续", "我完成了"]
          : ["我想学养花", "看看园艺有什么课", "打开第一节课"]
        ).map((s) => (
          <button key={s} disabled={busy} onClick={() => send(s)}>
            {s}
          </button>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <label htmlFor={"input-" + role}>
          {role === "tutor" ? "问问私教" : "告诉小伴您想做什么"}
        </label>
        <div className="input-row">
          <input
            id={"input-" + role}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="在这里打字…"
            maxLength={2000}
          />
          <button
            type="submit"
            className="primary"
            disabled={busy || !message.trim()}
          >
            发送
          </button>
        </div>
      </form>
      <label className="voice-option">
        <input
          type="checkbox"
          checked={autoVoice}
          onChange={(e) => setAutoVoice(e.target.checked)}
        />
        说完自动执行并播报（可关闭）
      </label>
      <div className="voice-row">
        <VoiceInput
          enabled={!!user && user.audio_provider !== "mock"}
          busy={busy || speaking}
          suspend={failure.current >= 2}
          onText={(s) => {
            if (autoVoice) void send(s);
            else {
              setMessage(s);
              setError("请核对识别文字，再点击发送。");
            }
          }}
          onError={(s) => {
            setError(s);
            failure.current++;
          }}
        />
        <span>
          录音最长 19 秒<br />
          停顿后自动发送
        </span>
      </div>
      <p className="privacy-note">
        录音将发送至服务端与语音提供商转写，不保存原始音频。仅点击开始语音对话后申请权限。
      </p>
      {(error || failure.current >= 2) && (
        <p role="alert" className="error">
          {error || "可以使用下方按钮继续。"}
        </p>
      )}
      {failure.current >= 2 && (
        <Link className="secondary" to="/skills">
          选择园艺课程
        </Link>
      )}
    </div>
  );
}

function Assistant({ user }: { user: any }) {
  const [open, setOpen] = useState(false);
  return (
    <aside
      className={"assistant " + (open ? "open" : "")}
      data-testid="companion"
    >
      {open ? (
        <section className="assistant-panel" aria-label="小伴操作助手">
          <div className="assistant-heading">
            <span className="avatar">
              <Sprout />
            </span>
            <div>
              <h2>小伴，帮您操作</h2>
              <small>加入技能 · 打开课程 · 继续学习</small>
            </div>
            <button
              aria-label="关闭小伴"
              onClick={() => {
                stopAudio();
                setOpen(false);
              }}
            >
              <X />
            </button>
          </div>
          <Chat role="companion" user={user} />
        </section>
      ) : (
        <button className="assistant-trigger" onClick={() => setOpen(true)}>
          <MessageCircle size={24} /> 找小伴帮忙
        </button>
      )}
    </aside>
  );
}

function PracticePage({ user }: { user: any }) {
  const { sessionId } = useParams(),
    [session, setSession] = useState<any>(null),
    [error, setError] = useState(""),
    navigate = useNavigate();
  async function load() {
    try {
      const r = await api("/practice/sessions/" + sessionId);
      setSession(r);
      if (r.state === "READY") {
        const active = await api(
          "/practice/sessions/" + sessionId + "/commands",
          "POST",
          { command: "START" },
        );
        setSession(active);
      }
      const aid = sessionStorage.getItem("practice-action");
      if (aid) {
        await api("/agent/ui-actions/" + aid + "/ack", "POST", {
          result: "applied",
          error_code: null,
        });
        sessionStorage.removeItem("practice-action");
      }
    } catch (e) {
      setError(friendly(e));
    }
  }
  useEffect(() => {
    load();
    return () => stopAudio();
  }, [sessionId]);
  async function exit() {
    stopAudio();
    try {
      if (session && !["COMPLETED", "ABANDONED"].includes(session.state))
        await api("/practice/sessions/" + sessionId + "/commands", "POST", {
          command: "STOP",
        });
      navigate("/lessons/" + (session?.course_id || COURSE));
    } catch (e) {
      setError(friendly(e));
    }
  }
  return (
    <>
      <button className="back" onClick={exit}>
        <ArrowLeft size={20} /> 退出陪练
      </button>
      <p className="eyebrow">独立私教 · 跟着步骤练习</p>
      <h1 id="page-title" tabIndex={-1}>
        一步一步，慢慢来。
      </h1>
      <p className="muted">没有摄像头 · 仅记录您自述的进度</p>
      {session ? (
        <>
          <section
            className="practice-current"
            data-practice-ready={sessionId}
            data-page="practice"
          >
            <span className="pill">
              {session.state === "PAUSED"
                ? "已暂停"
                : session.state === "COMPLETED"
                  ? "自述已完成"
                  : session.state === "ABANDONED"
                    ? "已结束"
                    : "练习中"}{" "}
              · 第 {session.current_step} / {session.total_steps} 步
            </span>
            <div className="practice-number">
              {String(session.current_step).padStart(2, "0")}
            </div>
            <h2>{session.step.title}</h2>
            <p>{session.step.instruction}</p>
            <div className="step-progress">
              {Array.from({ length: session.total_steps }, (_, i) => (
                <span
                  className={i + 1 <= session.current_step ? "done" : ""}
                  key={i}
                />
              ))}
            </div>
          </section>
          <p className="notice">
            沉默不会推进步骤；“我完成了”记录为用户自述，不代表动作质量核验。
          </p>
          {user?.provider !== "mock" && sessionId && (
            <PhotoFeedback sessionId={sessionId} />
          )}
          <Chat
            role="tutor"
            sessionId={sessionId}
            user={user}
            onResult={(r) => {
              if (r.practice) setSession(r.practice);
            }}
          />
        </>
      ) : (
        <p role="status">{error || "正在加载练习…"}</p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </>
  );
}

function SettingsPage({ logout }: { logout: () => void }) {
  const [confirm, setConfirm] = useState(""),
    [error, setError] = useState("");
  async function erase() {
    try {
      await api("/me/data", "DELETE", { confirmation: confirm });
      logout();
    } catch (e) {
      setError(friendly(e));
    }
  }
  return (
    <>
      <p className="eyebrow">我的与隐私</p>
      <Link className="secondary" to="/community">
        作品社区与我的投稿
      </Link>
      <h1 id="page-title" tabIndex={-1} data-page="settings">
        学习由您做主。
      </h1>
      <section className="panel">
        <ShieldCheck size={30} />
        <h2>只保存必要的学习记录</h2>
        <p>
          保存已加入的技能、课程位置与自述完成记录。不开启摄像头，不保存原始音频，不主动问候。
        </p>
        <p className="muted">
          本地测试使用开发身份；公开登录与隐私保留期限尚待确认。
        </p>
      </section>
      <section className="panel">
        <Trash2 />
        <h2>删除我的学习数据</h2>
        <p>删除技能库、进度、陪练会话与回复。此操作无法撤销。</p>
        <label htmlFor="delete-confirm">输入 DELETE_MY_DATA 确认删除</label>
        <input
          id="delete-confirm"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <button
          className="danger"
          disabled={confirm !== "DELETE_MY_DATA"}
          onClick={erase}
        >
          删除数据并退出
        </button>
        {error && <p role="alert">{error}</p>}
      </section>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
