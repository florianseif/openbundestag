<script setup lang="ts">
import { ref, computed, watchEffect, onMounted, onUnmounted } from 'vue';
import { api, ApiError } from '$lib/api';
import { setPartyMeta, partyFoundingOrder, partyColor } from '$lib/format';
import { i18n } from '$lib/i18n';
import type {
	Meta,
	Filters,
	CountMode,
	TimelinePoint,
	PartyCount,
	TermCount,
	PoliticianCount,
	Totals,
	Politician
} from '$lib/types';

import TimelineChart from '$lib/components/TimelineChart.vue';
import CompareChart from '$lib/components/CompareChart.vue';
import HBars from '$lib/components/HBars.vue';
import Donut from '$lib/components/Donut.vue';
import SpeechModal from '$lib/components/SpeechModal.vue';
import SpeechTable from '$lib/components/SpeechTable.vue';
import PageHero from '$lib/components/PageHero.vue';
import TermFilter from '$lib/components/TermFilter.vue';

// --- bootstrap state ------------------------------------------------------
const meta = ref<Meta | null>(null);
const bootError = ref<string | null>(null);

// Read initial URL params natively (SPA: window.location matches page.url).
const sp = new URLSearchParams(window.location.search);
const DEFAULTS: Filters = {
	word: sp.get('word') ?? 'Schuldenbremse',
	parties: sp.getAll('parties'),
	terms: sp.getAll('terms').map(Number).filter(Boolean),
	politician_id: null,
	date_from: null,
	date_to: null,
	granularity: 'Quarterly',
	count_mode: (sp.get('mode') as CountMode) ?? 'occurrences'
};
const filters = ref<Filters>({ ...DEFAULTS });

// Curated example searches — each produces a dramatic, story-telling curve.
const SUGGESTIONS = ['Schuldenbremse', 'Klimawandel', 'Migration', 'Digitalisierung', 'Rente', 'Ukraine'];

// Politician filter — scopes only the timeline and speech list.
const polId = ref<number | null>(sp.get('pol') ? Number(sp.get('pol')) : null);
const polQuery = ref(sp.get('pol') ? '…' : '');
const polResults = ref<Politician[]>([]);
const polOpen = ref(false);
let polTimer: ReturnType<typeof setTimeout>;

function onPolInput(v: string) {
	polQuery.value = v;
	polOpen.value = true;
	if (!v.trim()) {
		polId.value = null;
	}
	clearTimeout(polTimer);
	polTimer = setTimeout(async () => {
		polResults.value = v.trim() ? await api.politicians(v.trim(), 8).catch(() => []) : [];
	}, 200);
}
function pickPol(p: Politician) {
	polId.value = p.id;
	polQuery.value = p.name;
	polOpen.value = false;
	polResults.value = [];
}
function clearPol() {
	polId.value = null;
	polQuery.value = '';
	polResults.value = [];
	polOpen.value = false;
}
function onPolBlur() {
	setTimeout(() => (polOpen.value = false), 150);
}

watchEffect(() => {
	if (polId.value != null && polQuery.value === '…') {
		api.politicians('', 1).catch(() => []);
		polQuery.value = `#${polId.value}`;
	}
});

// --- result state ---------------------------------------------------------
const total = ref<Totals | null>(null);
const timeline = ref<TimelinePoint[]>([]);
const byParty = ref<PartyCount[]>([]);
const top = ref<PoliticianCount[]>([]);
const loading = ref(false);
const queryError = ref<string | null>(null);

const topN = ref(15);

// --- word-vs-word comparison ----------------------------------------------
const showCompare = ref(!!sp.get('vs'));
const compareWord = ref(sp.get('vs') ?? '');
const compareTimeline = ref<TimelinePoint[]>([]);
const compareParty = ref<string | null>(null);
const compareActive = computed(() => compareWord.value.trim().length > 0);

function aggregate(tl: TimelinePoint[], party?: string | null): { period: string; value: number }[] {
	const src = party ? tl.filter((p) => p.party === party) : tl;
	const m = new Map<string, number>();
	for (const p of src) m.set(p.period, (m.get(p.period) ?? 0) + p.value);
	return [...m.entries()]
		.map(([period, value]) => ({ period, value }))
		.sort((x, y) => (x.period < y.period ? -1 : 1));
}
const seriesA = computed(() => aggregate(timeline.value, compareParty.value));
const seriesB = computed(() => aggregate(compareTimeline.value, compareParty.value));

const compareParties = computed(() => {
	const set = new Set<string>();
	for (const p of timeline.value) if (p.party && p.party !== 'Unknown') set.add(p.party);
	for (const p of compareTimeline.value) if (p.party && p.party !== 'Unknown') set.add(p.party);
	return [...set].sort((a, b) => partyFoundingOrder(a) - partyFoundingOrder(b));
});

function closeCompare() {
	compareWord.value = '';
	showCompare.value = false;
	compareTimeline.value = [];
	compareParty.value = null;
}

async function boot() {
	bootError.value = null;
	try {
		const m = await api.meta();
		setPartyMeta(m.party_colors, m.party_full_names);
		meta.value = m;
		// Default to current legislature if no terms were provided via URL
		if (filters.value.terms.length === 0) {
			const latestTerm = Math.max(...m.terms.map((t) => t.term));
			filters.value.terms = [latestTerm];
		}
	} catch (e) {
		const err = e as ApiError;
		bootError.value = err.status === 0 ? null : err.message;
		if (err.status === 0) {
			setTimeout(boot, 4000);
			return;
		}
	}
}
onMounted(boot);

const valueLabel = computed(() =>
	filters.value.count_mode === 'speeches' ? i18n.t('speeches') : i18n.t('occurrences')
);

