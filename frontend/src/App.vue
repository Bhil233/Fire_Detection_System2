<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import NavigationMenu from "./components/NavigationMenu.vue";
import FireDetectionView from "./components/FireDetectionView.vue";
import DataMonitorView from "./components/DataMonitorView.vue";
import { apiBase } from "./config/api";
import { useScriptSocket } from "./composables/useScriptSocket";
import {
  createMonitorRecord,
  deleteMonitorRecordRequest,
  detectManualFireRequest,
  fetchMonitorRecords,
  updateMonitorRecord,
} from "./services/fireApi";
import {
  formatDateTime,
  formatRatio,
  formatSensorValue,
  getMonitorStatusClass,
  getMonitorStatusText,
  resolveMonitorImageUrl,
} from "./utils/format";

const activeMenu = ref("fire_detection");

const manualSelectedFile = ref(null);
const manualPreviewUrl = ref("");
const manualLoading = ref(false);
const manualResultText = ref("");
const manualFireDetected = ref(false);
const manualFireConfidence = ref(null);
const manualErrorText = ref("");
const manualCanUpload = computed(
  () => !!manualSelectedFile.value && !manualLoading.value
);

const {
  scriptPreviewUrl,
  scriptResultText,
  scriptFireDetected,
  scriptFireConfidence,
  scriptErrorText,
  scriptSocketConnected,
  connectScriptSocket,
  cleanupScriptSocket,
} = useScriptSocket();

const monitorRows = ref([]);
const monitorLoading = ref(false);
const monitorSubmitting = ref(false);
const monitorErrorText = ref("");
const monitorSortBy = ref("created_at");
const monitorSortOrder = ref("desc");
const monitorForm = ref({
  id: null,
  scene_image_file: null,
  scene_image_preview: "",
  yolo_confidence: "",
  temperature: "",
  smoke_density: "",
  remark: "",
});

const monitorTotalCount = computed(() => monitorRows.value.length);
const monitorFireCount = computed(
  () =>
    monitorRows.value.filter((row) => {
      const status = String(row.status ?? "").trim().toLowerCase();
      return status === "fire" || status === "发生火灾";
    }).length
);
const monitorNormalCount = computed(
  () =>
    monitorRows.value.filter((row) => {
      const status = String(row.status ?? "").trim().toLowerCase();
      return (
        status === "normal" ||
        status === "no_fire" ||
        status === "nofire" ||
        status === "无火灾"
      );
    }).length
);
const latestRecordTime = computed(() => {
  if (!monitorRows.value.length) {
    return "暂无记录";
  }
  const first = monitorRows.value[0];
  return formatDateTime(first.updated_at || first.created_at);
});
const systemStatusText = computed(() =>
  scriptSocketConnected.value ? "边缘脚本在线" : "边缘脚本重连中"
);
const alertLevelText = computed(() => {
  if (manualFireDetected.value || scriptFireDetected.value || monitorFireCount.value > 0) {
    return "高风险";
  }
  return "低风险";
});

function onManualFileChange(event) {
  const file = event.target.files?.[0] || null;
  manualSelectedFile.value = file;
  manualResultText.value = "";
  manualErrorText.value = "";
  manualFireDetected.value = false;
  manualFireConfidence.value = null;

  if (manualPreviewUrl.value) {
    URL.revokeObjectURL(manualPreviewUrl.value);
    manualPreviewUrl.value = "";
  }

  if (file) {
    manualPreviewUrl.value = URL.createObjectURL(file);
  }
}

async function detectManualFire() {
  if (!manualSelectedFile.value) {
    return;
  }

  manualLoading.value = true;
  manualResultText.value = "";
  manualErrorText.value = "";
  manualFireDetected.value = false;
  manualFireConfidence.value = null;

  try {
    const data = await detectManualFireRequest(apiBase, manualSelectedFile.value);
    manualResultText.value = data.result_text || "";
    manualFireDetected.value = !!data.fire_detected;
    manualFireConfidence.value = data.fire_confidence ?? null;

    if (manualFireDetected.value) {
      window.alert("警告：检测到火灾，请立即处理并上报。");
    }
  } catch (error) {
    manualErrorText.value = error.message || "请求失败";
  } finally {
    manualLoading.value = false;
  }
}

