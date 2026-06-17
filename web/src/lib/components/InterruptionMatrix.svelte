<script lang="ts">
	import { partyColor, partyFoundingOrder } from '$lib/format';
	import { formatNumber } from '$lib/format';
	import { i18n } from '$lib/i18n.svelte';
	import { api } from '$lib/api';
	import type { ZwischenrufMatrixRow, ZwischenrufSample } from '$lib/types';

	// `axisRow`/`axisCol`/`noun` let the same matrix serve both the heckling and the
	// applause view (the words "calling/interrupted/interjections" are wrong for applause).
	let {
		rows,
		showSamples = false,
		axisRow = i18n.t('mx_axis_calling'),
		axisCol = i18n.t('mx_axis_interrupted'),
		noun = i18n.t('mx_noun_zw')
	}: {
		rows: ZwischenrufMatrixRow[];
		showSamples?: boolean;
		axisRow?: string;
		axisCol?: string;
		noun?: string;
	} = $props();

	// Derive ordered party lists from data
	const callers = $derived(
		[...new Set(rows.map((r) => r.caller_party))].sort(
			(a, b) => partyFoundingOrder(a) - partyFoundingOrder(b)
		)
	);
	const targets = $derived(
		[...new Set(rows.map((r) => r.target_speaker_party))].sort(
			(a, b) => partyFoundingOrder(a) - partyFoundingOrder(b)
		)
	);

	function totalByParty(party: string, role: 'caller' | 'target'): number {
		return rows
			.filter((r) => (role === 'caller' ? r.caller_party : r.target_speaker_party) === party)
			.reduce((s, r) => s + r.n, 0);
	}

	// Lookup map for O(1) cell access
	const lookup = $derived(
		new Map(rows.map((r) => [`${r.caller_party}→${r.target_speaker_party}`, r.n]))
	);
	const maxVal = $derived(Math.max(1, ...rows.map((r) => r.n)));

	function cell(caller: string, target: string): number {
		return lookup.get(`${caller}→${target}`) ?? 0;
	}

	// Intensity mapped to alpha: 0 → 0.04, max → 0.88
	function intensity(n: number): number {
		return n === 0 ? 0 : 0.08 + (n / maxVal) * 0.8;
	}

	// Abbreviate long party names for tight cells
	function abbrev(party: string): string {
		const MAP: Record<string, string> = {
			'Bündnis 90/Die Grünen': 'Grüne',
			'Die Linke': 'Linke',
			'CDU/CSU': 'CDU/CSU',
			Fraktionslos: 'fraktlos',
			Unknown: '?'
		};
		return MAP[party] ?? party;
	}

	let hoveredCell = $state<{ caller: string; target: string; n: number } | null>(null);
	let samples = $state<ZwischenrufSample[]>([]);
	let samplesLoading = $state(false);
	let samplesDebounce: ReturnType<typeof setTimeout>;

	function fetchSamples(caller: string, target: string) {
		if (!showSamples) return;
		clearTimeout(samplesDebounce);
		samples = [];
		samplesDebounce = setTimeout(async () => {
			samplesLoading = true;
			try {
				samples = await api.zwischenrufe.samples({ callerParty: caller, targetParty: target, limit: 5 });
			} finally {
				samplesLoading = false;
			}
		}, 180);
	}
</script>

