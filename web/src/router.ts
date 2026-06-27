import { createRouter, createWebHistory } from 'vue-router';

// Routes mirror the old SvelteKit file-routing. Views are lazy-loaded so each
// chunk splits like the old per-route bundles. SSR is off (this is an SPA).
export const router = createRouter({
	history: createWebHistory(),
	routes: [
		{ path: '/', name: 'home', component: () => import('./views/Home.vue') },
		{ path: '/explore', name: 'explore', component: () => import('./views/Explore.vue') },
		{ path: '/about', name: 'about', component: () => import('./views/About.vue') },
		{
			path: '/architecture',
			name: 'architecture',
			component: () => import('./views/Architecture.vue')
		},
		{ path: '/beifall', name: 'beifall', component: () => import('./views/Beifall.vue') },
		{
			path: '/zwischenrufe',
			name: 'zwischenrufe',
			component: () => import('./views/Zwischenrufe.vue')
		}
	],
	scrollBehavior() {
		return { top: 0 };
	}
});
