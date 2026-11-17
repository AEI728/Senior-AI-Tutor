import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, friendly, token } from "./api";

export function AccountLogin({
  onLogin,
}: {
  onLogin: (token: string) => void;
}) {
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [register, setRegister] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api(
        "/auth/" + (register ? "register" : "login"),
        "POST",
        { username, password },
      );
      onLogin(r.access_token);
    } catch (e) {
      setError(
        e instanceof Error && e.message === "USERNAME_TAKEN"
          ? "该账号已存在。"
          : e instanceof Error && e.message === "INVALID_CREDENTIALS"
            ? "账号或密码不正确。"
            : friendly(e),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>{register ? "创建独立账号" : "登录独立账号"}</h2>
      <p className="muted">
        可在连接同一后端的设备上恢复学习数据。当前用于内部测试。
      </p>
      <form onSubmit={submit}>
        <label>
          账号（字母、数字或下划线）
          <input
            required
            minLength={3}
            maxLength={40}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
          />
        </label>
        <label>
          密码（至少10位）
          <input
            required
            type="password"
            minLength={10}
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={register ? "new-password" : "current-password"}
          />
        </label>
        <div className="button-row">
          <button className="primary" disabled={busy}>
            {register ? "注册并进入" : "登录"}
          </button>
          <button type="button" onClick={() => setRegister(!register)}>
            {register ? "已有账号，去登录" : "没有账号，去注册"}
          </button>
        </div>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}

export function SkillCatalog({ skillId }: { skillId?: string }) {
  const [items, setItems] = useState<any[]>([]),
    [courses, setCourses] = useState<Record<string, any[]>>({}),
    [error, setError] = useState("");
  async function load() {
    try {
      const r = await api("/catalog/skills");
      setItems(r.items);
      const entries = await Promise.all(
        r.items.map(async (s: any) => [
          s.id,
          (await api("/catalog/skills/" + s.id + "/courses")).items,
        ]),
      );
      setCourses(Object.fromEntries(entries));
    } catch (e) {
      setError(friendly(e));
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function toggle(s: any) {
    try {
      await api("/library/" + s.id, s.joined ? "DELETE" : "PUT");
      void load();
      window.dispatchEvent(new Event("learning-changed"));
    } catch (e) {
      setError(friendly(e));
    }
  }
  return (
    <>
      <p className="eyebrow">发现新喜欢</p>
      <h1 id="page-title" tabIndex={-1} data-page="skills">
        技能广场
      </h1>
      <p className="muted">所有课程为平台自编内部草稿，未经专业审核。</p>
      {items
        .filter((s) => !skillId || s.id === skillId)
        .map((s) => (
          <section className="panel" key={s.id}>
            <h2>{s.name}</h2>
            <button
              className={s.joined ? "secondary" : "primary"}
              onClick={() => toggle(s)}
            >
              {s.joined ? "已加入 · 点击移除" : "加入技能库"}
            </button>
            {courses[s.id]?.map((c) => (
              <article className="catalog-lesson" key={c.id}>
                <h3>{c.title}</h3>
                <p>{c.learning_goal}</p>
                <Link
                  className="secondary"
                  to={"/lessons/" + encodeURIComponent(c.id)}
                >
                  查看课程
                </Link>
              </article>
            ))}
          </section>
        ))}
      {skillId && !items.some((s) => s.id === skillId) && (
        <p>
          未找到该技能。<Link to="/skills">查看全部技能</Link>
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </>
  );
}

export function Community({ user }: { user: any }) {
  const [file, setFile] = useState<File | null>(null),
    [items, setItems] = useState<any[]>([]),
    [mine, setMine] = useState(false),
    [title, setTitle] = useState(""),
    [description, setDescription] = useState(""),
    [course, setCourse] = useState("repotting-basics"),
    [courses, setCourses] = useState<any[]>([]),
    [confirmed, setConfirmed] = useState(false),
    [notice, setNotice] = useState(""),
    [queue, setQueue] = useState<any[]>([]);
  async function load() {
    try {
      setItems((await api("/community/works?mine=" + mine)).items);
      if (user?.is_admin) setQueue((await api("/community/moderation")).items);
    } catch (e) {
      setNotice(friendly(e));
    }
  }
  useEffect(() => {
    void load();
  }, [mine, user?.is_admin]);
  useEffect(() => {
    api("/catalog/skills")
      .then(async (r) => {
        const all = await Promise.all(
          r.items.map((s: any) => api("/catalog/skills/" + s.id + "/courses")),
        );
        setCourses(all.flatMap((r) => r.items));
      })
      .catch((e) => setNotice(friendly(e)));
  }, []);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const submitted = await api("/community/works", "POST", {
        title,
        description,
        course_id: course,
        publish_confirmation: "SHARE_THIS_WORK",
      });
      if (file) {
        const form = new FormData();
        form.append("file", file);
        try {
          await api("/community/works/" + submitted.id + "/image", "PUT", form);
        } catch {
          setNotice("文字已提交，图片未上传成功；可撤下后重新提交。");
          setMine(true);
          void load();
          return;
        }
      }
      setFile(null);
      setTitle("");
      setDescription("");
      setConfirmed(false);
      setNotice("已提交审核，尚未公开。");
      setMine(true);
      void load();
    } catch (e) {
      setNotice(friendly(e));
    }
  }
  async function remove(id: string) {
    try {
      await api("/community/works/" + id, "DELETE");
      void load();
    } catch (e) {
      setNotice(friendly(e));
    }
  }
  async function report(id: string) {
    try {
      await api("/community/works/" + id + "/report", "POST");
      setNotice("已举报，作品已转回审核。");
      void load();
    } catch (e) {
      setNotice(friendly(e));
    }
  }
  async function moderate(id: string, decision: string) {
    try {
      await api("/community/moderation/" + id, "POST", { decision });
      void load();
    } catch (e) {
      setNotice(friendly(e));
    }
  }
  return (
    <>
      <p className="eyebrow">一起分享学习收获</p>
      <h1 id="page-title" tabIndex={-1} data-page="community">
        作品社区
      </h1>
      <p className="notice">
        仅向连接当前服务的用户展示审核通过的文字作品。请勿填写姓名、电话、地址或他人隐私。当前无支付、私聊或附近的人。
      </p>
      <section className="panel">
        <h2>分享学习记录</h2>
        <form onSubmit={submit}>
          <label>
            对应课程
            <select value={course} onChange={(e) => setCourse(e.target.value)}>
              {courses.map((c) => (
                <option value={c.id} key={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
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
            附上原创作品照片（可选，4MiB以内；上传会去除位置信息）
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => {
                const selected = e.target.files?.[0];
                if (selected && selected.size <= 4 * 1024 * 1024)
                  setFile(selected);
                else {
                  setFile(null);
                  setNotice("图片不可超过4MiB。");
                }
              }}
            />
          </label>
          <label className="voice-option">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            确认内容由我创作，审核后可向当前服务用户展示
          </label>
          <button className="primary" disabled={!confirmed}>
            确认提交审核
          </button>
        </form>
      </section>
      <div className="button-row">
        <button aria-pressed={!mine} onClick={() => setMine(false)}>
          审核通过的作品
        </button>
        <button aria-pressed={mine} onClick={() => setMine(true)}>
          我的投稿
        </button>
      </div>
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      {!items.length && <p className="empty">这里还没有作品。</p>}
      {items.map((w) => (
        <article className="panel" key={w.id}>
          <span className="pill">
            {{ PENDING: "待审核", APPROVED: "审核通过", REJECTED: "未通过" }[
              w.state as string
            ] || w.state}
          </span>
          <h2>{w.title}</h2>
          <p className="work-text">{w.description}</p>
          {w.image_available && <WorkImage id={w.id} />}{" "}
          {mine ? (
            <button onClick={() => remove(w.id)}>撤下并删除</button>
          ) : (
            <button onClick={() => report(w.id)}>举报并交由管理员复核</button>
          )}
        </article>
      ))}
      {user?.is_admin && (
        <section className="panel">
          <h2>管理员审核队列</h2>
          {queue.map((w) => (
            <article key={w.id}>
              <h3>{w.title}</h3>
              <p className="work-text">{w.description}</p>
              {w.image_available && <WorkImage id={w.id} />}
              <div className="button-row">
                <button onClick={() => moderate(w.id, "approve")}>
                  通过审核
                </button>
                <button onClick={() => moderate(w.id, "reject")}>拒绝</button>
              </div>
            </article>
          ))}
        </section>
      )}
    </>
  );
}

function WorkImage({ id }: { id: string }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let active = true,
      value = "";
    fetch("/api/v1/community/works/" + id + "/image", {
      headers: { Authorization: "Bearer " + token() },
    })
      .then((r) => {
        if (!r.ok) throw new Error("IMAGE_UNAVAILABLE");
        return r.blob();
      })
      .then((b) => {
        value = URL.createObjectURL(b);
        if (active) setUrl(value);
      })
      .catch(() => {});
    return () => {
      active = false;
      if (value) URL.revokeObjectURL(value);
    };
  }, [id]);
  return url ? (
    <img
      src={url}
      alt="用户原创作品"
      className="work-image"
    />
  ) : (
    <p>照片暂未加载。</p>
  );
}