<div class="matrix-wrap">
	<div class="grid" style:--cols={targets.length + 1} style:--rows={callers.length + 1}>
		<!-- Top-left corner -->
		<div class="corner">
			<span class="axis-label row-axis">{axisRow}</span>
			<span class="axis-label col-axis">{axisCol}</span>
		</div>

		<!-- Column headers (target parties) -->
		{#each targets as target}
			<div class="header col-header" title={target}>
				<span class="dot" style:background={partyColor(target)}></span>
				{abbrev(target)}
			</div>
		{/each}

		<!-- Rows: one per calling party -->
		{#each callers as caller}
			<!-- Row header -->
			<div class="header row-header" title={caller}>
				<span class="dot" style:background={partyColor(caller)}></span>
				{abbrev(caller)}
			</div>

			<!-- Data cells -->
			{#each targets as target}
				{@const n = cell(caller, target)}
				{@const alpha = intensity(n)}
				{@const isSelf = caller === target}
				<!-- role + tabindex are both gated on n > 0, so a focusable cell is always a button -->
				<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
				<div
					class="cell"
					class:self={isSelf}
					class:active={n > 0}
					style:--alpha={alpha}
					style:--cc={partyColor(caller)}
					role={n > 0 ? 'button' : 'presentation'}
					tabindex={n > 0 ? 0 : undefined}
					aria-label={n > 0 ? `${caller} → ${target}: ${formatNumber(n, i18n.lang)} ${noun}` : undefined}
					onmouseenter={() => {
						hoveredCell = n > 0 ? { caller, target, n } : null;
						if (n > 0) fetchSamples(caller, target);
					}}
					onmouseleave={() => { hoveredCell = null; clearTimeout(samplesDebounce); }}
					onfocus={() => {
						hoveredCell = n > 0 ? { caller, target, n } : null;
						if (n > 0) fetchSamples(caller, target);
					}}
					onblur={() => { hoveredCell = null; clearTimeout(samplesDebounce); }}
				>
					{#if n > 0}
						<span class="n">{formatNumber(n, i18n.lang)}</span>
					{/if}
				</div>
			{/each}
		{/each}
	</div>

	<!-- Intensity legend + diagonal note -->
	<div class="mx-foot">
		<div class="mx-legend">
			<span>{i18n.t('mx_legend_less')}</span>
			<span class="mx-ramp" aria-hidden="true"></span>
			<span>{i18n.t('mx_legend_more')}</span>
		</div>
		<span class="mx-diag-note"><span class="mx-diag-swatch" aria-hidden="true"></span>{i18n.t('mx_diagonal')}</span>
	</div>

	<!-- Hover panel -->
	{#if hoveredCell}
		<div class="tooltip" class:has-samples={showSamples}>
			<div class="tt-header">
				<span class="tt-from" style:color={partyColor(hoveredCell.caller)}>{hoveredCell.caller}</span>
				<span class="tt-arrow">→</span>
				<span class="tt-to" style:color={partyColor(hoveredCell.target)}>{hoveredCell.target}</span>
				<strong class="tt-n">{formatNumber(hoveredCell.n, i18n.lang)} {noun}</strong>
			</div>
			{#if showSamples}
				<div class="tt-samples">
					{#if samplesLoading}
						<span class="tt-loading">…</span>
					{:else if samples.length}
						{#each samples as s}
							<div class="tt-sample">
								<span class="tt-caller" style:color={partyColor(s.caller_party ?? '')}>
									{s.caller_name ?? s.caller_party}
								</span>
								<span class="tt-quote">„{s.text}"</span>
							</div>
						{/each}
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.matrix-wrap {
		position: relative;
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
	}

	.grid {
		display: grid;
		grid-template-columns: minmax(72px, auto) repeat(calc(var(--cols) - 1), minmax(52px, 1fr));
		gap: 3px;
		min-width: max-content;
	}

	.corner {
		display: flex;
		flex-direction: column;
		justify-content: flex-end;
		padding: 0 6px 4px 0;
		gap: 2px;
	}
	.axis-label {
		font-size: 0.64rem;
		font-weight: 600;
		color: var(--ink-2);
		letter-spacing: 0.04em;
		text-transform: lowercase;
		white-space: nowrap;
	}

	.header {
		display: flex;
		align-items: center;
		gap: 5px;
		font-size: 0.72rem;
		font-weight: 600;
		color: var(--ink-2);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.col-header {
		flex-direction: column;
		align-items: flex-start;
		justify-content: flex-end;
		padding: 0 2px 5px;
		writing-mode: vertical-lr;
		transform: rotate(180deg);
		height: 90px;
		font-size: 0.68rem;
	}
	.col-header .dot {
		margin: 0;
	}
	.row-header {
		padding: 2px 6px 2px 2px;
		justify-content: flex-end;
		text-align: right;
	}

	.dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		flex: none;
	}

	.cell {
		height: 44px;
		border-radius: 6px;
		background: rgba(107, 145, 255, calc(var(--alpha) * 0.5));
		border: 1px solid rgba(255, 255, 255, 0.04);
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: default;
		transition: background 0.15s, border-color 0.15s, transform 0.15s;
		position: relative;
	}
	.cell.active {
		background: color-mix(in srgb, var(--cc) calc(var(--alpha) * 80%), transparent);
		border-color: color-mix(in srgb, var(--cc) 30%, transparent);
		box-shadow: 0 0 0 0 var(--cc);
		cursor: pointer;
	}
	.cell.active:hover,
	.cell.active:focus-visible {
		transform: scale(1.08);
		border-color: color-mix(in srgb, var(--cc) 60%, transparent);
		box-shadow: 0 0 16px -4px var(--cc);
		z-index: 2;
		outline: none;
	}
	.cell.active:focus-visible {
		box-shadow: 0 0 0 2px var(--accent), 0 0 16px -4px var(--cc);
	}
	.cell.self.active {
		box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--cc) 65%, transparent);
	}
	.cell.self.active::after {
		content: '';
		position: absolute;
		inset: 3px;
		border-radius: 4px;
		border: 1px dashed color-mix(in srgb, var(--cc) 55%, transparent);
		pointer-events: none;
	}

	.n {
		font-size: 0.7rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		color: var(--ink);
		line-height: 1;
	}

	.tooltip {
		position: sticky;
		bottom: 0;
		left: 0;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		padding: 0.6rem 1rem;
		background: var(--surface-2);
		border: 1px solid var(--line-2);
		border-radius: 12px;
		font-size: 0.82rem;
		margin-top: 0.6rem;
	}
	.tooltip:not(.has-samples) {
		border-radius: 999px;
		flex-direction: row;
		align-items: center;
	}
	.tt-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.tt-arrow {
		color: var(--ink-3);
	}
	.tt-n {
		margin-left: 0.3rem;
		font-variant-numeric: tabular-nums;
		color: var(--ink);
	}
	.tt-samples {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		border-top: 1px solid var(--line-2);
		padding-top: 0.5rem;
	}
	.tt-loading {
		color: var(--ink-3);
		font-size: 0.78rem;
	}
	.tt-sample {
		display: flex;
		gap: 0.5rem;
		align-items: baseline;
		font-size: 0.78rem;
		line-height: 1.4;
	}
	.tt-caller {
		font-weight: 600;
		white-space: nowrap;
		flex-shrink: 0;
	}
	.tt-quote {
		color: var(--ink-2);
		font-style: italic;
	}

	/* Footer: intensity legend + diagonal note */
	.mx-foot {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 0.6rem 1rem;
		margin-top: 0.9rem;
		padding-top: 0.7rem;
		border-top: 1px solid var(--line);
	}
	.mx-legend {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.7rem;
		color: var(--ink-3);
	}
	.mx-ramp {
		width: 120px;
		height: 8px;
		border-radius: 999px;
		background: linear-gradient(
			90deg,
			color-mix(in srgb, var(--accent) 8%, var(--surface-2)),
			var(--accent)
		);
		border: 1px solid var(--line);
	}
	.mx-diag-note {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.7rem;
		color: var(--ink-3);
	}
	.mx-diag-swatch {
		width: 14px;
		height: 14px;
		border-radius: 4px;
		background: color-mix(in srgb, var(--ink-2) 18%, transparent);
		border: 1px dashed color-mix(in srgb, var(--ink-2) 55%, transparent);
		flex: none;
	}
</style>
