import { api, ApiError, token } from "./api";
let pending: Promise<any> | null = null;
export async function prepareSession() {
  if (pending) return pending;
  pending = (async () => {
    const config = await api("/auth/config");
    if (token() || config.mode === "oidc") {
      try {
        return { user: await api("/me"), mode: config.mode };
      } catch (e) {
        if (!(e instanceof ApiError) || e.status !== 401) throw e;
        sessionStorage.removeItem("xiaoban-token");
      }
    }
    if (config.mode === "oidc") return { user: null, mode: "oidc" };
    const session = await api("/dev/session", "POST", {});
    sessionStorage.setItem("xiaoban-token", session.access_token);
    return { user: await api("/me"), mode: config.mode };
  })();
  try {
    return await pending;
  } finally {
    pending = null;
  }
}