// --- debounced query whenever filters or polId change --------------------
let debounce: ReturnType<typeof setTimeout>;
watchEffect(() => {
	if (!meta.value) return;
	const f = {
		...filters.value,
		parties: [...filters.value.parties],
		terms: [...filters.value.terms]
	};
	const pid = polId.value;
	const n = topN.value;
	clearTimeout(debounce);
	debounce = setTimeout(() => runQuery(f, pid, n), 280);
});

// Compare word B: fetch its timeline (whole-keyword, same term/mode filters).
let cmpDebounce: ReturnType<typeof setTimeout>;
watchEffect(() => {
	if (!meta.value) return;
	const w = compareWord.value.trim();
	const f = {
		...filters.value,
		parties: [...filters.value.parties],
		terms: [...filters.value.terms]
	};
	if (!w) {
		compareTimeline.value = [];
		return;
	}
	clearTimeout(cmpDebounce);
	cmpDebounce = setTimeout(async () => {
		try {
			const res = await api.search({ ...f, word: w, politician_id: null }, 1);
			compareTimeline.value = res.timeline;
		} catch {
			compareTimeline.value = [];
		}
	}, 320);
});

async function runQuery(f: Filters, pid: number | null, n: number) {
	if (!f.word.trim()) {
		total.value = null;
		timeline.value = [];
		byParty.value = [];
		top.value = [];
		return;
	}
	loading.value = true;
	queryError.value = null;
	// One request → one text scan on the API → total + timeline + by-party +
	// top-speakers. politician_id narrows total+timeline only.
	try {
		const res = await api.search({ ...f, politician_id: pid }, n);
		total.value = res.total;
		timeline.value = res.timeline;
		byParty.value = res.by_party;
		top.value = res.top_politicians;
		queryError.value = null;
	} catch (e) {
		queryError.value = (e as ApiError).message;
	}
	loading.value = false;
}

// Encode filter state + polId in URL for shareability (native history API,
// matching SvelteKit's replaceState — no navigation/reload).
watchEffect(() => {
	const f = filters.value;
	const url = new URL(window.location.href);
	if (f.word.trim()) url.searchParams.set('word', f.word.trim());
	else url.searchParams.delete('word');
	url.searchParams.delete('parties');
	for (const p of f.parties) url.searchParams.append('parties', p);
	url.searchParams.delete('terms');
	for (const t of f.terms) url.searchParams.append('terms', String(t));
	if (polId.value != null) url.searchParams.set('pol', String(polId.value));
	else url.searchParams.delete('pol');
	if (compareWord.value.trim()) url.searchParams.set('vs', compareWord.value.trim());
	else url.searchParams.delete('vs');
	// Legacy date params no longer used — clean them up
	url.searchParams.delete('from');
	url.searchParams.delete('to');
	url.searchParams.delete('gran');
	if (f.count_mode !== 'occurrences') url.searchParams.set('mode', f.count_mode);
	else url.searchParams.delete('mode');
	history.replaceState(history.state, '', url);
});

function onWindowKeydown(e: KeyboardEvent) {
	if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
		e.preventDefault();
		document.getElementById('kw')?.focus();
	}
}
onMounted(() => window.addEventListener('keydown', onWindowKeydown));
onUnmounted(() => window.removeEventListener('keydown', onWindowKeydown));

function reset() {
	const latestTerm = meta.value ? Math.max(...meta.value.terms.map((t) => t.term)) : 20;
	filters.value = { ...DEFAULTS, word: filters.value.word, terms: [latestTerm] };
	clearPol();
	topN.value = 15;
}

// --- drill-down -----------------------------------------------------------
const flipped = ref(false);
const drill = ref<{ q: Filters; title: string } | null>(null);
function pick(period: string, party?: string) {
	const start = new Date(period);
	const end = new Date(start);
	end.setMonth(end.getMonth() + 3);
	// Clicking any timeline point shows all parties at that period; the active
	// legend filter (filters.parties) is still respected if one is set.
	const parties = party ? [party] : filters.value.parties;
	const label = party ?? (parties.length ? parties.join(', ') : i18n.t('all_parties'));
	drill.value = {
		q: {
			...filters.value,
			politician_id: polId.value,
			parties,
			date_from: period,
			date_to: end.toISOString().slice(0, 10)
		},
		title: `${label} · ${period.slice(0, 7)}`
	};
}

function onToggleParty(p: string) {
	filters.value.parties = filters.value.parties.includes(p)
		? filters.value.parties.filter((x) => x !== p)
		: [...filters.value.parties, p];
}

// --- derived views --------------------------------------------------------
const cleanParties = computed(() =>
	byParty.value
		.filter((d) => d.party !== 'Unknown')
		.sort((a, b) => partyFoundingOrder(a.party) - partyFoundingOrder(b.party))
);
const partyBars = computed(() =>
	cleanParties.value.map((d) => ({ label: d.party, value: d.speeches, color: partyColor(d.party) }))
);
const donutSlices = computed(() =>
	cleanParties.value
		.slice(0, 8)
		.map((d) => ({ label: d.party, value: d.speeches, color: partyColor(d.party) }))
);
const topBars = computed(() =>
	top.value.map((d) => ({
		label: d.politician,
		sub: d.party,
		value: d.speeches,
		color: partyColor(d.party)
	}))
);

const speechFilters = computed(() => ({ ...filters.value, politician_id: polId.value }));

// Corpus stat chips shown in the page hero
const heroStats = computed(() =>
	meta.value
		? [
				{ value: meta.value.terms.length, label: i18n.t('hero_terms') },
				{ value: `${meta.value.min_date.slice(0, 4)}–${i18n.t('present')}`, label: '' },
				{ value: meta.value.parties.length, label: i18n.t('hero_parties') }
			]
		: []
);

