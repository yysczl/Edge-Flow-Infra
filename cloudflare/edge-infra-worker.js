const FRONTEND_ORIGIN = "https://edge-flow-ai.vercel.app";
const API_ORIGIN = "https://edge-infra-api-origin.ianyys.com";

const API_PATHS = ["/health", "/v1/"];

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const targetOrigin = isApiPath(url.pathname) ? API_ORIGIN : FRONTEND_ORIGIN;
    const targetUrl = new URL(request.url);
    const target = new URL(targetOrigin);

    targetUrl.protocol = target.protocol;
    targetUrl.hostname = target.hostname;
    targetUrl.port = target.port;

    return fetch(new Request(targetUrl, request));
  },
};

function isApiPath(pathname) {
  return API_PATHS.some((path) => {
    if (path.endsWith("/")) {
      return pathname.startsWith(path);
    }
    return pathname === path;
  });
}
