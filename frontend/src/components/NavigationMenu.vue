<script setup>
defineProps({
  activeMenu: {
    type: String,
    required: true,
  },
});

const emit = defineEmits(["update:activeMenu"]);

function switchMenu(menu) {
  emit("update:activeMenu", menu);
}
</script>

<template>
  <nav class="menu" aria-label="主导航">
    <button
      type="button"
      class="menu-btn"
      :class="{ active: activeMenu === 'fire_detection' }"
      @click="switchMenu('fire_detection')"
    >
      火灾检测工作台
    </button>
    <button
      type="button"
      class="menu-btn"
      :class="{ active: activeMenu === 'data_monitor' }"
      @click="switchMenu('data_monitor')"
    >
      充电棚数据监控
    </button>
  </nav>
</template>
