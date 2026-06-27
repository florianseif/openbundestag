<script setup lang="ts">
// onclose callback prop → emit('close')
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { api } from '$lib/api';
import type { Filters, SpeechItem, SpeechFull } from '$lib/types';
import { i18n } from '$lib/i18n';
import { partyColor, formatDate, formatNumber } from '$lib/format';

const props = defineProps<{
	query: Filters | null;
	title: string;
	word: string;
}>();

// Replaces the `onclose: () => void` callback prop.
const emit = defineEmits<{ close: [] }>();

const items = ref<SpeechItem[]>([]);
const total = ref<number | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

const openId = ref<number | null>(null);
const fullCache = ref<Record<number, SpeechFull>>({});
const fullLoading = ref<number | null>(null);

// Fetch speeches whenever query changes.
watch(() => props.query, (q) => {
	items.value = [];
	total.value = null;
	error.value = null;
	openId.value = null;
	if (!q) return;
	loading.value = true;
	Promise.all([api.speeches(q, 30, 0), api.total(q)])
		.then(([page, tot]) => {
			items.value = page.items;
			total.value = tot.count;
		})
		.catch((e: Error) => (error.value = e.message))
		.finally(() => (loading.value = false));
}, { immediate: true });

// Lock body scroll while modal is open.
watch(() => props.query, (q) => {
	if (typeof document === 'undefined') return;
	document.body.style.overflow = q ? 'hidden' : '';
});
onUnmounted(() => {
	if (typeof document !== 'undefined') document.body.style.overflow = '';
});

function onkey(e: KeyboardEvent) {
	if (e.key === 'Escape') emit('close');
}
onMounted(() => window.addEventListener('keydown', onkey));
onUnmounted(() => window.removeEventListener('keydown', onkey));

async function toggle(id: number) {
	if (openId.value === id) { openId.value = null; return; }
	openId.value = id;
	if (!fullCache.value[id]) {
		fullLoading.value = id;
		try { fullCache.value[id] = await api.speech(id); } catch { /* ignore */ }
		finally { fullLoading.value = null; }
	}
}

