export function token() {
  return sessionStorage.getItem("xiaoban-token") || "";
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<any> {
  const controller = new AbortController();
  let timedOut = false;
  const relay = () => controller.abort(signal?.reason);
  if (signal?.aborted) relay();
  else signal?.addEventListener("abort", relay, { once: true });
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, 45000);
  try {
    const response = await fetch("/api/v1" + path, {
      method,
      signal: controller.signal,
      credentials: "same-origin",
      headers: {
        Authorization: "Bearer " + token(),
        ...(body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
      },
      body:
        body === undefined
          ? undefined
          : body instanceof FormData
            ? body
            : JSON.stringify(body),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(error.error?.code || "NETWORK_ERROR", response.status);
    }
    return response.status === 204 ? undefined : await response.json();
  } catch (e) {
    if (timedOut) throw new ApiError("REQUEST_TIMEOUT", 0);
    throw e;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", relay);
  }
}
export const newId = () => crypto.randomUUID();
export function friendly(error: unknown) {
  const code = error instanceof Error ? error.message : "";
  if (code === "REQUEST_TIMEOUT")
    return "这次响应有些慢，请稍后重试。";
  if (code === "PROVIDER_AUTH")
    return "模型服务认证失败，请检查后端提供商密钥及权限。";
  if (code === "PROVIDER_QUOTA")
    return "模型额度不足或请求受限，请检查提供商账户。";
  if (code.includes("AUTH") || code.includes("TOKEN"))
    return "连接已失效，请刷新页面后重试。";
  if (code.includes("AUDIO") || code.includes("ASR"))
    return "语音识别服务暂时不可用，请稍后重试。";
  if (code.includes("VISION"))
    return "图像理解服务暂时不可用，请稍后重试。";
  if (code.includes("RATE") || code.includes("BUDGET"))
    return "本次使用额度已到，请稍后再试。";
  return "暂时没能完成，请检查服务连接后重试。";
}
