<script setup lang="ts">
// Reusable "Wahlperiode" filter bar — a horizontal scroller of electoral-term
// chips. Binds to an array of term numbers (empty = all terms). Clicking a
// single anchor then another chip selects the contiguous range between them.
// Shared by the explorer and the Zwischenrufe page.
//
// Runes → Vue mapping:
//   selected = $bindable()      → defineModel<number[]>('selected') — parent uses v-model:selected
//   $derived(...)               → computed(...)
//   $derived.by(() => {...})    → computed(() => {...})
//   $state() template ref       → ref<HTMLDivElement | null>(null) + ref="scroller" on element
//   $effect (scroll init)       → watchEffect (tracks scroller.value; fires after mount)
//   {@const ...} in #each       → pre-computed processedTerms array (no local vars in v-for)
import { ref, computed, watchEffect } from 'vue';
import { partyColor } from '$lib/format';
import { i18n } from '$lib/i18n';
import governmentsRaw from '$lib/governments.json';
import type { TermInfo } from '$lib/types';

// $bindable() → defineModel (parent binds with v-model:selected)
const selected = defineModel<number[]>('selected', { required: true });
const { options } = defineProps<{ options: TermInfo[] }>();

function toggleTerm(term: number) {
	const cur = selected.value;
	// Clicking the only selected term clears the selection.
	if (cur.length === 1 && cur[0] === term) {
		selected.value = [];
		return;
	}
	// A single term is selected → extend to the contiguous range between the
	// anchor and the clicked term (inclusive), filling in everything between.
	if (cur.length === 1) {
		const all = options.map((t) => t.term);
		const lo = Math.min(cur[0], term);
		const hi = Math.max(cur[0], term);
		selected.value = all.filter((t) => t >= lo && t <= hi).sort((a, b) => a - b);
		return;
	}
	// No selection, or a range is already active → start fresh from this term.
	selected.value = [term];
}

// Oldest→newest, left→right — matching the timeline's time axis
const sortedTerms = computed(() => [...options].sort((a, b) => a.term - b.term));

// Template ref for the scroller div (bind:this → ref="scroller")
const scroller = ref<HTMLDivElement | null>(null);
let didInitScroll = false;

// $effect → watchEffect: tracks scroller.value (null before mount, set after).
// Fires again after mount when scroller.value is assigned and scrolls to end.
watchEffect(() => {
	if (scroller.value && !didInitScroll && sortedTerms.value.length) {
		scroller.value.scrollLeft = scroller.value.scrollWidth;
		didInitScroll = true;
	}
});

// --- chancellor lookup for term chips -------------------------------------
function govPartyToDisplay(code: string): string {
	if (code === 'CDU' || code === 'CSU') return 'CDU/CSU';
	if (code === 'Grüne') return 'Bündnis 90/Die Grünen';
	return code;
}
function shortChancellor(name: string): string {
	const parts = name.split(' ');
	return parts[parts.length - 1];
}

