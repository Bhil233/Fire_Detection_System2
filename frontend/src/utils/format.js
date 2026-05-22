export function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function getMonitorStatusText(status) {
  const raw = String(status ?? "").trim();
  const normalized = raw.toLowerCase();

  if (normalized === "fire" || raw === "发生火灾") {
    return "发生火灾";
  }

  if (
    normalized === "normal" ||
    normalized === "no_fire" ||
    normalized === "nofire" ||
    raw === "无火灾"
  ) {
    return "无火灾";
  }

  return raw || "-";
}

export function getMonitorStatusClass(status) {
  const statusText = getMonitorStatusText(status);
  if (statusText === "发生火灾") {
    return "monitor-status-fire";
  }
  if (statusText === "无火灾") {
    return "monitor-status-normal";
  }
  return "";
}

export function formatRatio(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const numberValue = Number(value);
  if (Number.isNaN(numberValue)) {
    return "-";
  }
  return numberValue.toFixed(3);
}

export function formatSensorValue(value, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const numberValue = Number(value);
  if (Number.isNaN(numberValue)) {
    return "-";
  }
  return numberValue.toFixed(digits);
}

export function resolveMonitorImageUrl(url, apiBase) {
  if (!url) {
    return "";
  }
  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  if (url.startsWith("/")) {
    return `${apiBase}${url}`;
  }
  return `${apiBase}/${url}`;
}