watchEffect(() => {
	document.title = `${filters.value.word ? `${filters.value.word} · ` : ''}${i18n.t('ws_title')} · OpenBundestag`;
});
</script>

<template>
	<div v-if="!meta" class="boot wrap">
		<template v-if="bootError">
			<h2>{{ i18n.t('error') }}</h2>
			<p class="muted">{{ bootError }}</p>
			<button class="btn" @click="boot">{{ i18n.t('retry') }}</button>
		</template>
		<template v-else>
			<div class="orb"></div>
			<p class="muted">{{ i18n.t('waking') }}</p>
		</template>
	</div>
	<div v-else class="explore wrap">
		<PageHero :title="i18n.t('ws_title')" :subtitle="i18n.t('ws_subtitle')" :stats="heroStats" />

		<!-- ── Search section ─────────────────────────────────────────────── -->
		<div class="search-section glass">
			<div class="search-hero">
				<div class="search-aurora-ring" :class="{ 'has-word': filters.word.trim().length > 0 }">
					<div class="search-input-wrap">
						<svg class="search-icon" width="20" height="20" viewBox="0 0 16 16" fill="none" aria-hidden="true">
							<circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" stroke-width="1.5" />
							<line x1="10" y1="10" x2="14" y2="14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
						</svg>
						<input
							id="kw"
							class="search-input"
							v-model="filters.word"
							:maxlength="meta!.keyword_max_len"
							:placeholder="i18n.t('keyword_ph')"
							autocomplete="off"
						/>
						<span v-if="loading" class="pulse"></span>
					</div>
				</div>
				<button class="reset-btn" @click="reset">{{ i18n.t('reset') }}</button>
			</div>

			<!-- Compare — its own prominent row -->
			<div class="cmp-row">
				<span v-if="showCompare || compareWord" class="cmp-field">
					<svg class="cmp-icon" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
						<path d="M3 3v8M11 3v8M1 7h12" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
					</svg>
					<span class="cmp-vs">vs</span>
					<input
						class="cmp-input"
						v-model="compareWord"
						:placeholder="i18n.t('cmp_ph')"
						:maxlength="meta!.keyword_max_len"
						autocomplete="off"
					/>
					<button class="cmp-x" @click="closeCompare" :aria-label="i18n.t('cmp_clear')">✕</button>
				</span>
				<button v-else class="cmp-add" @click="showCompare = true">
					<svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
						<path d="M3 3v8M11 3v8M1 7h12" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
					</svg>
					{{ i18n.t('cmp_add') }}
				</button>
			</div>

			<!-- Suggestions -->
			<div class="suggestions">
				<button
					v-for="w in SUGGESTIONS"
					:key="w"
					class="suggestion"
					:class="{ active: filters.word === w }"
					@click="filters.word = w"
				>
					{{ w }}
				</button>
			</div>
		</div>

		<!-- ── Filter bar ─────────────────────────────────────────────────── -->
		<div class="filter-bar glass">
			<!-- Wahlperioden term chips -->
			<div class="term-section-inner">
				<TermFilter v-model:selected="filters.terms" :options="meta!.terms" />
			</div>

			<!-- Count mode -->
			<div class="controls-row">
				<div class="ctrl-group">
					<span class="ctrl-lbl">{{ i18n.t('count_by') }}</span>
					<div class="seg">
						<button :class="{ on: filters.count_mode === 'speeches' }" @click="filters.count_mode = 'speeches'">
							{{ i18n.t('speeches') }}
						</button>
						<button :class="{ on: filters.count_mode === 'occurrences' }" @click="filters.count_mode = 'occurrences'">
							{{ i18n.t('occurrences') }}
						</button>
					</div>
				</div>
			</div>
		</div>

		<!-- ── Main content ──────────────────────────────────────────────── -->
		<div class="content" :class="{ scanning: loading && total }">
			<Transition name="fade">
				<div v-if="loading && total" class="data-scan" aria-hidden="true">
					<div class="scan-beam"></div>
					<div class="scan-trail"></div>
					<div class="scan-label">
						<span class="scan-dot"></span>
						<span class="scan-text">ANALYSIERE</span>
					</div>
				</div>
			</Transition>

			<div v-if="!filters.word.trim()" class="empty-state glass">
				<svg class="empty-icon" width="52" height="52" viewBox="0 0 52 52" fill="none" aria-hidden="true">
					<rect x="20" y="4" width="12" height="24" rx="6" stroke="var(--accent)" stroke-width="2" />
					<path d="M10 26c0 8.837 7.163 16 16 16s16-7.163 16-16" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" />
					<line x1="26" y1="42" x2="26" y2="50" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" />
					<line x1="16" y1="50" x2="36" y2="50" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" />
				</svg>
				<p>{{ i18n.t('enter_keyword') }}</p>
			</div>
			<!-- ponytail: dropped the skeleton's 150ms fade-in (imperceptible vs data-scan) -->
			<div v-else-if="loading && !total" class="skeleton" aria-hidden="true">
				<div class="sk-tabs">
					<span class="sk-shimmer"></span>
					<span class="sk-shimmer"></span>
				</div>
				<div class="sk-hero sk-shimmer"></div>
				<div class="grid-2">
					<div class="sk-panel sk-shimmer"></div>
					<div class="sk-panel sk-shimmer"></div>
				</div>
			</div>
			<div v-else-if="total && total.count === 0" class="empty-state glass zero">
				<svg class="zero-icon" width="120" height="40" viewBox="0 0 120 40" fill="none" aria-hidden="true">
					<line x1="4" y1="20" x2="116" y2="20" stroke="var(--line-3)" stroke-width="2" stroke-linecap="round" stroke-dasharray="2 6" />
					<circle cx="60" cy="20" r="3.5" fill="var(--accent)" />
				</svg>
				<h3 class="zero-title">{{ i18n.t('no_results_title') }}</h3>
				<p class="zero-sub">{{ i18n.t('no_results', { word: filters.word }) }}</p>
				<div class="zero-suggest">
					<span class="zero-lbl">{{ i18n.t('try_instead') }}</span>
					<button
						v-for="w in SUGGESTIONS.filter((x) => x !== filters.word).slice(0, 5)"
						:key="w"
						class="suggestion"
						@click="filters.word = w"
					>
						{{ w }}
					</button>
				</div>
			</div>
			<template v-else>
				<div v-if="queryError" class="empty-state glass"><p class="err">{{ queryError }}</p></div>
				<!-- word-vs-word comparison -->
				<section v-else-if="compareActive" class="panel hero-panel solid compare-panel">
					<header class="p-head">
						<div>
							<h3 class="cmp-title">{{ filters.word }} <span class="cmp-vs-h">vs</span> {{ compareWord }}</h3>
							<p class="p-hint">{{ i18n.t('cmp_hint') }}</p>
						</div>
						<button class="reset-btn" @click="closeCompare">{{ i18n.t('cmp_exit') }}</button>
					</header>
					<!-- Party filter — single-select -->
					<div v-if="compareParties.length > 1" class="cmp-parties">
						<button
							class="cmp-party-chip"
							:class="{ on: compareParty === null }"
							@click="compareParty = null"
						>
							{{ i18n.t('all_parties') }}
						</button>
						<button
							v-for="p in compareParties"
							:key="p"
							class="cmp-party-chip"
							:class="{ on: compareParty === p }"
							:style="{ '--chip-c': partyColor(p) }"
							@click="compareParty = compareParty === p ? null : p"
						>
							<span class="cmp-party-dot" :style="{ background: partyColor(p) }"></span>
							{{ p }}
						</button>
					</div>
					<CompareChart
						v-if="seriesB.length"
						:a="{ word: filters.word, color: 'var(--accent)', series: seriesA }"
						:b="{ word: compareWord, color: 'var(--spark)', series: seriesB }"
						:value-label="valueLabel"
					/>
					<p v-else class="empty">{{ i18n.t('no_results', { word: compareWord }) }}</p>
				</section>
				<!-- Timeline hero with flip to speech list -->
				<template v-else>
					<div class="hero-wrap">
						<div class="hero-controls">
							<div class="view-tabs">
								<button class="view-tab" :class="{ active: !flipped }" @click="flipped = false">
									<svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true"><polyline points="1,11 4,5 7,8 10,3 13,6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none" /></svg>
									{{ i18n.t('flip_to_chart') }}
								</button>
								<button class="view-tab" :class="{ active: flipped }" @click="flipped = true">
									<svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true"><rect x="1" y="2" width="12" height="2" rx="1" fill="currentColor" /><rect x="1" y="6" width="8" height="2" rx="1" fill="currentColor" /><rect x="1" y="10" width="10" height="2" rx="1" fill="currentColor" /></svg>
									{{ i18n.t('flip_to_list') }}
								</button>
							</div>
						</div>

						<div class="flip-container">
							<div class="flip-inner" :class="{ flipped }">
								<!-- Front: timeline chart -->
								<section class="panel hero-panel flip-face flip-front solid">
									<header class="p-head">
										<div>
											<h3>{{ i18n.t('timeline_over_time') }}</h3>
											<p class="p-hint">{{ i18n.t('drilldown_hint') }}</p>
										</div>
										<!-- Politician filter: scopes timeline + speech list only -->
										<div class="pol-picker" :class="{ 'has-value': polId != null }">
											<svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true" class="pol-icon">
												<circle cx="6.5" cy="4" r="2.3" stroke="currentColor" stroke-width="1.4" />
												<path d="M1.5 11.5c0-2.761 2.239-5 5-5s5 2.239 5 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
											</svg>
											<div class="pol-input-wrap">
												<input
													class="pol-input"
													:value="polQuery"
													@input="onPolInput(($event.target as HTMLInputElement).value)"
													@focus="polOpen = true"
													@blur="onPolBlur"
													:placeholder="i18n.t('any_politician')"
													autocomplete="off"
												/>
												<button v-if="polId != null" class="pol-clr" @click="clearPol" aria-label="clear">✕</button>
												<ul v-if="polOpen && polResults.length" class="pol-dropdown">
													<li v-for="p in polResults" :key="p.id">
														<button @mousedown="pickPol(p)">
															<span class="pol-dot" :style="{ background: partyColor(p.party) }"></span>
															{{ p.name }}<span class="pol-party"> · {{ p.party }}</span>
														</button>
													</li>
												</ul>
											</div>
										</div>
									</header>
									<TimelineChart
										v-if="timeline.length"
										:data="timeline"
										:value-label="valueLabel"
										:selected-parties="filters.parties"
										@toggleparty="onToggleParty"
										@pick="pick"
									/>
									<p v-else class="empty">{{ i18n.t('no_results', { word: filters.word }) }}</p>
								</section>
								<!-- Back: speech list -->
								<section class="panel hero-panel flip-face flip-back solid">
									<header class="p-head">
										<div>
											<h3>{{ i18n.t('flip_to_list') }}</h3>
											<p class="p-hint">{{ i18n.t('matching_speeches') }}</p>
										</div>
									</header>
									<SpeechTable :filters="speechFilters" />
								</section>
							</div>
						</div>
					</div>

					<!-- Party + speakers -->
					<div class="grid-2">
						<section class="panel glass">
							<header class="p-head"><h3>{{ i18n.t('by_party_title') }}</h3></header>
							<div v-if="partyBars.length" class="party-body">
								<div class="donut-cell"><Donut :slices="donutSlices" /></div>
								<HBars :bars="partyBars" :value-label="i18n.t('speeches')" />
							</div>
							<p v-else class="empty">—</p>
						</section>

						<section class="panel glass">
							<header class="p-head">
								<h3>{{ i18n.t('top_speakers_title') }}</h3>
								<label class="slider">
									{{ i18n.t('top_n') }}: <strong>{{ topN }}</strong>
									<input type="range" min="5" max="30" v-model.number="topN" />
								</label>
							</header>
							<HBars v-if="topBars.length" :bars="topBars" :value-label="i18n.t('speeches')" />
							<p v-else class="empty">—</p>
						</section>
					</div>
				</template>
			</template>
		</div>
	</div>

	<SpeechModal
		:query="drill?.q ?? null"
		:title="drill?.title ?? ''"
		:word="filters.word"
		@close="drill = null"
	/>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}

