<script setup>
import { computed } from "vue";

const props = defineProps({
  modelValue: {
    type: String,
    required: true,
  },
});

const emit = defineEmits(["update:modelValue", "save", "refresh"]);

const value = computed({
  get: () => props.modelValue,
  set: (nextValue) => emit("update:modelValue", nextValue),
});
</script>

<template>
  <section class="connection-bar" aria-label="Connection">
    <label class="field wide-field">
      <span>Base URL</span>
      <input
        v-model="value"
        type="url"
        placeholder="Same origin proxy"
        spellcheck="false"
      >
    </label>
    <button class="primary-action" type="button" @click="$emit('save')">
      Save
    </button>
    <button type="button" @click="$emit('refresh')">
      Refresh
    </button>
  </section>
</template>
