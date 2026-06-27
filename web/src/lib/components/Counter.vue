<script setup lang="ts">
// REFERENCE PORT — mirrors Counter.svelte. Shows the runes -> Vue mapping:
//   $props()  -> defineProps (destructured props are reactive in Vue 3.5+)
//   $state(0) -> ref(0)  (use .value in <script>, auto-unwrapped in <template>)
//   $effect(fn returning cleanup) -> watchEffect((onCleanup) => { ...; onCleanup(cancel) })
//   i18n.lang -> unchanged (reactive store, same API)
import { ref, watchEffect } from 'vue';
import { countUp, formatNumber } from '$lib/format';
import { i18n } from '$lib/i18n';

const { value, dur = 850 } = defineProps<{ value: number; dur?: number }>();

const shown = ref(0);
// Latest emitted value, kept non-reactive so reading it as the tween origin
// doesn't re-trigger the effect.
let current = 0;

watchEffect((onCleanup) => {
	const target = value;
	const cancel = countUp(
		target,
		(v) => {
			current = v;
			shown.value = v;
		},
		dur,
		current
	);
	onCleanup(cancel);
});
</script>

<template>
	<span class="num">{{ formatNumber(shown, i18n.lang) }}</span>
</template>

<style scoped>
.num {
	font-variant-numeric: tabular-nums;
}
</style>
