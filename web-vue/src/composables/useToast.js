import { ref } from "vue";

export function useToast() {
  const message = ref("");
  const visible = ref(false);
  let timer = 0;

  function toast(nextMessage) {
    window.clearTimeout(timer);
    message.value = nextMessage;
    visible.value = true;
    timer = window.setTimeout(() => {
      visible.value = false;
    }, 2600);
  }

  return {
    message,
    visible,
    toast,
  };
}
