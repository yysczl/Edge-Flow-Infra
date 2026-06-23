<script setup>
defineProps({
  tabs: {
    type: Array,
    required: true,
  },
  activeTab: {
    type: String,
    required: true,
  },
});

defineEmits(["select"]);
</script>

<template>
  <nav class="tabs" aria-label="Console sections">
    <button
      v-for="tab in tabs"
      :key="tab.id"
      :class="['tab', { active: activeTab === tab.id }]"
      type="button"
      @click="$emit('select', tab.id)"
    >
      {{ tab.label }}
    </button>
  </nav>
</template>
