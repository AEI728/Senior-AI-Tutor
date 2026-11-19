import { Assistant } from "../features/assistant/Assistant";
import { useEffect, useState } from "react";
import {
  Link,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Sprout,
  Home,
  Sparkles,
  MessageCircle,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { api, friendly } from "../lib/api";
import { stopAudio } from "../features/voice/VoiceInput";
import "../styles/base.css";
import "../styles/app.css";
import {
  HomePage,
  SkillsPage,
  SkillPage,
  LessonPage,
  RecommendationPage,
} from "../pages/LearningPages";
import { prepareSession } from "../lib/session";
import { AudioDebugPage } from "../pages/AudioDebug";
import { LearningProvider } from "../features/learning/LearningProvider";
import { SharePage } from "../features/community/Community";
import { PracticePage } from "../pages/Practice";

export function App() {
  const [user, setUser] = useState<any>(null),
    [mode, setMode] = useState("dev"),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const [fontLevel, setFontLevel] = useState(() => {
    const n = Number(localStorage.getItem("xiaoban-font-level"));
    return Number.isInteger(n) && n >= 0 && n <= 4 ? n : 0;
  });
  const location = useLocation(),
    navigate = useNavigate();
  async function initialize() {
    setLoading(true);
    setError("");
    try {
      const r = await prepareSession();
      setMode(r.mode);
      setUser(r.user);
    } catch (e) {
      setError(friendly(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void initialize();
  }, []);
  useEffect(() => {
    stopAudio(false);
    document.getElementById("page-title")?.focus();
  }, [location.pathname]);
  function resize(next: number) {
    const value = Math.max(0, Math.min(4, next));
    setFontLevel(value);
    localStorage.setItem("xiaoban-font-level", String(value));
  }
  async function resetView() {
    stopAudio();
    sessionStorage.removeItem("xiaoban-token");
    setUser(null);
    navigate("/");
    await initialize();
  }
  return (
    <div
      className={
        "app reference-ui font-level-" +
        fontLevel +
        (location.pathname !== "/" ? " hide-font-controls" : "") +
        (location.pathname.startsWith("/recommend/")
          ? " on-recommendation"
          : "") +
        (location.pathname === "/share" || location.pathname === "/community"
          ? " on-reels"
          : "")
      }
      data-font-level={fontLevel}
    >
      <header
        className={
          "topbar " +
          (location.pathname === "/" ? "home-topbar" : "utility-topbar")
        }
      >
        <Link to="/" className="brand">
          <span className="brand-mark">伴</span>
          <span>
            <b>小伴</b>
            <small>银发 AI 私教</small>
          </span>
        </Link>
        {location.pathname === "/" && <Link className="settings-link" to="/settings" aria-label="学习设置">
          <ShieldCheck size={20} />
        </Link>}
        <div className="font-controls" role="group" aria-label="字号调节">
          <span className="font-label">字号</span>
          <button
            aria-label="缩小字号"
            disabled={fontLevel === 0}
            onClick={() => resize(fontLevel - 1)}
          >
            A−
          </button>
          <output aria-live="polite" aria-label="当前字号">
            {100 + fontLevel * 10}%
          </output>
          <button
            aria-label="放大字号"
            disabled={fontLevel === 4}
            onClick={() => resize(fontLevel + 1)}
          >
            A＋
          </button>
        </div>
      </header>
      {!user ? (
        <main className="main session-status">
          <p role="status">
            {loading ? "正在准备，请稍候…" : error || "请先完成账户授权。"}
          </p>
          {!loading && (
            <button
              className="primary"
              onClick={() => {
                if (mode === "oidc")
                  window.location.href = "/api/v1/auth/oidc/start";
                else void initialize();
              }}
            >
              {mode === "oidc" ? "继续授权" : "重新连接"}
            </button>
          )}
        </main>
      ) : (
        <LearningProvider key={user.id} user={user}>
          <main className="main">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/skills" element={<SkillsPage />} />
              <Route path="/skills/:skillId" element={<SkillPage />} />
              <Route path="/lessons/:courseId" element={<LessonPage />} />
              <Route path="/practice" element={<PracticePage />} />
              <Route path="/practice/:sessionId" element={<PracticePage />} />
              <Route
                path="/recommend/:skillId"
                element={<RecommendationPage />}
              />
              <Route path="/share" element={<SharePage />} />
              <Route path="/community" element={<SharePage />} />
              {mode === "dev" && <Route path="/debug/audio" element={<AudioDebugPage />} />}
              <Route
                path="/settings"
                element={
                  <SettingsPage user={user} logout={() => void resetView()} />
                }
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
          {!location.pathname.startsWith("/recommend/") && (
            <Assistant user={user} />
          )}
          <nav className="bottom-nav" aria-label="主要导航">
            <Link className={location.pathname === "/" ? "active" : ""} to="/">
              <Home />
              首页
            </Link>
            <Link
              className={
                location.pathname.includes("skills") ||
                location.pathname.includes("lessons")
                  ? "active"
                  : ""
              }
              to="/skills"
            >
              <Sprout />
              技能广场
            </Link>
            <span className="nav-microphone-slot" aria-hidden="true" />
            <Link
              className={
                location.pathname.startsWith("/practice") ? "active" : ""
              }
              to="/practice"
            >
              <Sparkles />
              陪练
            </Link>
            <Link
              className={
                ["/share", "/community"].includes(location.pathname)
                  ? "active"
                  : ""
              }
              to="/share"
            >
              <MessageCircle />
              分享
            </Link>
          </nav>
        </LearningProvider>
      )}
    </div>
  );
}

function SettingsPage({ logout, user }: { logout: () => void; user: any }) {
  const [confirm, setConfirm] = useState(""),
    [error, setError] = useState("");
  async function erase() {
    try {
      await api("/me/data", "DELETE", { confirmation: confirm });
      localStorage.removeItem("xiaoban-backgrounds-" + user.id);
      logout();
    } catch (e) {
      setError(friendly(e));
    }
  }
  return (
    <div className="page learning-settings-page">
      <section className="panel" data-page="settings">
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
          删除我的学习记录
        </button>
        {error && <p role="alert">{error}</p>}
      </section>
    </div>
  );
}