function resetMonitorForm() {
  if (monitorForm.value.scene_image_preview?.startsWith("blob:")) {
    URL.revokeObjectURL(monitorForm.value.scene_image_preview);
  }
  monitorForm.value = {
    id: null,
    scene_image_file: null,
    scene_image_preview: "",
    yolo_confidence: "",
    temperature: "",
    smoke_density: "",
    remark: "",
  };
}

async function loadMonitorRecords() {
  monitorLoading.value = true;
  monitorErrorText.value = "";

  try {
    monitorRows.value = await fetchMonitorRecords(
      apiBase,
      monitorSortBy.value,
      monitorSortOrder.value
    );
  } catch (error) {
    monitorErrorText.value = error.message || "请求失败";
    monitorRows.value = [];
  } finally {
    monitorLoading.value = false;
  }
}

function onMonitorImageChange(event) {
  const file = event.target.files?.[0] || null;
  if (monitorForm.value.scene_image_preview?.startsWith("blob:")) {
    URL.revokeObjectURL(monitorForm.value.scene_image_preview);
  }
  monitorForm.value.scene_image_file = file;
  if (file) {
    monitorForm.value.scene_image_preview = URL.createObjectURL(file);
  } else {
    monitorForm.value.scene_image_preview = "";
  }
}

function onMonitorRemarkChange(value) {
  monitorForm.value.remark = value;
}

function onMonitorMetadataChange(key, value) {
  monitorForm.value[key] = value;
}

function onMonitorSortByChange(value) {
  monitorSortBy.value = value;
  void loadMonitorRecords();
}

function onMonitorSortOrderChange(value) {
  monitorSortOrder.value = value;
  void loadMonitorRecords();
}

async function saveMonitorRecord() {
  monitorSubmitting.value = true;
  monitorErrorText.value = "";

  try {
    const remark = monitorForm.value.remark.trim();
    const editingId = monitorForm.value.id;
    const isEdit = editingId !== null;
    if (!isEdit && !monitorForm.value.scene_image_file) {
      throw new Error("新增记录必须上传 jpg 图片");
    }

    if (isEdit) {
      await updateMonitorRecord(
        apiBase,
        editingId,
        remark,
        monitorForm.value.scene_image_file,
        {
          yolo_confidence: monitorForm.value.yolo_confidence,
          temperature: monitorForm.value.temperature,
          smoke_density: monitorForm.value.smoke_density,
        }
      );
    } else {
      await createMonitorRecord(apiBase, remark, monitorForm.value.scene_image_file, {
        yolo_confidence: monitorForm.value.yolo_confidence,
        temperature: monitorForm.value.temperature,
        smoke_density: monitorForm.value.smoke_density,
      });
    }

    resetMonitorForm();
    await loadMonitorRecords();
  } catch (error) {
    monitorErrorText.value = error.message || "请求失败";
  } finally {
    monitorSubmitting.value = false;
  }
}

function startEditMonitorRecord(record) {
  if (monitorForm.value.scene_image_preview?.startsWith("blob:")) {
    URL.revokeObjectURL(monitorForm.value.scene_image_preview);
  }
  monitorForm.value = {
    id: record.id,
    scene_image_file: null,
    scene_image_preview: resolveMonitorImageUrl(record.scene_image_url, apiBase),
    yolo_confidence: record.yolo_confidence ?? "",
    temperature: record.temperature ?? "",
    smoke_density: record.smoke_density ?? "",
    remark: record.remark ?? "",
  };
}

function cancelEditMonitorRecord() {
  resetMonitorForm();
}

async function deleteMonitorRecord(recordId) {
  if (!window.confirm("确认删除这条监控记录吗？")) {
    return;
  }

  monitorErrorText.value = "";
  try {
    await deleteMonitorRecordRequest(apiBase, recordId);
    await loadMonitorRecords();
    if (monitorForm.value.id === recordId) {
      resetMonitorForm();
    }
  } catch (error) {
    monitorErrorText.value = error.message || "请求失败";
  }
}

function resolveMonitorImageUrlWithBase(url) {
  return resolveMonitorImageUrl(url, apiBase);
}

watch(
  activeMenu,
  (menu) => {
    if (menu === "data_monitor") {
      void loadMonitorRecords();
    }
  },
  { immediate: true }
);

