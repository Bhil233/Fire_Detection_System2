function trimTrailingSlash(value) {
  return String(value || "").replace(/\/+$/, "");
}

function resolveApiBaseFromEnv() {
  const envBase = trimTrailingSlash(import.meta.env.VITE_API_BASE);
  if (envBase) {
    return envBase;
  }

  if (import.meta.env.DEV) {
    return "";
  }

  if (typeof window === "undefined") {
    return "";
  }

  const apiPort = String(import.meta.env.VITE_API_PORT || "").trim();
  if (!apiPort) {
    return window.location.origin;
  }

  const protocol = window.location.protocol || "http:";
  const hostname = window.location.hostname || "127.0.0.1";
  return `${protocol}//${hostname}:${apiPort}`;
}

export const apiBase = resolveApiBaseFromEnv();

export function getWsBaseUrl(httpBase = apiBase) {
  const base = trimTrailingSlash(httpBase);

  if (!base && typeof window !== "undefined") {
    return window.location.origin.replace(/^http/i, "ws");
  }

  if (base.startsWith("https://")) {
    return `wss://${base.slice("https://".length)}`;
  }

  if (base.startsWith("http://")) {
    return `ws://${base.slice("http://".length)}`;
  }

  return base;
}
