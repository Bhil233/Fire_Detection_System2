import { ref } from "vue";
import { apiBase, getWsBaseUrl } from "../config/api";

export function useScriptSocket() {
  const scriptPreviewUrl = ref("");
  const scriptResultText = ref("");
  const scriptFireDetected = ref(false);
  const scriptErrorText = ref("");
  const scriptSocketConnected = ref(false);

  let scriptSocket = null;
  let scriptReconnectTimer = null;

  function scheduleScriptReconnect() {
    if (scriptReconnectTimer !== null) {
      return;
    }
    scriptReconnectTimer = window.setTimeout(() => {
      scriptReconnectTimer = null;
      connectScriptSocket();
    }, 2000);
  }

  function connectScriptSocket() {
    if (
      scriptSocket &&
      (scriptSocket.readyState === WebSocket.OPEN ||
        scriptSocket.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    const wsBase = getWsBaseUrl(apiBase);
    const wsUrl = `${wsBase}/ws/script/latest-upload-image`;
    const socket = new WebSocket(wsUrl);
    scriptSocket = socket;

    socket.onopen = () => {
      scriptSocketConnected.value = true;
      scriptErrorText.value = "";
    };

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type !== "script_upload_result") {
          return;
        }
        if (payload.image_data_url) {
          scriptPreviewUrl.value = payload.image_data_url;
        }
        scriptFireDetected.value = !!payload.fire_detected;
        scriptResultText.value = payload.result_text || "";
        scriptErrorText.value = "";
      } catch {
        scriptErrorText.value = "脚本模块消息解析失败";
      }
    };

    socket.onclose = () => {
      if (scriptSocket === socket) {
        scriptSocket = null;
        scriptSocketConnected.value = false;
        scheduleScriptReconnect();
      }
    };

    socket.onerror = () => {
      socket.close();
    };
  }

  function cleanupScriptSocket() {
    if (scriptSocket) {
      scriptSocket.close();
      scriptSocket = null;
    }
    if (scriptReconnectTimer !== null) {
      clearTimeout(scriptReconnectTimer);
      scriptReconnectTimer = null;
    }
  }

  return {
    scriptPreviewUrl,
    scriptResultText,
    scriptFireDetected,
    scriptErrorText,
    scriptSocketConnected,
    connectScriptSocket,
    cleanupScriptSocket,
  };
}