onMounted(() => {
  connectScriptSocket();
  void loadMonitorRecords();
});

onBeforeUnmount(() => {
  if (manualPreviewUrl.value) {
    URL.revokeObjectURL(manualPreviewUrl.value);
  }
  cleanupScriptSocket();
  if (monitorForm.value.scene_image_preview?.startsWith("blob:")) {
    URL.revokeObjectURL(monitorForm.value.scene_image_preview);
  }
});
</script>

<template>
  <main class="page">
    <header class="hero">
      <div class="hero-main">
        <p class="hero-kicker">E-BIKE CHARGING SHED SAFETY CENTER</p>
        <h1 class="title">AI智能电动车充电棚火灾监测平台</h1>
        <p class="hero-description">
          面向电动车充电棚场景，覆盖充电桩阵列、配电箱、线缆桥架与电池停放位，实现实时图像识别与台账监控。
        </p>
        <div class="hero-tags">
          <span class="hero-tag">区域: 充电棚A区</span>
          <span class="hero-tag">连接: {{ systemStatusText }}</span>
          <span class="hero-tag">预警等级: {{ alertLevelText }}</span>
        </div>
      </div>
      <div class="hero-stats">
        <article class="stat-card">
          <p class="stat-label">监控总记录</p>
          <p class="stat-value">{{ monitorTotalCount }}</p>
        </article>
        <article class="stat-card stat-card-warn">
          <p class="stat-label">火灾告警记录</p>
          <p class="stat-value">{{ monitorFireCount }}</p>
        </article>
        <article class="stat-card stat-card-safe">
          <p class="stat-label">正常记录</p>
          <p class="stat-value">{{ monitorNormalCount }}</p>
        </article>
        <article class="stat-card">
          <p class="stat-label">最近更新</p>
          <p class="stat-value stat-time">{{ latestRecordTime }}</p>
        </article>
      </div>
    </header>

    <section class="menu-shell">
      <NavigationMenu v-model:active-menu="activeMenu" />
    </section>

    <FireDetectionView
      v-if="activeMenu === 'fire_detection'"
      :manual-can-upload="manualCanUpload"
      :manual-loading="manualLoading"
      :manual-preview-url="manualPreviewUrl"
      :manual-error-text="manualErrorText"
      :manual-result-text="manualResultText"
      :manual-fire-detected="manualFireDetected"
      :manual-fire-confidence="manualFireConfidence"
      :script-preview-url="scriptPreviewUrl"
      :script-result-text="scriptResultText"
      :script-fire-detected="scriptFireDetected"
      :script-fire-confidence="scriptFireConfidence"
      :script-error-text="scriptErrorText"
      :script-socket-connected="scriptSocketConnected"
      :monitor-rows="monitorRows"
      @manual-file-change="onManualFileChange"
      @detect-manual-fire="detectManualFire"
    />

    <DataMonitorView
      v-else
      :monitor-form="monitorForm"
      :monitor-loading="monitorLoading"
      :monitor-submitting="monitorSubmitting"
      :monitor-error-text="monitorErrorText"
      :monitor-rows="monitorRows"
      :monitor-sort-by="monitorSortBy"
      :monitor-sort-order="monitorSortOrder"
      :format-date-time="formatDateTime"
      :format-ratio="formatRatio"
      :format-sensor-value="formatSensorValue"
      :get-monitor-status-text="getMonitorStatusText"
      :get-monitor-status-class="getMonitorStatusClass"
      :resolve-monitor-image-url="resolveMonitorImageUrlWithBase"
      @monitor-image-change="onMonitorImageChange"
      @monitor-remark-change="onMonitorRemarkChange"
      @monitor-metadata-change="onMonitorMetadataChange"
      @save-monitor-record="saveMonitorRecord"
      @cancel-edit-monitor-record="cancelEditMonitorRecord"
      @load-monitor-records="loadMonitorRecords"
      @monitor-sort-by-change="onMonitorSortByChange"
      @monitor-sort-order-change="onMonitorSortOrderChange"
      @start-edit-monitor-record="startEditMonitorRecord"
      @delete-monitor-record="deleteMonitorRecord"
    />
  </main>
</template>
