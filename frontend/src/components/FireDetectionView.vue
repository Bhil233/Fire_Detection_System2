<script setup>
import { computed } from "vue";

const props = defineProps({
  manualCanUpload: {
    type: Boolean,
    required: true,
  },
  manualLoading: {
    type: Boolean,
    required: true,
  },
  manualPreviewUrl: {
    type: String,
    required: true,
  },
  manualErrorText: {
    type: String,
    required: true,
  },
  manualResultText: {
    type: String,
    required: true,
  },
  manualFireDetected: {
    type: Boolean,
    required: true,
  },
  scriptPreviewUrl: {
    type: String,
    required: true,
  },
  scriptResultText: {
    type: String,
    required: true,
  },
  scriptFireDetected: {
    type: Boolean,
    required: true,
  },
  scriptErrorText: {
    type: String,
    required: true,
  },
  scriptSocketConnected: {
    type: Boolean,
    required: true,
  },
  monitorRows: {
    type: Array,
    required: true,
  },
});

const emit = defineEmits(["manual-file-change", "detect-manual-fire"]);

const chartSize = {
  width: 760,
  height: 280,
  top: 14,
  right: 16,
  bottom: 42,
  left: 42,
};

function isFireStatus(status) {
  const normalized = String(status ?? "").trim().toLowerCase();
  return normalized === "fire" || normalized === "发生火灾";
}

function isNormalStatus(status) {
  const normalized = String(status ?? "").trim().toLowerCase();
  return (
    normalized === "normal" ||
    normalized === "no_fire" ||
    normalized === "nofire" ||
    normalized === "无火灾"
  );
}

function formatDayKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function toY(value, max) {
  const plotHeight = chartSize.height - chartSize.top - chartSize.bottom;
  return chartSize.top + ((max - value) / max) * plotHeight;
}

function buildLinePath(points) {
  if (!points.length) {
    return "";
  }

  let path = `M ${points[0][0]} ${points[0][1]}`;
  for (let i = 1; i < points.length; i += 1) {
    path += ` L ${points[i][0]} ${points[i][1]}`;
  }
  return path;
}

function buildAreaPath(points, baselineY) {
  if (!points.length) {
    return "";
  }

  return `${buildLinePath(points)} L ${points[points.length - 1][0]} ${baselineY} L ${points[0][0]} ${baselineY} Z`;
}

function resolveNiceMax(value) {
  if (value <= 5) {
    return 5;
  }

  const magnitude = 10 ** Math.floor(Math.log10(value));
  const scaled = value / magnitude;

  if (scaled <= 2) {
    return 2 * magnitude;
  }
  if (scaled <= 5) {
    return 5 * magnitude;
  }
  return 10 * magnitude;
}

const fireCount = computed(() => props.monitorRows.filter((row) => isFireStatus(row.status)).length);
const normalCount = computed(() => props.monitorRows.filter((row) => isNormalStatus(row.status)).length);
const totalCount = computed(() => fireCount.value + normalCount.value);

const firePercent = computed(() => {
  if (!totalCount.value) {
    return 0;
  }
  return Math.round((fireCount.value / totalCount.value) * 100);
});

const normalPercent = computed(() => {
  if (!totalCount.value) {
    return 0;
  }
  return 100 - firePercent.value;
});

const pieStyle = computed(() => {
  if (!totalCount.value) {
    return {
      background: "conic-gradient(#cbd5e1 0deg 360deg)",
    };
  }

  const fireDegrees = (fireCount.value / totalCount.value) * 360;
  return {
    background: `conic-gradient(#dc2626 0deg ${fireDegrees}deg, #16a34a ${fireDegrees}deg 360deg)`,
  };
});

const dailySeries = computed(() => {
  const buckets = new Map();

  props.monitorRows.forEach((row) => {
    const dateValue = row.created_at || row.updated_at;
    if (!dateValue) {
      return;
    }

    const date = new Date(dateValue);
    if (Number.isNaN(date.getTime())) {
      return;
    }

    const key = formatDayKey(date);
    if (!buckets.has(key)) {
      buckets.set(key, {
        key,
        fire: 0,
        normal: 0,
      });
    }

    const target = buckets.get(key);
    if (isFireStatus(row.status)) {
      target.fire += 1;
    } else if (isNormalStatus(row.status)) {
      target.normal += 1;
    }
  });

  let list = [...buckets.values()].sort((a, b) => a.key.localeCompare(b.key));

  if (!list.length) {
    const fallback = [];
    for (let i = 6; i >= 0; i -= 1) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      fallback.push({
        key: formatDayKey(date),
        fire: 0,
        normal: 0,
      });
    }
    list = fallback;
  }

  return list.map((item) => ({
    ...item,
    label: item.key.slice(5),
  }));
});

