# Edge AI Gateway Console Vue Frontend

Vue 3 + Vite frontend for the Edge AI Gateway.

The legacy static frontend in `../web` is intentionally left in place. This module is the Vue replacement and can be built and deployed independently.

## Development

Start the gateway first, then run:

```bash
cd web-vue
npm install
npm run dev
```

The Vite dev server listens on `0.0.0.0:8080` and proxies `/health` and `/v1` to `http://127.0.0.1:8000` by default.

Override the dev proxy target when needed:

```bash
VITE_DEV_GATEWAY_TARGET=http://192.168.1.20:8000 npm run dev
```

## Production Build

```bash
cd web-vue
npm run build
```

Serve the generated `dist/` directory with any static server, or build the Docker image.

## Docker

The container serves the built frontend with nginx and proxies API requests to a service named `gateway` on port `8000`.

```bash
cd web-vue
docker build -t edge-ai-gateway-console .
docker run --rm -p 8080:80 edge-ai-gateway-console
```

In a compose deployment, put `frontend` and `gateway` on the same Docker network so nginx can resolve `http://gateway:8000`.

## Module Layout

- `src/api`: gateway fetch clients and SSE parsing.
- `src/composables`: stateful business logic for status, chat, recording, and toast messages.
- `src/panels`: top-level feature panels.
- `src/components`: reusable layout/status widgets.
- `src/utils`: audio, file, and binary helpers.
