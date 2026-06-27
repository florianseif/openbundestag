<script setup lang="ts">
import { ref, computed, watchEffect } from 'vue';
import { pie, arc } from 'd3-shape';
import { i18n } from '$lib/i18n';
import { formatNumber, countUp } from '$lib/format';

interface Slice {
	label: string;
	value: number;
	color: string;
}
const { slices } = defineProps<{ slices: Slice[] }>();

const R = 120;
const total = computed(() => slices.reduce((s, d) => s + d.value, 0));
const arcs = computed(() =>
	pie<Slice>()
		.value((d) => d.value)
		.sort(null)(slices)
);
const gen = arc<(typeof arcs.value)[number]>()
	.innerRadius(R * 0.58)
	.outerRadius(R)
	.padAngle(0.012)
	.cornerRadius(3);

const hover = ref<number | null>(null);
const active = computed(() => (hover.value != null ? slices[hover.value] : null));

// Morph the resting centre total between values when the data changes.
// Hover shows the focused slice's raw value instantly (no per-hover tween).
const shownTotal = ref(0);
let curTotal = 0;
watchEffect((onCleanup) => {
	const target = total.value;
	const cancel = countUp(
		target,
		(v) => {
			curTotal = v;
			shownTotal.value = v;
		},
		650,
		curTotal
	);
	onCleanup(cancel);
});
</script>

<template>
	<div class="donut">
		<svg
			:viewBox="`${-R - 4} ${-R - 4} ${2 * R + 8} ${2 * R + 8}`"
			role="img"
			aria-label="Share by party"
		>
			<path
				v-for="(a, i) in arcs"
				:key="a.data.label"
				:d="gen(a) ?? undefined"
				:fill="a.data.color"
				stroke="var(--surface)"
				stroke-width="1.5"
				:opacity="hover == null || hover === i ? 1 : 0.32"
				:transform="hover === i ? 'scale(1.04)' : 'scale(1)'"
				@mouseenter="hover = i"
				@mouseleave="hover = null"
				role="presentation"
			/>
			<text class="center-v" text-anchor="middle" dy="-0.1em">
				{{
					active
						? formatNumber(active.value, i18n.lang)
						: formatNumber(shownTotal, i18n.lang)
				}}
			</text>
			<text class="center-l" text-anchor="middle" dy="1.3em">
				{{ active ? active.label : i18n.t('metric_speeches') }}
			</text>
		</svg>
	</div>
</template>

<style scoped>
.donut {
	display: flex;
	justify-content: center;
}
svg {
	width: 100%;
	max-width: 300px;
	height: auto;
}
path {
	cursor: pointer;
	transform-origin: center;
	transition:
		opacity 0.2s,
		transform 0.25s var(--spring);
}
.center-v {
	fill: var(--ink);
	font-family: var(--serif);
	font-size: 2rem;
	font-weight: 600;
}
.center-l {
	fill: var(--ink-3);
	font-size: 0.8rem;
	font-family: var(--sans);
}
</style>
