<script setup>
defineProps({
  message: {
    type: String,
    default: "",
  },
  visible: {
    type: Boolean,
    default: false,
  },
});
</script>

<template>
  <div :class="['toast', { visible }]" role="status" aria-live="polite">
    {{ message }}
  </div>
</template>