.boot {
	min-height: 64vh;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 1.2rem;
	text-align: center;
}
.muted {
	color: var(--ink-3);
}
.orb {
	width: 64px;
	height: 64px;
	border-radius: 50%;
	background: var(--grad);
	filter: blur(2px);
	animation:
		orb 1.6s var(--ease) infinite,
		spin 3s linear infinite;
	box-shadow: var(--glow);
}
@keyframes orb {
	0%,
	100% {
		transform: scale(1);
		opacity: 0.9;
	}
	50% {
		transform: scale(0.7);
		opacity: 0.5;
	}
}
@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

/* ── Layout ────────────────────────────────────────────────────────── */
.explore {
	display: flex;
	flex-direction: column;
	gap: 1.4rem;
	padding-top: 1.8rem;
	padding-bottom: 3rem;
}

/* ── Search section — visually separated ───────────────────────────── */
.search-section {
	padding: 1.5rem 1.5rem 1.2rem;
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}

/* ── Filter bar ────────────────────────────────────────────────────── */
.filter-bar {
	padding: 1rem 1.5rem;
	display: flex;
	flex-direction: column;
	gap: 0.85rem;
}
.term-section-inner {
	padding-bottom: 0.6rem;
	border-bottom: 1px solid var(--line);
}

/* Search hero — large, prominent, full-width */
.search-hero {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}

