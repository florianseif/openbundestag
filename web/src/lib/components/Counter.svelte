<script lang="ts">
	import { countUp, formatNumber } from '$lib/format';
	import { i18n } from '$lib/i18n.svelte';

	let { value, dur = 850 }: { value: number; dur?: number } = $props();
	let shown = $state(0);
	// Latest emitted value, kept non-reactive so reading it as the tween origin
	// doesn't re-trigger the effect. First run morphs 0 → value (count-up);
	// later target changes morph from wherever the odometer currently sits.
	let current = 0;

	$effect(() => {
		const target = value;
		return countUp(target, (v) => ((current = v), (shown = v)), dur, current);
	});
</script>

<span class="num">{formatNumber(shown, i18n.lang)}</span>

<style>
	.num {
		font-variant-numeric: tabular-nums;
	}
</style>
