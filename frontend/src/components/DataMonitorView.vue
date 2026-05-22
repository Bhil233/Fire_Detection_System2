<script setup>
import { computed } from "vue";

const props = defineProps({
  monitorForm: {
    type: Object,
    required: true,
  },
  monitorLoading: {
    type: Boolean,
    required: true,
  },
  monitorSubmitting: {
    type: Boolean,
    required: true,
  },
  monitorErrorText: {
    type: String,
    required: true,
  },
  monitorRows: {
    type: Array,
    required: true,
  },
  monitorSortBy: {
    type: String,
    required: true,
  },
  monitorSortOrder: {
    type: String,
    required: true,
  },
  formatDateTime: {
    type: Function,
    required: true,
  },
  formatRatio: {
    type: Function,
    required: true,
  },
  formatSensorValue: {
    type: Function,
    required: true,
  },
  getMonitorStatusText: {
    type: Function,
    required: true,
  },
  getMonitorStatusClass: {
    type: Function,
    required: true,
  },
  resolveMonitorImageUrl: {
    type: Function,
    required: true,
  },
});

const emit = defineEmits([
  "monitor-image-change",
  "monitor-remark-change",
  "monitor-metadata-change",
  "save-monitor-record",
  "cancel-edit-monitor-record",
  "load-monitor-records",
  "monitor-sort-by-change",
  "monitor-sort-order-change",
  "start-edit-monitor-record",
  "delete-monitor-record",
]);

const fireCount = computed(
  () =>
    props.monitorRows.filter((row) => {
      const status = String(row.status ?? "").trim().toLowerCase();
      return status === "fire" || status === "发生火灾";
    }).length
);

const normalCount = computed(
  () =>
    props.monitorRows.filter((row) => {
      const status = String(row.status ?? "").trim().toLowerCase();
      return (
        status === "normal" ||
        status === "no_fire" ||
        status === "nofire" ||
        status === "无火灾"
      );
    }).length
);

const riskLevel = computed(() => (fireCount.value > 0 ? "需重点复核" : "整体稳定"));
</script>

