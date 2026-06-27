<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { api } from '$lib/api';
import type { Filters, SpeechItem, SpeechFull } from '$lib/types';
import { i18n } from '$lib/i18n';
import { partyColor, formatDate } from '$lib/format';

const { filters } = defineProps<{ filters: Filters }>();

const PAGE = 20;
const offset = ref(0);
const items = ref<SpeechItem[]>([]);
const total = ref(0);
const loading = ref(false);
const openId = ref<number | null>(null);
const fullCache = ref<Record<number, SpeechFull>>({});
const fullLoading = ref<number | null>(null);

// Derived filter key to detect any filter change.
const filterKey = computed(() =>
	[filters.word, ...filters.parties, ...filters.terms.map(String),
	 String(filters.politician_id), filters.date_from, filters.date_to].join('|')
);

// Reset page when filters change.
watch(filterKey, () => {
	offset.value = 0;
});

// Fetch whenever filterKey or offset changes.
watch([filterKey, offset], () => {
	if (!filters.word.trim()) { items.value = []; total.value = 0; return; }
	loading.value = true;
	openId.value = null;
	Promise.all([api.speeches(filters, PAGE, offset.value), api.total(filters)])
		.then(([page, tot]) => { items.value = page.items; total.value = tot.count; })
		.catch(() => {})
		.finally(() => (loading.value = false));
}, { immediate: true });

const pages = computed(() => Math.ceil(total.value / PAGE));
const currentPage = computed(() => Math.floor(offset.value / PAGE) + 1);

async function toggle(id: number) {
	if (openId.value === id) { openId.value = null; return; }
	openId.value = id;
	if (!fullCache.value[id]) {
		fullLoading.value = id;
		try { fullCache.value[id] = await api.speech(id); } catch { /* ignore */ }
		finally { fullLoading.value = null; }
	}
}

async function download(item: SpeechItem) {
	if (!fullCache.value[item.id]) {
		try { fullCache.value[item.id] = await api.speech(item.id); } catch { /* ignore */ }
	}
	const full = fullCache.value[item.id];
	const body = full?.speech_content ?? item.snippet ?? '';
	const rule = '─'.repeat(64);
	const lines = [
		'OpenBundestag — Plenarrede', rule,
		`Sprecher:    ${item.politician}`,
		`Partei:      ${item.party}`,
		`Datum:       ${formatDate(item.date, i18n.lang)}`,
		`Wahlperiode: ${item.electoral_term}`,
		`Sitzung:     ${item.session}`,
		rule, '', body, '',
		rule, 'Quelle: Deutscher Bundestag · bundestag.de/services/opendata'
	].join('\n');
	const a = document.createElement('a');
	a.href = URL.createObjectURL(new Blob([lines], { type: 'text/plain;charset=utf-8' }));
	a.download = `rede-${item.id}-${item.politician.replace(/\s+/g, '-').toLowerCase()}.txt`;
	a.click();
	URL.revokeObjectURL(a.href);
}

