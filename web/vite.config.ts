import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

// SPA build for Cloudflare Pages. Output -> dist/ (static). The Svelte app's
// adapter-cloudflare is gone; deep-link routing is handled by public/_redirects.
export default defineConfig({
	plugins: [vue()],
	resolve: {
		alias: {
			$lib: fileURLToPath(new URL('./src/lib', import.meta.url))
		}
	}
});
