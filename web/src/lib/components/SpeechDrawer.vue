<script setup lang="ts">
// onclose callback prop → emit('close')
import { ref, watch } from 'vue';
import { api } from '$lib/api';
import type { Filters, SpeechPage } from '$lib/types';
import { i18n } from '$lib/i18n';
import { partyColor, formatDate } from '$lib/format';

const props = defineProps<{
	query: Filters | null;
	title: string;
}>();

// Replaces the `onclose: () => void` callback prop.
const emit = defineEmits<{ close: [] }>();

const page = ref<SpeechPage | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

watch(() => props.query, (q) => {
	page.value = null;
	error.value = null;
	if (!q) return;
	loading.value = true;
	api
		.speeches(q, 15, 0)
		.then((p) => (page.value = p))
		.catch((e: Error) => (error.value = e.message))
		.finally(() => (loading.value = false));
}, { immediate: true });
</script>

<template>
	<Transition name="scrim">
		<div
			v-if="query"
			class="scrim"
			role="presentation"
			@click="emit('close')"
		></div>
	</Transition>

	<Transition name="drawer">
		<aside v-if="query" class="drawer" aria-label="Speech detail">
			<header>
				<div>
					<div class="eyebrow">{{ title }}</div>
					<h3>{{ i18n.t('read_passage') }}</h3>
				</div>
				<button class="x" @click="emit('close')" :aria-label="i18n.t('close')">✕</button>
			</header>

			<p class="soon">{{ i18n.t('drilldown_soon') }}</p>

			<div v-if="loading" class="skeleton">
				<div v-for="i in 4" :key="i" class="sk"></div>
			</div>
			<p v-else-if="error" class="err">{{ error }}</p>
			<ul v-else-if="page" class="list">
				<li v-for="s in page.items" :key="s.id">
					<div class="meta">
						<span class="pill" :style="{ background: partyColor(s.party) }"></span>
						<strong>{{ s.politician }}</strong>
						<span class="muted">· {{ s.party }}</span>
						<span class="muted date">{{ formatDate(s.date, i18n.lang) }}</span>
					</div>
					<p v-if="s.snippet" class="snippet">…{{ s.snippet }}…</p>
					<p v-else class="snippet muted">
						{{ s.position_long ?? s.position_short }} · WP {{ s.electoral_term }}
					</p>
				</li>
			</ul>
		</aside>
	</Transition>
</template>

<style scoped>
/* ponytail: approximated Svelte transition:fade on scrim */
.scrim-enter-active { transition: opacity 0.2s; }
.scrim-leave-active { transition: opacity 0.2s; }
.scrim-enter-from   { opacity: 0; }
.scrim-leave-to     { opacity: 0; }

/* ponytail: approximated Svelte transition:fly x=420 on drawer */
.drawer-enter-active { transition: transform 0.32s var(--ease, ease), opacity 0.32s; }
.drawer-leave-active { transition: transform 0.25s var(--ease, ease), opacity 0.25s; }
.drawer-enter-from   { transform: translateX(420px); opacity: 0; }
.drawer-leave-to     { transform: translateX(420px); opacity: 0; }

.scrim {
	position: fixed;
	inset: 0;
	background: rgba(20, 18, 14, 0.42);
	z-index: 40;
}
.drawer {
	position: fixed;
	top: 0;
	right: 0;
	bottom: 0;
	width: min(440px, 92vw);
	background: var(--card);
	border-left: 1px solid var(--line);
	box-shadow: var(--shadow-lg);
	z-index: 41;
	padding: 1.4rem 1.4rem 2rem;
	overflow-y: auto;
}
header {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 1rem;
}
h3 {
	margin: 0.1rem 0 0;
}
.x {
	font-size: 1rem;
	background: none;
	border: 1px solid var(--line-2);
	border-radius: 999px;
	width: 34px;
	height: 34px;
	cursor: pointer;
	color: var(--ink-2);
	flex: none;
}
.soon {
	font-size: 0.82rem;
	color: var(--ink-3);
	background: var(--paper-2);
	border-radius: var(--radius-sm);
	padding: 0.6rem 0.75rem;
	margin: 0.9rem 0 1.2rem;
}
.list {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 0.9rem;
}
.list li {
	border-bottom: 1px solid var(--line);
	padding-bottom: 0.9rem;
}
.meta {
	display: flex;
	align-items: center;
	gap: 0.4rem;
	font-size: 0.85rem;
	flex-wrap: wrap;
}
.pill {
	width: 10px;
	height: 10px;
	border-radius: 3px;
	flex: none;
}
.muted {
	color: var(--ink-3);
}
.date {
	margin-left: auto;
}
.snippet {
	margin: 0.4rem 0 0;
	font-size: 0.88rem;
	line-height: 1.55;
	color: var(--ink-2);
}
.err {
	color: #b3261e;
	font-size: 0.85rem;
}
.skeleton {
	display: flex;
	flex-direction: column;
	gap: 0.8rem;
}
.sk {
	height: 48px;
	border-radius: 8px;
	background: linear-gradient(90deg, var(--paper-2), var(--line), var(--paper-2));
	background-size: 200% 100%;
	animation: shimmer 1.3s infinite;
}
@keyframes shimmer {
	to {
		background-position: -200% 0;
	}
}
</style>
