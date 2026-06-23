import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const gatewayTarget = process.env.VITE_DEV_GATEWAY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 8080,
    proxy: {
      "/health": {
        target: gatewayTarget,
        changeOrigin: true,
      },
      "/v1": {
        target: gatewayTarget,
        changeOrigin: true,
      },
    },
  },
});