function segs(text: string) {
	const w = filters.word.trim();
	if (!w) return [{ t: text, hit: false }];
	const re = new RegExp(`(${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
	return text.split(re).map((t) => ({ t, hit: t.toLowerCase() === w.toLowerCase() }));
}

function protocolUrl(item: SpeechItem) {
	return `https://dserver.bundestag.de/btp/${String(item.electoral_term).padStart(2, '0')}/${item.session}.pdf`;
}
</script>

<template>
	<div class="table-wrap">
		<template v-if="loading">
			<div class="loading">
				<div v-for="i in 5" :key="i" class="sk" :style="`--d:${(i - 1) * 60}ms`"></div>
			</div>
		</template>
		<template v-else-if="!items.length">
			<p class="empty">{{ i18n.t('no_results', { word: filters.word }) }}</p>
		</template>
		<template v-else>
			<div class="count">{{ total.toLocaleString(i18n.lang === 'de' ? 'de-DE' : 'en-GB') }} {{ i18n.t('matching_speeches') }}</div>

			<ul class="list">
				<li
					v-for="(s, idx) in items"
					:key="s.id"
					class="row"
					:class="{ open: openId === s.id }"
					:style="`--d:${idx * 30}ms`"
				>
					<button class="row-head" @click="toggle(s.id)">
						<span class="date">{{ formatDate(s.date, i18n.lang) }}</span>
						<span class="who">
							<span class="dot" :style="{ background: partyColor(s.party) }"></span>
							<strong>{{ s.politician }}</strong>
						</span>
						<span class="party" :style="{ color: partyColor(s.party) }">{{ s.party }}</span>
						<span class="role">{{ s.position_long ?? s.position_short }}</span>
						<span v-if="s.snippet" class="snip">…<template v-for="(seg, si) in segs(s.snippet)" :key="si"><mark v-if="seg.hit">{{ seg.t }}</mark><template v-else>{{ seg.t }}</template></template>…</span>
						<span class="chev" :class="{ up: openId === s.id }">⌄</span>
					</button>

					<Transition name="detail">
						<div v-if="openId === s.id" class="detail">
							<div v-if="fullLoading === s.id" class="sk tall"></div>
							<p v-else-if="fullCache[s.id]?.speech_content" class="full">
								<template v-for="(seg, si) in segs(fullCache[s.id].speech_content!)" :key="si"><mark v-if="seg.hit">{{ seg.t }}</mark><template v-else>{{ seg.t }}</template></template>
							</p>
							<p v-else class="unavail">{{ i18n.t('fulltext_unavailable') }}</p>
							<div class="actions">
								<button class="btn--ghost mini" @click="download(s)">⤓ {{ i18n.t('download') }}</button>
								<a class="btn--ghost mini" :href="protocolUrl(s)" target="_blank" rel="noopener noreferrer">
									⤓ {{ i18n.t('download_protocol') }}
								</a>
							</div>
						</div>
					</Transition>
				</li>
			</ul>

			<div v-if="pages > 1" class="pagination">
				<button class="pg-btn" :disabled="offset === 0" @click="offset -= PAGE">‹ {{ i18n.t('prev') }}</button>
				<span class="pg-info">{{ currentPage }} / {{ pages }}</span>
				<button class="pg-btn" :disabled="currentPage >= pages" @click="offset += PAGE">{{ i18n.t('next') }} ›</button>
			</div>
		</template>
	</div>
</template>

<style scoped>
/* ponytail: approximated Svelte transition:fly with css transform on .detail-enter/leave */
.detail-enter-active { transition: opacity 0.2s, transform 0.2s; }
.detail-leave-active { transition: opacity 0.15s, transform 0.15s; }
.detail-enter-from { opacity: 0; transform: translateY(-6px); }
.detail-leave-to   { opacity: 0; transform: translateY(-6px); }

.table-wrap {
	min-height: 320px;
}
.count {
	font-size: 0.78rem;
	color: var(--ink-3);
	margin-bottom: 0.8rem;
}
.loading {
	display: flex;
	flex-direction: column;
	gap: 0.6rem;
	padding-top: 0.4rem;
}
.sk {
	height: 52px;
	border-radius: 8px;
	background: linear-gradient(90deg, var(--surface-2), var(--surface-3), var(--surface-2));
	background-size: 200% 100%;
	animation: shimmer 1.3s infinite;
	animation-delay: var(--d, 0ms);
}
.sk.tall { height: 140px; }
@keyframes shimmer { to { background-position: -200% 0; } }

.list {
	list-style: none;
	margin: 0;
	padding: 0;
}
.row {
	border-bottom: 1px solid var(--line);
	animation: rise 0.45s var(--ease) backwards;
	animation-delay: var(--d, 0ms);
}
@keyframes rise {
	from { opacity: 0; transform: translateY(6px); }
}
.row-head {
	width: 100%;
	display: grid;
	grid-template-columns: 6.5rem 1fr auto auto;
	grid-template-rows: auto auto auto;
	column-gap: 0.75rem;
	row-gap: 0.2rem;
	align-items: baseline;
	padding: 0.75rem 0.2rem;
	background: none;
	border: none;
	cursor: pointer;
	text-align: left;
	font: inherit;
	color: var(--ink);
	transition: background 0.15s;
}
.row-head:hover { background: var(--surface-2); border-radius: var(--radius-sm); }
.date {
	font-size: 0.78rem;
	color: var(--ink-3);
	font-variant-numeric: tabular-nums;
	grid-row: 1;
	grid-column: 1;
}
.who {
	display: flex;
	align-items: center;
	gap: 0.4rem;
	grid-row: 1;
	grid-column: 2;
	font-size: 0.9rem;
}
.dot {
	width: 8px;
	height: 8px;
	border-radius: 50%;
	flex: none;
}
.party {
	grid-row: 1;
	grid-column: 3;
	font-size: 0.75rem;
	font-weight: 600;
}
.chev {
	grid-row: 1;
	grid-column: 4;
	color: var(--ink-3);
	font-size: 1.1rem;
	transition: transform 0.25s var(--ease);
	align-self: center;
}
.chev.up { transform: rotate(180deg); color: var(--accent); }
.role {
	grid-row: 2;
	grid-column: 2;
	font-size: 0.75rem;
	color: var(--ink-3);
}
.snip {
	grid-row: 3;
	grid-column: 1 / 5;
	margin-top: 0.15rem;
	font-size: 0.78rem;
	color: var(--ink-2);
	line-height: 1.5;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
}
mark {
	background: linear-gradient(180deg, transparent 55%, rgba(255, 206, 92, 0.45) 55%);
	color: var(--ink);
	padding: 0 0.05em;
	border-radius: 2px;
	font-weight: 600;
}
.detail {
	padding: 0.6rem 0.2rem 1rem 1.2rem;
	border-left: 2px solid var(--accent);
	margin: 0 0 0.5rem 0.3rem;
}
.full {
	font-size: 0.88rem;
	line-height: 1.7;
	color: var(--ink);
	max-height: 280px;
	overflow-y: auto;
	margin: 0 0 0.8rem;
	white-space: pre-wrap;
}
.unavail {
	font-size: 0.82rem;
	color: var(--ink-3);
	font-style: italic;
	margin: 0 0 0.8rem;
}
.actions {
	display: flex;
	gap: 0.5rem;
	flex-wrap: wrap;
}
.mini {
	padding: 0.45rem 0.9rem;
	font-size: 0.82rem;
	text-decoration: none;
}
.pagination {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 1rem;
	padding-top: 1.2rem;
}
.pg-btn {
	font: inherit;
	font-size: 0.85rem;
	padding: 0.45rem 1rem;
	border: 1px solid var(--line-2);
	border-radius: 999px;
	background: var(--surface);
	color: var(--ink-2);
	cursor: pointer;
	transition: color 0.15s, border-color 0.15s;
}
.pg-btn:hover:not(:disabled) { color: var(--ink); border-color: var(--line-3); }
.pg-btn:disabled { opacity: 0.35; cursor: default; }
.pg-info {
	font-size: 0.82rem;
	color: var(--ink-3);
	font-variant-numeric: tabular-nums;
}
.empty {
	color: var(--ink-3);
	text-align: center;
	padding: 3rem 0;
	font-size: 0.9rem;
}

@media (max-width: 600px) {
	.row-head {
		grid-template-columns: 5.5rem 1fr auto;
	}
	.party { display: none; }
	.snip { grid-column: 1 / 4; }
}
</style>