const axisMax = computed(() => {
  const maxValue = Math.max(
    1,
    ...dailySeries.value.map((item) => Math.max(item.fire, item.normal))
  );
  return resolveNiceMax(maxValue);
});

const trendPoints = computed(() => {
  const data = dailySeries.value;
  const plotWidth = chartSize.width - chartSize.left - chartSize.right;

  return data.map((item, index) => {
    const x =
      data.length === 1
        ? chartSize.left + plotWidth / 2
        : chartSize.left + (index * plotWidth) / (data.length - 1);

    return {
      ...item,
      x,
      fireY: toY(item.fire, axisMax.value),
      normalY: toY(item.normal, axisMax.value),
    };
  });
});

const baselineY = computed(() => chartSize.height - chartSize.bottom);

const fireLinePath = computed(() =>
  buildLinePath(trendPoints.value.map((point) => [point.x, point.fireY]))
);

const normalLinePath = computed(() =>
  buildLinePath(trendPoints.value.map((point) => [point.x, point.normalY]))
);

const fireAreaPath = computed(() =>
  buildAreaPath(
    trendPoints.value.map((point) => [point.x, point.fireY]),
    baselineY.value
  )
);

const normalAreaPath = computed(() =>
  buildAreaPath(
    trendPoints.value.map((point) => [point.x, point.normalY]),
    baselineY.value
  )
);

const yTicks = computed(() => {
  const tickCount = 4;
  const ticks = [];

  for (let i = 0; i <= tickCount; i += 1) {
    const value = Math.round((axisMax.value * (tickCount - i)) / tickCount);
    ticks.push({
      value,
      y: toY(value, axisMax.value),
    });
  }

  return ticks;
});

const xLabelStep = computed(() => {
  const count = dailySeries.value.length;
  return Math.max(1, Math.ceil(count / 7));
});

