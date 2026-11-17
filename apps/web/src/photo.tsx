import { useState } from "react";
import { api, friendly } from "./api";
export function PhotoFeedback({ sessionId }: { sessionId: string }) {
  const [consent, setConsent] = useState(false),
    [feedback, setFeedback] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function send(file?: File) {
    if (!file || !consent) return;
    if (file.size > 4 * 1024 * 1024) {
      setError("照片请小于4MiB。");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await api(
        "/practice/sessions/" + sessionId + "/photo-feedback",
        "POST",
        form,
      );
      setFeedback(r.feedback);
    } catch (e) {
      setError(friendly(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>看照片，聊当前步骤</h2>
      <p className="muted">
        照片会发送给当前模型提供商，不保存原图。仅给本张照片的参考反馈，不判断动作达标，也不会自动推进。
      </p>
      <label className="voice-option">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
        />
        我同意发送本次选择的照片，请勿包含他人或隐私信息
      </label>
      <label>
        选择照片（4MiB以内）
        <input
          disabled={!consent || busy}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={(e) => {
            void send(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </label>
      {busy && <p role="status">正在查看照片…</p>}
      {feedback && (
        <p className="notice" role="status">
          {feedback}
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}