/* Aurora gradient ring around the search field */
.search-aurora-ring {
	flex: 1;
	position: relative;
	border-radius: 14px;
	padding: 2px;
	background: var(--line-2);
	transition: background 0.35s;
}
.search-aurora-ring::before {
	content: '';
	position: absolute;
	inset: -1px;
	border-radius: 15px;
	background: var(--grad);
	opacity: 0;
	transition: opacity 0.35s;
	z-index: 0;
}
.search-aurora-ring::after {
	content: '';
	position: absolute;
	inset: -3px;
	border-radius: 17px;
	background: var(--grad);
	opacity: 0;
	filter: blur(12px);
	transition: opacity 0.45s;
	z-index: 0;
}
.search-aurora-ring:focus-within::before,
.search-aurora-ring.has-word::before {
	opacity: 1;
}
.search-aurora-ring:focus-within::after {
	opacity: 0.4;
}
.search-aurora-ring.has-word:focus-within::after {
	opacity: 0.5;
}

.search-input-wrap {
	position: relative;
	z-index: 1;
	display: flex;
	align-items: center;
	gap: 0.8rem;
	background: var(--bg);
	border-radius: 12px;
	padding: 0.9rem 1.2rem;
}
.search-icon {
	color: var(--ink-3);
	flex-shrink: 0;
	transition: color 0.25s;
}
.search-aurora-ring:focus-within .search-icon,
.search-aurora-ring.has-word .search-icon {
	color: var(--accent);
}
.search-input {
	flex: 1;
	font: inherit;
	font-size: 1.35rem;
	font-weight: 500;
	letter-spacing: -0.01em;
	background: none;
	border: none;
	outline: none;
	color: var(--ink);
	min-width: 0;
}
.search-input::placeholder {
	color: var(--ink-3);
}

.pulse {
	width: 8px;
	height: 8px;
	border-radius: 50%;
	background: var(--accent);
	flex-shrink: 0;
	box-shadow: 0 0 0 0 rgba(107, 145, 255, 0.6);
	animation: pulse 1.4s var(--ease) infinite;
}
@keyframes pulse {
	0% {
		box-shadow: 0 0 0 0 rgba(107, 145, 255, 0.55);
	}
	70% {
		box-shadow: 0 0 0 8px rgba(107, 145, 255, 0);
	}
	100% {
		box-shadow: 0 0 0 0 rgba(107, 145, 255, 0);
	}
}

.reset-btn {
	font: inherit;
	font-size: 0.78rem;
	font-weight: 600;
	letter-spacing: 0.04em;
	color: var(--ink-3);
	background: none;
	border: 1px solid var(--line-2);
	border-radius: 999px;
	padding: 0.45rem 0.95rem;
	cursor: pointer;
	white-space: nowrap;
	transition:
		color 0.2s,
		border-color 0.2s;
}
.reset-btn:hover {
	color: var(--ink);
	border-color: var(--line-3);
}