const visibleXLabels = computed(() => {
  const last = trendPoints.value.length - 1;

  return trendPoints.value.filter(
    (_, index) => index === 0 || index === last || index % xLabelStep.value === 0
  );
});
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <section class="panel">
        <h2>人工图像检测</h2>
        <p class="hint">上传充电棚现场图像，重点检查充电线缆过热、插头焦化和电池堆放异常。</p>

        <input type="file" accept="image/*" @change="emit('manual-file-change', $event)" />

        <button :disabled="!manualCanUpload" @click="emit('detect-manual-fire')">
          {{ manualLoading ? "检测中..." : "开始检测" }}
        </button>
      </section>

      <section class="panel shed-elements-card">
        <h2>充电棚关键点位</h2>
        <ul class="shed-zone-list">
          <li>
            <span class="zone-name">充电桩排位区</span>
            <span class="zone-risk">关注插头温升与线缆弯折</span>
          </li>
          <li>
            <span class="zone-name">配电箱与漏保</span>
            <span class="zone-risk">关注电弧火花与异味烟雾</span>
          </li>
          <li>
            <span class="zone-name">电池临时停放区</span>
            <span class="zone-risk">关注电池鼓包与热失控迹象</span>
          </li>
          <li>
            <span class="zone-name">棚顶通风排烟区</span>
            <span class="zone-risk">关注烟气积聚和排风有效性</span>
          </li>
        </ul>
      </section>
    </aside>

    <section class="workspace">
      <div class="workspace-header">
        <h2>检测工作区</h2>
        <p class="hint">建议先核查充电桩端口、电池连接线和行车通道周边区域。</p>
      </div>

      <div class="result-grid">
        <section class="result-card">
          <h3>人工上传结果</h3>
          <div v-if="manualPreviewUrl" class="preview-wrap">
            <img :src="manualPreviewUrl" alt="人工上传预览图" />
          </div>
          <p v-else class="hint">请先在左侧上传图片。</p>
          <p v-if="manualErrorText" class="error">{{ manualErrorText }}</p>
          <p v-else-if="manualResultText" :class="manualFireDetected ? 'danger' : 'safe'">
            {{ manualResultText }}
          </p>
        </section>

        <section class="result-card">
          <h3>自动上传结果</h3>
          <p :class="scriptSocketConnected ? 'connected' : 'disconnected'">
            {{ scriptSocketConnected ? "实时连接正常" : "连接断开，正在重连..." }}
          </p>
          <div v-if="scriptPreviewUrl" class="preview-wrap">
            <img :src="scriptPreviewUrl" alt="脚本上传预览图" />
          </div>
          <p v-else class="hint">等待脚本上传图片...</p>
          <p v-if="scriptErrorText" class="error">{{ scriptErrorText }}</p>
          <p v-else-if="scriptResultText" :class="scriptFireDetected ? 'danger' : 'safe'">
            {{ scriptResultText }}
          </p>
        </section>
      </div>

      <section class="result-card checklist-card">
        <h3>充电棚巡检建议</h3>
        <ul class="checklist">
          <li>每日首检确认灭火器、消防栓与紧急断电按钮无遮挡。</li>
          <li>高峰时段重点检查车位过密、飞线充电和非标充电器接入。</li>
          <li>发现温升异常或烟雾时，立即执行断电、疏散、告警三步流程。</li>
        </ul>
      </section>

      <section class="result-card chart-section">
        <div class="chart-header">
          <h3>记录分析图</h3>
          <p class="hint">火灾情况统计</p>
        </div>

        <div class="chart-grid">
          <article class="chart-card pie-card">
            <h4>记录占比饼图</h4>
            <div class="pie-chart" :style="pieStyle">
              <div class="pie-core">
                <p>总记录</p>
                <strong>{{ totalCount }}</strong>
              </div>
            </div>
            <div class="pie-legend">
              <p><span class="legend-dot legend-fire"></span>火灾告警记录: {{ fireCount }} ({{ firePercent }}%)</p>
              <p><span class="legend-dot legend-normal"></span>正常记录: {{ normalCount }} ({{ normalPercent }}%)</p>
            </div>
          </article>

          <article class="chart-card trend-card">
            <h4>火灾趋势</h4>
            <div class="trend-wrap">
              <svg :viewBox="`0 0 ${chartSize.width} ${chartSize.height}`" role="img" aria-label="按天记录趋势图">
                <line
                  x1="42"
                  :x2="chartSize.width - chartSize.right"
                  :y1="baselineY"
                  :y2="baselineY"
                  class="axis-line"
                />
                <line
                  x1="42"
                  x2="42"
                  y1="14"
                  :y2="baselineY"
                  class="axis-line"
                />

                <g>
                  <line
                    v-for="tick in yTicks"
                    :key="`grid-${tick.value}`"
                    x1="42"
                    :x2="chartSize.width - chartSize.right"
                    :y1="tick.y"
                    :y2="tick.y"
                    class="grid-line"
                  />
                  <text
                    v-for="tick in yTicks"
                    :key="`tick-${tick.value}`"
                    x="32"
                    :y="tick.y + 4"
                    class="axis-text"
                  >
                    {{ tick.value }}
                  </text>
                </g>

                <path :d="normalAreaPath" class="normal-area" />
                <path :d="fireAreaPath" class="fire-area" />

                <path :d="normalLinePath" class="normal-line" />
                <path :d="fireLinePath" class="fire-line" />

                <circle
                  v-for="(point, index) in trendPoints"
                  :key="`fire-point-${index}`"
                  :cx="point.x"
                  :cy="point.fireY"
                  r="2.8"
                  class="fire-point"
                />
                <circle
                  v-for="(point, index) in trendPoints"
                  :key="`normal-point-${index}`"
                  :cx="point.x"
                  :cy="point.normalY"
                  r="2.8"
                  class="normal-point"
                />

                <text
                  v-for="point in visibleXLabels"
                  :key="`x-${point.key}`"
                  :x="point.x"
                  :y="chartSize.height - 12"
                  class="axis-text axis-x"
                >
                  {{ point.label }}
                </text>
              </svg>
            </div>
            <div class="line-legend">
              <span><i class="legend-line fire-line-dot"></i>火灾告警记录</span>
              <span><i class="legend-line normal-line-dot"></i>正常记录</span>
            </div>
          </article>
        </div>
      </section>
    </section>
  </div>
</template>