function segments(text: string): { t: string; hit: boolean }[] {
	const w = props.word.trim();
	if (!w) return [{ t: text, hit: false }];
	const re = new RegExp(`(${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
	return text.split(re).map((t) => ({ t, hit: t.toLowerCase() === w.toLowerCase() }));
}

async function download(item: SpeechItem) {
	if (!fullCache.value[item.id]) {
		try { fullCache.value[item.id] = await api.speech(item.id); } catch { /* ignore */ }
	}
	const full = fullCache.value[item.id];
	const body = full?.speech_content ?? item.snippet ?? '';
	const rule = '─'.repeat(64);
	const meta = [
		[i18n.t('speaker') + ':', item.politician],
		[i18n.t('party') + ':', item.party],
		[i18n.t('role') + ':', item.position_long ?? item.position_short],
		[i18n.t('date') + ':', formatDate(item.date, i18n.lang)],
		[i18n.t('term_short') + ':', String(item.electoral_term)],
		[i18n.t('session') + ':', String(item.session)],
		[i18n.t('keyword') + ':', props.word]
	]
		.map(([k, v]) => `${k.padEnd(12)} ${v}`)
		.join('\n');
	const lines = [
		'OpenBundestag — Plenarrede',
		rule, meta, rule, '',
		body || i18n.t('fulltext_unavailable'),
		'', rule,
		'Quelle: Deutscher Bundestag · Plenarprotokolle',
		'(bundestag.de/services/opendata) · via OpenBundestag'
	].join('\n');
	const blob = new Blob([lines], { type: 'text/plain;charset=utf-8' });
	const a = document.createElement('a');
	a.href = URL.createObjectURL(blob);
	a.download = `rede-${item.id}-${item.politician.replace(/\s+/g, '-').toLowerCase()}.txt`;
	a.click();
	URL.revokeObjectURL(a.href);
}
</script>

<template>
	<Transition name="modal">
		<div
			v-if="query"
			class="scrim"
			role="presentation"
			@click="emit('close')"
		></div>
	</Transition>

	<Transition name="modal-shell">
		<div v-if="query" class="modal-shell" role="presentation">
			<div
				class="modal glass"
				role="dialog"
				aria-modal="true"
				:aria-label="i18n.t('read_passage')"
			>
				<header>
					<div class="htext">
						<div class="eyebrow">{{ i18n.t('read_passage') }}</div>
						<h3>
							<span class="kw">„{{ word }}"</span>
							<span class="ctx">· {{ title }}</span>
						</h3>
						<p v-if="total != null" class="count">{{ formatNumber(total, i18n.lang) }} {{ i18n.t('matching_speeches') }}</p>
					</div>
					<button class="x" @click="emit('close')" :aria-label="i18n.t('close')">✕</button>
				</header>

				<div class="body">
					<div v-if="loading" class="skeleton">
						<div v-for="i in 5" :key="i" class="sk"></div>
					</div>
					<p v-else-if="error" class="err">{{ error }}</p>
					<p v-else-if="!items.length" class="empty">{{ i18n.t('no_results', { word }) }}</p>
					<ul v-else class="list">
						<li
							v-for="(s, i) in items"
							:key="s.id"
							class="item"
							:class="{ open: openId === s.id }"
							:style="{ '--c': partyColor(s.party), '--d': `${i * 28}ms` }"
						>
							<button class="head" @click="toggle(s.id)" :aria-expanded="openId === s.id">
								<span class="rail"></span>
								<span class="info">
									<span class="who">
										<strong>{{ s.politician }}</strong>
										<span class="party" :style="{ color: partyColor(s.party) }">{{ s.party }}</span>
									</span>
									<span class="sub">
										{{ formatDate(s.date, i18n.lang) }} · {{ s.position_long ?? s.position_short }} ·
										{{ i18n.t('term_short') }}&nbsp;{{ s.electoral_term }}
									</span>
								</span>
								<span class="chev" :class="{ up: openId === s.id }" aria-hidden="true">⌄</span>
							</button>

							<p v-if="s.snippet" class="snippet">
								…<template v-for="(seg, si) in segments(s.snippet)" :key="si"><mark v-if="seg.hit">{{ seg.t }}</mark><template v-else>{{ seg.t }}</template></template>…
							</p>

							<div class="actions">
								<button class="btn--ghost mini" @click="download(s)">
									⤓ {{ i18n.t('download') }}
								</button>
								<a
									class="btn--ghost mini"
									:href="`https://dserver.bundestag.de/btp/${String(s.electoral_term).padStart(2, '0')}/${s.session}.pdf`"
									target="_blank"
									rel="noopener noreferrer"
								>
									⤓ {{ i18n.t('download_protocol') }}
								</a>
							</div>

							<Transition name="reader">
								<div v-if="openId === s.id" class="reader">
									<div v-if="fullLoading === s.id" class="sk tall"></div>
									<p v-else-if="fullCache[s.id]?.speech_content" class="full">
										<template v-for="(seg, si) in segments(fullCache[s.id].speech_content!)" :key="si"><mark v-if="seg.hit">{{ seg.t }}</mark><template v-else>{{ seg.t }}</template></template>
									</p>
									<p v-else class="unavailable">{{ i18n.t('fulltext_unavailable') }}</p>
								</div>
							</Transition>
						</li>
					</ul>
				</div>
			</div>
		</div>
	</Transition>
</template>

<style scoped>
/* ponytail: approximated Svelte transition:fade on scrim with css opacity */
.modal-enter-active  { transition: opacity 0.22s; }
.modal-leave-active  { transition: opacity 0.22s; }
.modal-enter-from    { opacity: 0; }
.modal-leave-to      { opacity: 0; }

/* ponytail: approximated Svelte transition:scale on modal shell */
.modal-shell-enter-active { transition: opacity 0.32s, transform 0.32s; }
.modal-shell-leave-active { transition: opacity 0.22s, transform 0.22s; }
.modal-shell-enter-from   { opacity: 0; transform: scale(0.96); }
.modal-shell-leave-to     { opacity: 0; transform: scale(0.96); }

/* ponytail: approximated Svelte transition:fly on reader */
.reader-enter-active { transition: opacity 0.22s, transform 0.22s; }
.reader-leave-active { transition: opacity 0.15s, transform 0.15s; }
.reader-enter-from   { opacity: 0; transform: translateY(-6px); }
.reader-leave-to     { opacity: 0; transform: translateY(-6px); }

.scrim {
	position: fixed;
	inset: 0;
	background: rgba(3, 4, 8, 0.66);
	backdrop-filter: blur(6px);
	z-index: 50;
}
.modal-shell {
	position: fixed;
	inset: 0;
	z-index: 51;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: clamp(1rem, 4vw, 2.5rem);
	pointer-events: none;
}
.modal {
	pointer-events: auto;
	width: min(720px, 100%);
	max-height: min(86vh, 820px);
	display: flex;
	flex-direction: column;
	border-radius: var(--radius-lg);
	overflow: hidden;
}
header {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 1rem;
	padding: 1.4rem 1.5rem 1.1rem;
	border-bottom: 1px solid var(--line);
	background: var(--grad-soft);
}
h3 {
	margin: 0.15rem 0 0;
	font-size: 1.4rem;
}
.kw {
	color: var(--ink);
}
.ctx {
	color: var(--ink-3);
	font-weight: 400;
	font-size: 1rem;
}
.count {
	margin: 0.45rem 0 0;
	font-size: 0.82rem;
	color: var(--ink-2);
}
.x {
	font-size: 1rem;
	background: var(--glass-2);
	border: 1px solid var(--line-2);
	border-radius: 999px;
	width: 36px;
	height: 36px;
	cursor: pointer;
	color: var(--ink-2);
	flex: none;
	transition:
		transform 0.25s var(--spring),
		color 0.2s;
}
.x:hover {
	transform: rotate(90deg);
	color: var(--ink);
}
.body {
	overflow-y: auto;
	padding: 0.6rem 1.5rem 1.5rem;
}
.list {
	list-style: none;
	margin: 0;
	padding: 0;
}
.item {
	border-bottom: 1px solid var(--line);
	animation: rise 0.5s var(--ease) backwards;
	animation-delay: var(--d);
}
@keyframes rise {
	from {
		opacity: 0;
		transform: translateY(8px);
	}
}
.head {
	width: 100%;
	display: flex;
	align-items: center;
	gap: 0.85rem;
	padding: 0.95rem 0.2rem;
	background: none;
	border: none;
	cursor: pointer;
	text-align: left;
	font: inherit;
	color: var(--ink);
}
.rail {
	width: 4px;
	align-self: stretch;
	min-height: 32px;
	border-radius: 99px;
	background: var(--c);
	flex: none;
	box-shadow: 0 0 12px -2px var(--c);
}
.info {
	flex: 1;
	min-width: 0;
}
.who {
	display: flex;
	align-items: baseline;
	gap: 0.5rem;
	flex-wrap: wrap;
}
.who strong {
	font-weight: 600;
}
.party {
	font-size: 0.8rem;
	font-weight: 600;
}
.sub {
	display: block;
	font-size: 0.78rem;
	color: var(--ink-3);
	margin-top: 0.1rem;
}
.chev {
	color: var(--ink-3);
	font-size: 1.3rem;
	transition: transform 0.3s var(--ease);
	flex: none;
}
.chev.up {
	transform: rotate(180deg);
	color: var(--accent);
}
.snippet {
	margin: 0 0 0.85rem 1.85rem;
	font-size: 0.88rem;
	line-height: 1.6;
	color: var(--ink-2);
}
.reader {
	margin: 0 0 1.1rem 1.85rem;
}
.full {
	margin: 0 0 0.9rem;
	font-size: 0.92rem;
	line-height: 1.72;
	color: var(--ink);
	max-height: 360px;
	overflow-y: auto;
	padding-right: 0.6rem;
	white-space: pre-wrap;
}
.unavailable {
	margin: 0 0 0.9rem;
	font-size: 0.85rem;
	color: var(--ink-3);
	font-style: italic;
	padding: 0.7rem 0.9rem;
	background: var(--glass-2);
	border-radius: var(--radius-sm);
	border: 1px dashed var(--line-2);
}
mark {
	background: linear-gradient(180deg, transparent 55%, rgba(255, 206, 92, 0.45) 55%);
	color: var(--ink);
	padding: 0 0.05em;
	border-radius: 2px;
	font-weight: 600;
}
.actions {
	display: flex;
	gap: 0.5rem;
	margin: 0 0 0.85rem 1.85rem;
}
.mini {
	padding: 0.5rem 1rem;
	font-size: 0.85rem;
	text-decoration: none;
}
.err {
	color: var(--spark);
	font-size: 0.9rem;
}
.empty {
	color: var(--ink-3);
	text-align: center;
	padding: 2rem 0;
}
.skeleton {
	display: flex;
	flex-direction: column;
	gap: 0.7rem;
	padding-top: 0.6rem;
}
.sk {
	height: 56px;
	border-radius: 10px;
	background: linear-gradient(90deg, var(--surface-2), var(--surface-3), var(--surface-2));
	background-size: 200% 100%;
	animation: shimmer 1.3s infinite;
}
.sk.tall {
	height: 160px;
}
@keyframes shimmer {
	to {
		background-position: -200% 0;
	}
}
</style>
