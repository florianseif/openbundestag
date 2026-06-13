<script lang="ts">
	import { countUp, formatNumber } from '$lib/format';
	import { i18n } from '$lib/i18n.svelte';

	let { value }: { value: number } = $props();
	let shown = $state(0);

	// Re-run the count-up whenever the target changes.
	$effect(() => {
		const target = value;
		return countUp(target, (v) => (shown = v), 850);
	});
</script>

<span class="num">{formatNumber(shown, i18n.lang)}</span>

<style>
	.num {
		font-variant-numeric: tabular-nums;
	}
</style>
