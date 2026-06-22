<script lang="ts">
	import Counter from './Counter.svelte';

	interface Bar {
		label: string;
		sub?: string;
		value: number;
		color: string;
	}
	let { bars, valueLabel = '' }: { bars: Bar[]; valueLabel?: string } = $props();

	const maxVal = $derived(Math.max(1, ...bars.map((b) => b.value)));
</script>

<div class="bars" style:--n={bars.length}>
	{#each bars as b, i (b.label + i)}
		<div class="row" style:--i={i}>
			<div class="label" title={b.label}>
				{b.label}
				{#if b.sub}<span class="sub">{b.sub}</span>{/if}
			</div>
			<div class="track">
				<div
					class="fill"
					style:width="{(b.value / maxVal) * 100}%"
					style:background={b.color}
					style:color={b.color}
				></div>
			</div>
			<div class="val"><Counter value={b.value} dur={650} /></div>
		</div>
	{/each}
	{#if valueLabel}<div class="cap">{valueLabel}</div>{/if}
</div>

<style>
	.bars {
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
	}
	.row {
		display: grid;
		grid-template-columns: minmax(90px, 26%) 1fr auto;
		align-items: center;
		gap: 0.7rem;
		animation: slide 0.5s var(--ease) backwards;
		animation-delay: calc(var(--i) * 30ms);
	}
	.label {
		font-size: 0.85rem;
		font-weight: 500;
		color: var(--ink-2);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		text-align: right;
	}
	.sub {
		display: block;
		font-size: 0.72rem;
		color: var(--ink-3);
		font-weight: 400;
	}
	.track {
		height: 22px;
		background: var(--surface-2);
		border: 1px solid var(--line);
		border-radius: 7px;
		overflow: hidden;
	}
	.fill {
		height: 100%;
		border-radius: 6px;
		transform-origin: left;
		filter: saturate(1.05) brightness(1.05);
		box-shadow: 0 0 18px -4px currentColor;
		animation: grow 0.7s var(--ease) backwards;
		animation-delay: calc(var(--i) * 30ms);
	}
	.val {
		font-variant-numeric: tabular-nums;
		font-weight: 600;
		font-size: 0.85rem;
		min-width: 3ch;
		text-align: right;
	}
	.cap {
		margin-top: 0.3rem;
		font-size: 0.72rem;
		color: var(--ink-3);
		text-align: right;
	}
	@keyframes grow {
		from {
			transform: scaleX(0);
		}
	}
	@keyframes slide {
		from {
			opacity: 0;
			transform: translateY(6px);
		}
	}
</style>
