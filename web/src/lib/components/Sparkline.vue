<script setup lang="ts">
import { computed } from 'vue';
import { scaleLinear } from 'd3-scale';
import { line, area, curveMonotoneX } from 'd3-shape';

interface Point {
	year: number;
	value: number;
}
const { series, color = 'var(--accent)', progress = 1 } = defineProps<{
	series: Point[];
	color?: string;
	progress?: number;
}>();

const W = 600;
const H = 200;
const pad = { t: 12, r: 8, b: 8, l: 8 };

const x = computed(() =>
	scaleLinear()
		.domain([series[0]?.year ?? 0, series[series.length - 1]?.year ?? 1])
		.range([pad.l, W - pad.r])
);
const y = computed(() =>
	scaleLinear()
		.domain([0, Math.max(1, ...series.map((d) => d.value))])
		.range([H - pad.b, pad.t])
);

// progress (0..1) reveals the line left-to-right as the story scrolls in.
const shown = computed(() => series.slice(0, Math.max(2, Math.ceil(series.length * progress))));

const linePath = computed(
	() =>
		line<Point>()
			.x((d) => x.value(d.year))
			.y((d) => y.value(d.value))
			.curve(curveMonotoneX)(shown.value) ?? ''
);
const areaPath = computed(
	() =>
		area<Point>()
			.x((d) => x.value(d.year))
			.y0(H - pad.b)
			.y1((d) => y.value(d.value))
			.curve(curveMonotoneX)(shown.value) ?? ''
);
const last = computed(() => shown.value[shown.value.length - 1]);
const gid = `sg-${Math.random().toString(36).slice(2, 8)}`;
</script>

<template>
	<svg
		:viewBox="`0 0 ${W} ${H}`"
		preserveAspectRatio="none"
		class="spark"
		role="img"
		aria-hidden="true"
	>
		<defs>
			<linearGradient :id="gid" x1="0" x2="0" y1="0" y2="1">
				<stop offset="0%" :stop-color="color" stop-opacity="0.32" />
				<stop offset="100%" :stop-color="color" stop-opacity="0" />
			</linearGradient>
		</defs>
		<path :d="areaPath" :fill="`url(#${gid})`" />
		<path :d="linePath" fill="none" :stroke="color" stroke-width="3" stroke-linecap="round" />
		<circle v-if="last" :cx="x(last.year)" :cy="y(last.value)" r="5" :fill="color" />
	</svg>
</template>

<style scoped>
.spark {
	width: 100%;
	height: 100%;
	display: block;
}
</style>
