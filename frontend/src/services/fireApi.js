async function parseJsonResponse(response) {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function appendOptionalNumber(formData, key, value) {
  if (value === null || value === undefined || value === "") {
    return;
  }
  formData.append(key, String(value));
}

export async function detectManualFireRequest(apiBase, file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${apiBase}/api/manual/detect-fire`, {
    method: "POST",
    body: formData,
  });
  const data = await parseJsonResponse(response);
  if (!response.ok) {
    throw new Error(data.detail || "检测失败，请稍后重试。");
  }
  return data;
}

export async function fetchMonitorRecords(apiBase, sortBy, sortOrder) {
  const query = new URLSearchParams({
    sort_by: sortBy,
    sort_order: sortOrder,
  });
  const response = await fetch(`${apiBase}/api/data-monitor/records?${query.toString()}`);
  const data = await parseJsonResponse(response);
  if (!response.ok) {
    throw new Error(data.detail || "获取数据监控列表失败");
  }
  return Array.isArray(data) ? data : [];
}

export async function createMonitorRecord(apiBase, remark, sceneImageFile, metadata = {}) {
  const formData = new FormData();
  formData.append("remark", remark);
  if (sceneImageFile) {
    formData.append("scene_image", sceneImageFile);
  }
  appendOptionalNumber(formData, "yolo_confidence", metadata.yolo_confidence);
  appendOptionalNumber(formData, "temperature", metadata.temperature);
  appendOptionalNumber(formData, "smoke_density", metadata.smoke_density);

  const response = await fetch(`${apiBase}/api/data-monitor/records`, {
    method: "POST",
    body: formData,
  });
  const data = await parseJsonResponse(response);
  if (!response.ok) {
    throw new Error(data.detail || "新增失败");
  }
  return data;
}

export async function updateMonitorRecord(apiBase, recordId, remark, sceneImageFile, metadata = {}) {
  const formData = new FormData();
  formData.append("remark", remark);
  if (sceneImageFile) {
    formData.append("scene_image", sceneImageFile);
  }
  appendOptionalNumber(formData, "yolo_confidence", metadata.yolo_confidence);
  appendOptionalNumber(formData, "temperature", metadata.temperature);
  appendOptionalNumber(formData, "smoke_density", metadata.smoke_density);

  const response = await fetch(`${apiBase}/api/data-monitor/records/${recordId}`, {
    method: "PUT",
    body: formData,
  });
  const data = await parseJsonResponse(response);
  if (!response.ok) {
    throw new Error(data.detail || "更新失败");
  }
  return data;
}

export async function deleteMonitorRecordRequest(apiBase, recordId) {
  const response = await fetch(`${apiBase}/api/data-monitor/records/${recordId}`, {
    method: "DELETE",
  });
  const data = await parseJsonResponse(response);
  if (!response.ok) {
    throw new Error(data.detail || "删除失败");
  }
  return data;
}
