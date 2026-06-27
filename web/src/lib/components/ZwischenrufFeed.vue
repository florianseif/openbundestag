<script setup lang="ts">
import { ref, watch } from 'vue';
import { api } from '$lib/api';
import { i18n } from '$lib/i18n';
import { partyColor } from '$lib/format';
import type { ZwischenrufSample } from '$lib/types';

const { callerParty = '', targetParty = '', terms = undefined } = defineProps<{
	callerParty?: string;
	targetParty?: string;
	terms?: number[];
}>();

const keyword = ref('');
const items = ref<ZwischenrufSample[]>([]);
const loading = ref(false);
let debounce: ReturnType<typeof setTimeout>;

async function load() {
	loading.value = true;
	try {
		items.value = await api.zwischenrufe.samples({
			keyword: keyword.value || undefined,
			callerParty: callerParty || undefined,
			targetParty: targetParty || undefined,
			terms,
			limit: 60
		});
	} finally {
		loading.value = false;
	}
}

// Watch keyword (reactive ref) + all props for changes; debounce 300ms.
watch([keyword, () => callerParty, () => targetParty, () => terms], () => {
	clearTimeout(debounce);
	debounce = setTimeout(load, 300);
}, { immediate: true });

function highlight(text: string | null, kw: string): string {
	if (!text || !kw.trim()) return text ?? '';
	const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
	return text.replace(new RegExp(`(${escaped})`, 'gi'), '<mark>$1</mark>');
}

function fmtDate(d: string): string {
	return new Date(d).toLocaleDateString(i18n.lang === 'de' ? 'de-DE' : 'en-GB', {
		day: '2-digit', month: 'short', year: 'numeric'
	});
}
</script>

<template>
	<div class="feed">
		<div class="controls">
			<div class="search-wrap">
				<svg class="search-icon" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
					<circle cx="6" cy="6" r="4.5" stroke="currentColor" stroke-width="1.4"/>
					<line x1="9.5" y1="9.5" x2="13" y2="13" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
				</svg>
				<input
					class="search"
					type="search"
					:placeholder="i18n.t('zw_search_ph')"
					v-model="keyword"
				/>
			</div>
		</div>

		<div v-if="loading" class="loading">
			<span class="pulse-dot"></span>
		</div>
		<p v-else-if="items.length === 0" class="empty">{{ i18n.t('zw_no_results') }}</p>
		<ul v-else class="list">
			<li
				v-for="item in items"
				:key="item.id"
				class="card"
				:style="{ '--cc': partyColor(item.caller_party ?? ''), '--tc': partyColor(item.target_speaker_party ?? '') }"
			>
				<div class="meta">
					<span v-if="item.caller_name" class="caller" :style="{ color: partyColor(item.caller_party ?? '') }">{{ item.caller_name }}</span>
					<span v-if="item.caller_party" class="party-tag" :style="{ background: partyColor(item.caller_party) }">{{ item.caller_party }}</span>
					<template v-if="item.target_speaker_party">
						<span class="arrow">→</span>
						<span class="target-tag" :style="{ color: partyColor(item.target_speaker_party) }">{{ item.target_speaker_party }}</span>
					</template>
					<span class="date">{{ fmtDate(item.date) }}</span>
					<span class="term">WP {{ item.electoral_term }}</span>
				</div>
				<blockquote v-if="item.text" class="quote" v-html="`„${highlight(item.text, keyword)}&quot;`"></blockquote>
			</li>
		</ul>
	</div>
</template>

<style scoped>
.feed {
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.controls {
	display: flex;
	gap: 0.7rem;
	flex-wrap: wrap;
}

.search-wrap {
	position: relative;
	flex: 1;
	min-width: 200px;
}
.search-icon {
	position: absolute;
	left: 0.9rem;
	top: 50%;
	transform: translateY(-50%);
	color: var(--ink-3);
	pointer-events: none;
}
.search {
	width: 100%;
	padding: 0.6rem 0.9rem 0.6rem 2.4rem;
	background: var(--surface-2);
	border: 1px solid var(--line-2);
	border-radius: 999px;
	color: var(--ink);
	font: inherit;
	font-size: 0.88rem;
	outline: none;
	transition: border-color 0.2s;
}
.search:focus {
	border-color: var(--accent);
	box-shadow: 0 0 0 3px rgba(107, 145, 255, 0.15);
}
.search::placeholder {
	color: var(--ink-3);
}

.loading {
	display: flex;
	justify-content: center;
	padding: 2rem;
}
.pulse-dot {
	width: 10px;
	height: 10px;
	border-radius: 50%;
	background: var(--accent);
	animation: pulse 1.4s ease infinite;
}
@keyframes pulse {
	0%   { box-shadow: 0 0 0 0 rgba(107, 145, 255, 0.55); }
	70%  { box-shadow: 0 0 0 10px rgba(107, 145, 255, 0); }
	100% { box-shadow: 0 0 0 0 rgba(107, 145, 255, 0); }
}

.empty {
	color: var(--ink-3);
	text-align: center;
	padding: 2rem;
	font-size: 0.88rem;
}

.list {
	list-style: none;
	padding: 0;
	margin: 0;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.card {
	padding: 0.75rem 1rem;
	background: var(--surface-2);
	border: 1px solid var(--line);
	border-left: 3px solid var(--cc, var(--accent));
	border-radius: 10px;
	transition: border-color 0.2s, background 0.2s;
}
.card:hover {
	background: var(--surface-3);
	border-color: var(--line-2);
	border-left-color: var(--cc, var(--accent));
}

.meta {
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: 0.4rem;
	margin-bottom: 0.45rem;
	font-size: 0.78rem;
}
.caller {
	font-weight: 700;
}
.party-tag {
	font-size: 0.68rem;
	font-weight: 700;
	padding: 0.15rem 0.45rem;
	border-radius: 999px;
	color: #fff;
	mix-blend-mode: normal;
	filter: brightness(0.95) saturate(1.1);
}
.arrow {
	color: var(--ink-3);
}
.target-tag {
	font-size: 0.75rem;
	font-weight: 600;
}
.date,
.term {
	color: var(--ink-3);
	font-size: 0.72rem;
	margin-left: auto;
}
.term {
	margin-left: 0;
}

.quote {
	margin: 0;
	font-size: 0.88rem;
	line-height: 1.5;
	color: var(--ink-2);
	font-style: italic;
	padding-left: 0.6rem;
	border-left: 2px solid var(--line-2);
}
.quote :deep(mark) {
	background: rgba(107, 145, 255, 0.25);
	color: var(--accent);
	border-radius: 3px;
	padding: 0 2px;
	font-style: normal;
}
</style>