// $derived.by(() => {...}) → computed(() => {...})
const termChancellors = computed<Record<number, { name: string; party: string }>>(() => {
	// Map each electoral term to the chancellor who governed for MOST of it.
	const result: Record<number, { name: string; party: string }> = {};
	const today = new Date();
	for (const t of options) {
		const m = t.label.match(/\((\d{4})\s*[–-]\s*(\d{4})?/);
		if (!m) continue;
		const winStart = new Date(`${m[1]}-01-01`).getTime();
		const winEnd = (m[2] ? new Date(`${m[2]}-12-31`) : today).getTime();
		let best: (typeof governmentsRaw)[number] | null = null;
		let bestOverlap = 0;
		for (const g of governmentsRaw) {
			const gStart = new Date(g.start).getTime();
			const gEnd = g.end ? new Date(g.end).getTime() : today.getTime();
			const overlap = Math.min(gEnd, winEnd) - Math.max(gStart, winStart);
			if (overlap > bestOverlap) {
				bestOverlap = overlap;
				best = g;
			}
		}
		if (best) result[t.term] = { name: best.chancellor, party: govPartyToDisplay(best.parties[0]) };
	}
	return result;
});

// Pre-compute per-chip derived values (replaces {@const ...} locals in #each blocks,
// which have no equivalent in Vue v-for templates).
interface ProcessedTerm extends TermInfo {
	years: string;
	ch: { name: string; party: string } | undefined;
	chipColor: string;
}

const processedTerms = computed<ProcessedTerm[]>(() =>
	sortedTerms.value.map((t) => {
		const years = t.label.match(/\((.+?)\)/)?.[1] ?? '';
		const ch = termChancellors.value[t.term];
		const chipColor = ch ? partyColor(ch.party) : 'var(--line-2)';
		return { ...t, years, ch, chipColor };
	})
);
</script>

<template>
	<div class="term-row">
		<div class="term-row-head">
			<span class="term-row-lbl">{{ i18n.t('wahlperiode') }}</span>
			<!-- Vue 3.4+ auto-unwraps defineModel refs in inline template assignments -->
			<button v-if="selected.length > 0" class="term-clear" @click="selected = []">
				{{ i18n.t('show_all') }}
			</button>
		</div>
		<div class="term-scroller" ref="scroller">
			<button
				v-for="t in processedTerms"
				:key="t.term"
				class="term-chip"
				:class="{ active: selected.includes(t.term) }"
				@click="toggleTerm(t.term)"
				:title="t.label + (t.ch ? ' · ' + t.ch.name : '')"
				:style="{ '--chip-color': t.chipColor }"
			>
				<span class="chip-body">
					<span class="chip-era">WP</span>
					<span class="chip-num">{{ t.term }}</span>
					<span class="chip-years">{{ t.years }}</span>
					<span v-if="t.ch" class="chip-chancellor">
						<span class="chip-dot"></span>{{ shortChancellor(t.ch.name) }}
					</span>
				</span>
			</button>
		</div>
	</div>
</template>

<style scoped>
	/* ── Wahlperioden chips ─────────────────────────────────────────────── */
	.term-row {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		min-width: 0;
		width: 100%;
	}
	.term-row-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.term-row-lbl {
		font-size: 0.72rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-3);
	}
	.term-clear {
		font: inherit;
		font-size: 0.68rem;
		color: var(--accent);
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		opacity: 0.8;
		transition: opacity 0.15s;
	}
	.term-clear:hover { opacity: 1; }
	.term-scroller {
		display: flex;
		gap: 0.4rem;
		overflow-x: auto;
		padding-bottom: 4px;
		scrollbar-width: thin;
		scrollbar-color: var(--line-2) transparent;
	}
	.term-scroller::-webkit-scrollbar { height: 3px; }
	.term-scroller::-webkit-scrollbar-track { background: transparent; }
	.term-scroller::-webkit-scrollbar-thumb { background: var(--line-2); border-radius: 2px; }

	.term-chip {
		flex: none;
		display: flex;
		align-items: stretch;
		border-radius: 10px;
		border: 1px solid var(--line-2);
		background: var(--surface-2);
		cursor: pointer;
		overflow: hidden;
		transition: border-color 0.18s, background 0.18s, box-shadow 0.18s, transform 0.18s;
		text-align: left;
		min-width: 80px;
		position: relative;
	}
	.term-chip:hover:not(.active) {
		border-color: color-mix(in srgb, var(--chip-color, var(--line-3)) 45%, var(--line-2));
		background: var(--surface-3, var(--surface-2));
		transform: translateY(-2px);
		box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35);
	}
	.term-chip.active {
		/* Aurora gradient border — same rainbow effect as the search ring */
		overflow: visible;
		border-color: transparent;
		border-width: 2px;
		background:
			linear-gradient(var(--surface-2), var(--surface-2)) padding-box,
			var(--grad) border-box;
		box-shadow: 0 6px 22px -8px color-mix(in srgb, var(--accent) 45%, transparent);
	}
	.term-chip.active::after {
		content: '';
		position: absolute;
		inset: -3px;
		border-radius: 12px;
		background: var(--grad);
		opacity: 0.3;
		filter: blur(11px);
		z-index: -1;
		pointer-events: none;
	}
	.chip-body {
		display: flex;
		flex-direction: column;
		padding: 0.5rem 0.7rem 0.5rem;
		gap: 0;
		min-width: 0;
	}
	.chip-era {
		font-size: 0.58rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--ink-3);
		line-height: 1.2;
	}
	.chip-num {
		font-family: var(--display);
		font-size: 1.25rem;
		font-weight: 700;
		line-height: 1.1;
		letter-spacing: -0.02em;
		color: var(--ink);
		transition: color 0.18s;
	}
	.term-chip.active .chip-num { color: var(--chip-color, var(--accent)); }
	.chip-years {
		font-size: 0.62rem;
		color: var(--ink-3);
		line-height: 1.3;
		margin-top: 0.1rem;
		white-space: nowrap;
	}
	.chip-chancellor {
		display: flex;
		align-items: center;
		gap: 0.35em;
		font-size: 0.68rem;
		font-weight: 600;
		color: color-mix(in srgb, var(--chip-color, var(--ink-2)) 78%, var(--ink));
		margin-top: 0.35rem;
		white-space: nowrap;
	}
	.chip-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--chip-color, var(--line-2));
		box-shadow: 0 0 6px -1px var(--chip-color, transparent);
		flex-shrink: 0;
	}
</style>