.suggestions {
	display: flex;
	flex-wrap: wrap;
	gap: 0.35rem;
}
.suggestion {
	font: inherit;
	font-size: 0.76rem;
	padding: 0.2rem 0.65rem;
	border-radius: 999px;
	border: 1px solid var(--line-2);
	background: none;
	color: var(--ink-3);
	cursor: pointer;
	transition:
		color 0.15s,
		border-color 0.15s,
		background 0.15s;
}
.suggestion:hover {
	color: var(--accent);
	border-color: var(--accent);
}
.suggestion.active {
	color: var(--accent);
	border-color: var(--accent);
	background: color-mix(in srgb, var(--accent) 10%, transparent);
}

/* ── Compare control ────────────────────────────────────────────────── */
.cmp-row {
	display: flex;
	align-items: center;
}
.cmp-add {
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
	font: inherit;
	font-size: 0.82rem;
	font-weight: 600;
	padding: 0.45rem 1rem;
	border-radius: 999px;
	border: 1px solid color-mix(in srgb, var(--spark) 45%, var(--line-2));
	background: color-mix(in srgb, var(--spark) 6%, transparent);
	color: var(--spark);
	cursor: pointer;
	transition:
		background 0.2s,
		border-color 0.2s,
		box-shadow 0.2s;
}
.cmp-add:hover {
	background: color-mix(in srgb, var(--spark) 14%, transparent);
	border-color: var(--spark);
	box-shadow: 0 0 12px color-mix(in srgb, var(--spark) 20%, transparent);
}
.cmp-add svg {
	opacity: 0.8;
}
.cmp-field {
	display: inline-flex;
	align-items: center;
	gap: 0.4rem;
	padding: 0.35rem 0.5rem 0.35rem 0.65rem;
	border-radius: 999px;
	border: 1px solid color-mix(in srgb, var(--spark) 55%, var(--line-2));
	background: color-mix(in srgb, var(--spark) 8%, transparent);
}
.cmp-icon {
	color: var(--spark);
	opacity: 0.7;
	flex-shrink: 0;
}
.cmp-vs {
	font-size: 0.7rem;
	font-weight: 700;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: var(--spark);
}
.cmp-input {
	font: inherit;
	font-size: 0.9rem;
	background: none;
	border: none;
	outline: none;
	color: var(--ink);
	width: 10rem;
	padding: 0.2rem 0;
}
.cmp-input::placeholder {
	color: var(--ink-3);
}
.cmp-x {
	border: none;
	background: none;
	cursor: pointer;
	color: var(--ink-3);
	font-size: 0.75rem;
	line-height: 1;
	padding: 0.25rem 0.3rem;
}
.cmp-x:hover {
	color: var(--spark);
}
.compare-panel .cmp-title {
	display: flex;
	align-items: baseline;
	gap: 0.5rem;
	flex-wrap: wrap;
}
.cmp-vs-h {
	font-family: var(--sans);
	font-size: 0.7rem;
	font-weight: 700;
	letter-spacing: 0.08em;
	text-transform: uppercase;
	color: var(--ink-3);
}
/* Compare party chips — single-select filter row */
.cmp-parties {
	display: flex;
	flex-wrap: wrap;
	gap: 0.3rem;
	margin-bottom: 1rem;
}
.cmp-party-chip {
	display: inline-flex;
	align-items: center;
	gap: 0.3rem;
	font: inherit;
	font-size: 0.74rem;
	font-weight: 500;
	padding: 0.25rem 0.7rem;
	border-radius: 999px;
	border: 1px solid var(--line-2);
	background: none;
	color: var(--ink-3);
	cursor: pointer;
	transition:
		color 0.15s,
		border-color 0.15s,
		background 0.15s;
}
.cmp-party-chip:hover {
	color: var(--ink);
	border-color: var(--chip-c, var(--line-3));
}
.cmp-party-chip.on {
	color: var(--ink);
	border-color: var(--chip-c, var(--accent));
	background: color-mix(in srgb, var(--chip-c, var(--accent)) 12%, transparent);
}
.cmp-party-dot {
	width: 8px;
	height: 8px;
	border-radius: 50%;
	flex: none;
}

/* Controls row — count mode only */
.controls-row {
	display: flex;
	align-items: center;
	gap: 0.85rem;
	flex-wrap: wrap;
}
.ctrl-group {
	display: flex;
	align-items: center;
	gap: 0.55rem;
}
.ctrl-lbl {
	font-size: 0.72rem;
	font-weight: 600;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: var(--ink-3);
	white-space: nowrap;
}
.seg {
	display: flex;
	gap: 0;
	border: 1px solid var(--line-2);
	border-radius: 6px;
	overflow: hidden;
	background: var(--surface-2);
}
.seg button {
	font: inherit;
	font-size: 0.82rem;
	padding: 0.3rem 0.75rem;
	border: none;
	background: none;
	color: var(--ink-3);
	cursor: pointer;
	transition:
		background 0.15s,
		color 0.15s;
}
.seg button + button {
	border-left: 1px solid var(--line-2);
}
.seg button.on {
	background: var(--accent);
	color: #fff;
}
.seg button:hover:not(.on) {
	color: var(--ink);
	background: var(--surface-3);
}

