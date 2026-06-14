<script lang="ts">
	// Reusable "Wahlperiode" filter bar — a horizontal scroller of electoral-term
	// chips. Binds to an array of term numbers (empty = all terms). Clicking a
	// single anchor then another chip selects the contiguous range between them.
	// Shared by the explorer and the Zwischenrufe page.
	import { partyColor } from '$lib/format';
	import governmentsRaw from '$lib/governments.json';
	import type { TermInfo } from '$lib/types';

	let {
		selected = $bindable(),
		options
	}: { selected: number[]; options: TermInfo[] } = $props();

	function toggleTerm(term: number) {
		const cur = selected;
		// Clicking the only selected term clears the selection.
		if (cur.length === 1 && cur[0] === term) {
			selected = [];
			return;
		}
		// A single term is selected → extend to the contiguous range between the
		// anchor and the clicked term (inclusive), filling in everything between.
		if (cur.length === 1) {
			const all = options.map((t) => t.term);
			const lo = Math.min(cur[0], term);
			const hi = Math.max(cur[0], term);
			selected = all.filter((t) => t >= lo && t <= hi).sort((a, b) => a - b);
			return;
		}
		// No selection, or a range is already active → start fresh from this term.
		selected = [term];
	}

	// Terms sorted newest-first for the chip row
	const sortedTerms = $derived([...options].sort((a, b) => b.term - a.term));

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
	const termChancellors = $derived.by(() => {
		// Map each electoral term to the chancellor who governed for MOST of it.
		// A term's window can span two governments (e.g. WP 20 starts under Merkel
		// in 2021 but Scholz took office that December and governed the rest), so we
		// pick the government with the largest temporal overlap — not the one merely
		// in office on the term's first day.
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
</script>

<div class="term-row">
	<div class="term-row-head">
		<span class="term-row-lbl">Wahlperiode</span>
		{#if selected.length > 0}
			<button class="term-clear" onclick={() => (selected = [])}>Alle anzeigen</button>
		{/if}
	</div>
	<div class="term-scroller">
		{#each sortedTerms as t (t.term)}
			{@const years = t.label.match(/\((.+?)\)/)?.[1] ?? ''}
			{@const ch = termChancellors[t.term]}
			{@const chipColor = ch ? partyColor(ch.party) : 'var(--line-2)'}
			<button
				class="term-chip"
				class:active={selected.includes(t.term)}
				onclick={() => toggleTerm(t.term)}
				title={t.label + (ch ? ' · ' + ch.name : '')}
				style="--chip-color: {chipColor}"
			>
				<span class="chip-body">
					<span class="chip-era">WP</span>
					<span class="chip-num">{t.term}</span>
					<span class="chip-years">{years}</span>
					{#if ch}
						<span class="chip-chancellor">
							<span class="chip-dot"></span>{shortChancellor(ch.name)}
						</span>
					{/if}
				</span>
			</button>
		{/each}
	</div>
</div>

<style>
	/* ── Wahlperioden chips ─────────────────────────────────────────────── */
	.term-row {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
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
		opacity: 0.45;
		filter: blur(10px);
		z-index: -1;
		pointer-events: none;
		animation: aurora-spin 4s linear infinite;
	}
	@keyframes aurora-spin {
		from { filter: blur(10px) hue-rotate(0deg); }
		to   { filter: blur(10px) hue-rotate(360deg); }
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