<template>
  <section class="monitor-page">
    <header class="monitor-header">
      <h2>充电棚数据监控中心</h2>
      <p class="hint">集中管理现场台账、状态记录与图片证据，方便追溯充电棚告警事件全过程。</p>
    </header>

    <section class="monitor-overview">
      <article class="overview-item">
        <p class="overview-label">总记录数</p>
        <p class="overview-value">{{ monitorRows.length }}</p>
      </article>
      <article class="overview-item overview-item-warn">
        <p class="overview-label">火灾告警数</p>
        <p class="overview-value">{{ fireCount }}</p>
      </article>
      <article class="overview-item overview-item-safe">
        <p class="overview-label">正常记录数</p>
        <p class="overview-value">{{ normalCount }}</p>
      </article>
      <article class="overview-item">
        <p class="overview-label">风险态势</p>
        <p class="overview-value overview-text">{{ riskLevel }}</p>
      </article>
    </section>

    <section class="monitor-form-card">
      <h3>{{ monitorForm.id === null ? "新增监控记录" : `编辑记录 #${monitorForm.id}` }}</h3>

      <div class="monitor-form-grid">
        <label class="form-item">
          <span>现场图片 (jpg)</span>
          <input
            type="file"
            accept=".jpg,.jpeg,image/jpeg,image/jpg"
            @change="emit('monitor-image-change', $event)"
          />
        </label>

        <label class="form-item">
          <span>YOLO置信度 (0.0-1.0)</span>
          <input
            type="number"
            min="0"
            max="1"
            step="0.001"
            :value="monitorForm.yolo_confidence"
            placeholder="可选"
            @input="emit('monitor-metadata-change', 'yolo_confidence', $event.target.value)"
          />
        </label>

        <label class="form-item">
          <span>温度</span>
          <input
            type="number"
            step="0.01"
            :value="monitorForm.temperature"
            placeholder="可选"
            @input="emit('monitor-metadata-change', 'temperature', $event.target.value)"
          />
        </label>

        <label class="form-item">
          <span>烟雾浓度</span>
          <input
            type="number"
            step="0.01"
            :value="monitorForm.smoke_density"
            placeholder="可选"
            @input="emit('monitor-metadata-change', 'smoke_density', $event.target.value)"
          />
        </label>

        <p class="hint form-tip">状态和AI置信度由系统自动识别，附加数据为空时不会发送给AI。</p>

        <label class="form-item full">
          <span>备注</span>
          <textarea
            :value="monitorForm.remark"
            rows="2"
            placeholder="可选，补充现场说明"
            @input="emit('monitor-remark-change', $event.target.value)"
          ></textarea>
        </label>

        <div v-if="monitorForm.scene_image_preview" class="form-item full">
          <span>图片预览</span>
          <img class="table-image" :src="monitorForm.scene_image_preview" alt="现场图片预览" />
        </div>
      </div>

      <div class="monitor-actions">
        <button :disabled="monitorSubmitting" @click="emit('save-monitor-record')">
          {{ monitorSubmitting ? "提交中..." : monitorForm.id === null ? "新增记录" : "更新记录" }}
        </button>
        <button
          v-if="monitorForm.id !== null"
          type="button"
          class="ghost-btn"
          :disabled="monitorSubmitting"
          @click="emit('cancel-edit-monitor-record')"
        >
          取消编辑
        </button>
        <button type="button" class="ghost-btn" :disabled="monitorLoading" @click="emit('load-monitor-records')">
          {{ monitorLoading ? "刷新中..." : "刷新列表" }}
        </button>
      </div>
    </section>

    <p v-if="monitorErrorText" class="error">{{ monitorErrorText }}</p>

    <section class="result-card">
      <h3>监控数据列表</h3>
      <div class="monitor-sort-bar">
        <label class="sort-item">
          <span>排序字段</span>
          <select :value="monitorSortBy" @change="emit('monitor-sort-by-change', $event.target.value)">
            <option value="id">ID</option>
            <option value="status">状态</option>
            <option value="fire_confidence">AI置信度</option>
            <option value="yolo_confidence">YOLO置信度</option>
            <option value="temperature">温度</option>
            <option value="smoke_density">烟雾浓度</option>
            <option value="remark">备注</option>
            <option value="created_at">创建时间</option>
            <option value="updated_at">更新时间</option>
          </select>
        </label>
        <label class="sort-item">
          <span>排序方式</span>
          <select :value="monitorSortOrder" @change="emit('monitor-sort-order-change', $event.target.value)">
            <option value="desc">降序</option>
            <option value="asc">升序</option>
          </select>
        </label>
      </div>

      <p v-if="monitorLoading" class="hint">加载中...</p>
      <p v-else-if="!monitorRows.length" class="hint">暂无数据。</p>

      <div v-else class="table-wrap">
        <table class="monitor-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>现场图片</th>
              <th>状态</th>
              <th>AI置信度</th>
              <th>YOLO置信度</th>
              <th>温度</th>
              <th>烟雾浓度</th>
              <th>备注</th>
              <th>创建时间</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in monitorRows" :key="row.id">
              <td>{{ row.id }}</td>
              <td>
                <img class="table-image" :src="resolveMonitorImageUrl(row.scene_image_url)" alt="现场图片" />
                <p class="image-path">{{ row.scene_image_path }}</p>
              </td>
              <td>
                <span :class="['status-pill', getMonitorStatusClass(row.status)]">
                  {{ getMonitorStatusText(row.status) }}
                </span>
              </td>
              <td>{{ formatRatio(row.fire_confidence) }}</td>
              <td>{{ formatRatio(row.yolo_confidence) }}</td>
              <td>{{ formatSensorValue(row.temperature) }}</td>
              <td>{{ formatSensorValue(row.smoke_density) }}</td>
              <td>{{ row.remark || "-" }}</td>
              <td>{{ formatDateTime(row.created_at) }}</td>
              <td>{{ formatDateTime(row.updated_at) }}</td>
              <td class="table-actions">
                <button type="button" class="table-btn" @click="emit('start-edit-monitor-record', row)">编辑</button>
                <button type="button" class="table-btn danger-btn" @click="emit('delete-monitor-record', row.id)">
                  删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