/* Politician picker — lives in the timeline panel header */
.pol-picker {
	display: flex;
	align-items: center;
	gap: 0.45rem;
	background: var(--surface-2);
	border: 1px solid var(--line-2);
	border-radius: 999px;
	padding: 4px 4px 4px 10px;
	flex-shrink: 0;
	transition: border-color 0.2s;
}
.pol-picker:focus-within {
	border-color: var(--accent);
	box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 20%, transparent);
}
.pol-picker.has-value {
	border-color: var(--accent);
}
.pol-icon {
	color: var(--ink-3);
	flex-shrink: 0;
}
.pol-input-wrap {
	position: relative;
	flex: 1;
	min-width: 120px;
	max-width: 200px;
}
.pol-input {
	width: 100%;
	font: inherit;
	font-size: 0.84rem;
	background: none;
	border: none;
	outline: none;
	color: var(--ink);
	padding: 0.3rem 1.6rem 0.3rem 0;
}
.pol-input::placeholder {
	color: var(--ink-3);
}
.pol-clr {
	position: absolute;
	right: 0;
	top: 50%;
	transform: translateY(-50%);
	border: none;
	background: none;
	cursor: pointer;
	color: var(--ink-3);
	font-size: 0.75rem;
	padding: 0.2rem;
	line-height: 1;
}
.pol-clr:hover {
	color: var(--ink);
}
.pol-dropdown {
	position: absolute;
	z-index: 10;
	top: calc(100% + 6px);
	right: 0;
	width: 260px;
	list-style: none;
	margin: 0;
	padding: 0.3rem;
	background: var(--card);
	border: 1px solid var(--line-2);
	border-radius: var(--radius-sm);
	box-shadow: var(--shadow);
	max-height: 240px;
	overflow-y: auto;
}
.pol-dropdown button {
	width: 100%;
	text-align: left;
	font: inherit;
	font-size: 0.85rem;
	display: flex;
	align-items: center;
	gap: 0.45rem;
	padding: 0.45rem 0.5rem;
	border: none;
	background: none;
	border-radius: 6px;
	cursor: pointer;
	color: var(--ink);
}
.pol-dropdown button:hover {
	background: var(--paper-2);
}
.pol-dot {
	width: 8px;
	height: 8px;
	border-radius: 50%;
	flex: none;
}
.pol-party {
	color: var(--ink-3);
}

/* ── Content ───────────────────────────────────────────────────────── */
.content {
	display: flex;
	flex-direction: column;
	gap: 1.4rem;
	min-width: 0;
	position: relative;
}

/* dim everything except the scanner overlay when loading */
.content.scanning > :not(.data-scan) {
	opacity: 0.45;
	filter: blur(0.4px) saturate(0.7);
	transition:
		opacity 0.35s ease,
		filter 0.35s ease;
}
.content:not(.scanning) > :not(.data-scan) {
	opacity: 1;
	filter: none;
	transition:
		opacity 0.45s ease,
		filter 0.45s ease;
}

/* ── Data scan overlay ──────────────────────────────────────────────── */
.data-scan {
	position: absolute;
	inset: 0;
	z-index: 20;
	pointer-events: none;
	overflow: hidden;
	border-radius: 14px;
}

/* The main glowing beam */
.scan-beam {
	position: absolute;
	left: -5%;
	right: -5%;
	height: 2px;
	background: linear-gradient(
		90deg,
		transparent 0%,
		color-mix(in srgb, var(--accent) 30%, transparent) 10%,
		var(--accent) 35%,
		#c084fc 55%,
		var(--spark) 75%,
		color-mix(in srgb, var(--spark) 30%, transparent) 90%,
		transparent 100%
	);
	box-shadow:
		0 0 6px 2px color-mix(in srgb, var(--accent) 70%, transparent),
		0 0 20px 6px color-mix(in srgb, var(--accent) 35%, transparent),
		0 0 60px 16px color-mix(in srgb, var(--accent) 12%, transparent);
	animation: beam-sweep 2.2s cubic-bezier(0.4, 0, 0.4, 1) infinite;
}

/* Soft trailing fade below the beam */
.scan-trail {
	position: absolute;
	left: 0;
	right: 0;
	height: 120px;
	background: linear-gradient(
		to bottom,
		color-mix(in srgb, var(--accent) 8%, transparent) 0%,
		transparent 100%
	);
	animation: trail-sweep 2.2s cubic-bezier(0.4, 0, 0.4, 1) infinite;
}

@keyframes beam-sweep {
	0% {
		top: -4px;
		opacity: 0;
	}
	4% {
		opacity: 1;
	}
	96% {
		opacity: 1;
	}
	100% {
		top: calc(100% + 4px);
		opacity: 0;
	}
}
@keyframes trail-sweep {
	0% {
		top: -124px;
		opacity: 0;
	}
	4% {
		opacity: 1;
	}
	96% {
		opacity: 1;
	}
	100% {
		top: calc(100% + 4px);
		opacity: 0;
	}
}

/* Floating label that follows the beam */
.scan-label {
	position: absolute;
	right: 1.5rem;
	display: flex;
	align-items: center;
	gap: 0.45rem;
	background: color-mix(in srgb, var(--bg) 80%, transparent);
	border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent);
	border-radius: 999px;
	padding: 0.25rem 0.75rem 0.25rem 0.55rem;
	box-shadow: 0 0 12px color-mix(in srgb, var(--accent) 25%, transparent);
	animation: label-sweep 2.2s cubic-bezier(0.4, 0, 0.4, 1) infinite;
}
@keyframes label-sweep {
	0% {
		top: -18px;
		opacity: 0;
	}
	4% {
		opacity: 1;
	}
	96% {
		opacity: 1;
	}
	100% {
		top: calc(100% - 8px);
		opacity: 0;
	}
}

.scan-dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: var(--accent);
	box-shadow: 0 0 6px var(--accent);
	animation: dot-blink 0.8s ease-in-out infinite alternate;
}
@keyframes dot-blink {
	from {
		opacity: 1;
	}
	to {
		opacity: 0.3;
	}
}

.scan-text {
	font-size: 0.62rem;
	font-weight: 700;
	letter-spacing: 0.14em;
	color: var(--accent);
	font-family: var(--display);
}

