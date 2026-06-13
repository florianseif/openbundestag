// The explorer is a live client app talking to the HF Space API (which may be
// cold-starting). Render it client-side so we can show a "waking" state instead
// of blocking SSR on a sleeping backend.
export const ssr = false;
export const prerender = false;
