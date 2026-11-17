export function token() {
  return sessionStorage.getItem("xiaoban-token") || "";
}
export async function api(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<any> {
  const response = await fetch("/api/v1" + path, {
    method,
    signal,
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
    throw new Error(error.error?.code || "NETWORK_ERROR");
  }
  return response.status === 204 ? undefined : response.json();
}
export const newId = () => crypto.randomUUID();
export function friendly(error: unknown) {
  const code = error instanceof Error ? error.message : "";
  if (code === "PROVIDER_AUTH")
    return "模型服务认证失败，请检查后端提供商密钥及权限。";
  if (code === "PROVIDER_QUOTA")
    return "模型额度不足或请求受限，请检查提供商账户。";
  if (code.includes("AUTH") || code.includes("TOKEN"))
    return "登录已失效，请退出后重新登录。";
  if (code.includes("AUDIO") || code.includes("ASR"))
    return "语音暂时不可用，可以在下方打字。";
  if (code.includes("RATE") || code.includes("BUDGET"))
    return "本次使用额度已到，请稍后再试。";
  return "暂时没能完成，请检查服务连接后重试。";
}