/* ── Hero ──────────────────────────────────────────────────────────── */
.hero-wrap {
	display: flex;
	flex-direction: column;
	gap: 0;
}
.hero-controls {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	margin-bottom: 0.75rem;
}
.view-tabs {
	display: inline-flex;
	background: var(--surface-2);
	border: 1px solid var(--line-2);
	border-radius: 999px;
	padding: 3px;
	gap: 2px;
}
.view-tab {
	display: inline-flex;
	align-items: center;
	gap: 0.45rem;
	font: inherit;
	font-size: 0.85rem;
	font-weight: 600;
	padding: 0.5rem 1.15rem;
	border: none;
	border-radius: 999px;
	background: transparent;
	color: var(--ink-3);
	cursor: pointer;
	transition:
		background 0.2s,
		color 0.2s,
		box-shadow 0.2s;
	white-space: nowrap;
}
.view-tab:hover:not(.active) {
	color: var(--ink-2);
	background: var(--surface-3);
}
.view-tab.active {
	background: var(--surface);
	color: var(--ink);
	box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
}
.view-tab.active svg {
	filter: drop-shadow(0 0 4px var(--accent));
	color: var(--accent);
}

/* ── Flip ──────────────────────────────────────────────────────────── */
.flip-container {
	perspective: 1400px;
}
.flip-inner {
	position: relative;
	transform-style: preserve-3d;
	transition: transform 0.65s cubic-bezier(0.4, 0.2, 0.2, 1);
}
.flip-inner.flipped {
	transform: rotateY(180deg);
}
.flip-face {
	backface-visibility: hidden;
	-webkit-backface-visibility: hidden;
}
.flip-back {
	position: absolute;
	inset: 0;
	transform: rotateY(180deg);
	overflow-y: auto;
}

.panel {
	padding: 1.4rem 1.5rem;
}
.panel.solid {
	background: var(--surface);
	backdrop-filter: none;
	border-color: var(--line-2);
}
.p-head {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 1rem;
	margin-bottom: 1.1rem;
	flex-wrap: wrap;
}
.p-head h3 {
	margin: 0;
}
.p-hint {
	margin: 0.3rem 0 0;
	font-size: 0.8rem;
	color: var(--ink-3);
}

.slider {
	display: flex;
	align-items: center;
	gap: 0.55rem;
	font-size: 0.82rem;
	color: var(--ink-2);
}
.slider input[type='range'] {
	accent-color: var(--accent);
	width: 110px;
}

.grid-2 {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 1.4rem;
	align-items: start;
}
.party-body {
	display: grid;
	grid-template-columns: 1fr;
	gap: 1.5rem;
	align-items: start;
}
.party-body > .donut-cell {
	justify-self: center;
	max-width: 220px;
	width: 100%;
}

.empty,
.err {
	color: var(--ink-3);
	padding: 2rem 0;
	text-align: center;
}
.err {
	color: var(--spark);
}
.empty-state {
	padding: 4rem 2rem;
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 1.2rem;
	color: var(--ink-3);
	text-align: center;
}

/* ── Zero-results designed moment ──────────────────────────────────── */
.empty-state.zero {
	gap: 0.85rem;
}
.zero-icon {
	margin-bottom: 0.4rem;
	opacity: 0.9;
}
.zero-title {
	margin: 0;
	font-family: var(--display);
	font-size: 1.35rem;
	color: var(--ink);
	letter-spacing: -0.01em;
}
.zero-sub {
	margin: 0;
	max-width: 36ch;
	color: var(--ink-3);
}
.zero-suggest {
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	justify-content: center;
	gap: 0.4rem;
	margin-top: 0.6rem;
}
.zero-lbl {
	font-size: 0.72rem;
	font-weight: 600;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: var(--ink-3);
	margin-right: 0.15rem;
}

/* ── First-load skeleton ───────────────────────────────────────────── */
.skeleton {
	display: flex;
	flex-direction: column;
	gap: 1.4rem;
}
.sk-tabs {
	display: flex;
	gap: 0.5rem;
}
.sk-tabs .sk-shimmer {
	width: 130px;
	height: 38px;
	border-radius: 999px;
}
.sk-hero {
	height: 420px;
	border-radius: 14px;
}
.sk-panel {
	height: 280px;
	border-radius: 14px;
}
.sk-shimmer {
	position: relative;
	overflow: hidden;
	background: var(--surface-2);
	border: 1px solid var(--line);
}
.sk-shimmer::after {
	content: '';
	position: absolute;
	inset: 0;
	transform: translateX(-100%);
	background: linear-gradient(
		90deg,
		transparent 0%,
		color-mix(in srgb, var(--accent) 9%, transparent) 45%,
		color-mix(in srgb, var(--spark, var(--accent)) 12%, transparent) 55%,
		transparent 100%
	);
	animation: sk-sweep 1.5s ease-in-out infinite;
}
@keyframes sk-sweep {
	to {
		transform: translateX(100%);
	}
}
@media (prefers-reduced-motion: reduce) {
	.sk-shimmer::after {
		animation: none;
	}
}

/* ── Responsive ────────────────────────────────────────────────────── */
@media (max-width: 860px) {
	.grid-2 {
		grid-template-columns: 1fr;
	}
	.p-head {
		flex-direction: column;
	}
	.pol-picker {
		width: 100%;
		max-width: none;
	}
	.pol-input-wrap {
		max-width: none;
	}
}
@media (max-width: 520px) {
	.controls-row {
		gap: 0.6rem;
	}
	/* Larger tap targets for thumbs (≈44px) on the segmented toggles
	   and the politician-picker clear button. */
	.seg button {
		padding: 0.55rem 0.85rem;
		min-height: 40px;
	}
	.pol-clr {
		padding: 0.5rem;
		font-size: 0.85rem;
	}
}
</style>
