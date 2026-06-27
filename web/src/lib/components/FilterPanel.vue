<script setup lang="ts">
// Runes → Vue mapping:
//   filters = $bindable()  → defineModel<Filters>('filters') — parent uses v-model:filters
//   $derived(...)          → computed(...)
//   $state(v)              → ref(v)
//   $effect(() => {...})   → watch([yFrom, yTo], ..., { immediate: true })
import { ref, computed, watch } from 'vue';
import type { Filters, Meta } from '$lib/types';
import { i18n } from '$lib/i18n';

// $bindable() → defineModel (parent binds with v-model:filters)
const filters = defineModel<Filters>('filters', { required: true });
const { meta } = defineProps<{ meta: Meta }>();

const fromYear = computed(() => +meta.min_date.slice(0, 4));
const toYear = computed(() => +meta.max_date.slice(0, 4));
const years = computed(() =>
	Array.from({ length: toYear.value - fromYear.value + 1 }, (_, i) => fromYear.value + i)
);

const yFrom = ref(+(filters.value.date_from ?? '2010-01-01').slice(0, 4));
const yTo = ref(+(filters.value.date_to ?? '2026-12-31').slice(0, 4));

// $effect that writes yFrom/yTo back to filters →
// watch with immediate:true so it also fires on mount (same as $effect's eager first run)
watch(
	[yFrom, yTo],
	([from, to]) => {
		filters.value.date_from = `${from}-01-01`;
		filters.value.date_to = `${to}-12-31`;
	},
	{ immediate: true }
);

// Pre-compute filtered year lists to avoid ref-inside-callback gotcha in templates
const yFromOptions = computed(() => years.value.filter((y) => y <= yTo.value));
const yToOptions = computed(() => years.value.filter((y) => y >= yFrom.value));

const SUGGESTIONS = [
	'Schuldenbremse',
	'Klimawandel',
	'Migration',
	'Digitalisierung',
	'Rente',
	'Ukraine'
];
</script>

<template>
	<div class="panel">
		<section>
			<label class="lbl" for="kw">{{ i18n.t('keyword') }}</label>
			<input
				id="kw"
				class="kw"
				v-model="filters.word"
				:maxlength="meta.keyword_max_len"
				:placeholder="i18n.t('keyword_ph')"
				autocomplete="off"
			/>
			<div class="suggestions">
				<button
					v-for="w in SUGGESTIONS"
					:key="w"
					class="suggestion"
					@click="filters.word = w"
				>{{ w }}</button>
			</div>
		</section>

		<section>
			<span class="lbl">{{ i18n.t('period') }}</span>
			<div class="range">
				<select v-model="yFrom">
					<option v-for="y in yFromOptions" :key="y" :value="y">{{ y }}</option>
				</select>
				<span class="dash">–</span>
				<select v-model="yTo">
					<option v-for="y in yToOptions" :key="y" :value="y">{{ y }}</option>
				</select>
			</div>
		</section>

		<section class="opts">
			<span class="lbl">{{ i18n.t('granularity') }}</span>
			<div class="seg">
				<button
					:class="{ on: filters.granularity === 'Monthly' }"
					@click="filters.granularity = 'Monthly'"
				>{{ i18n.t('monthly') }}</button>
				<button
					:class="{ on: filters.granularity === 'Quarterly' }"
					@click="filters.granularity = 'Quarterly'"
				>{{ i18n.t('quarterly') }}</button>
			</div>
			<span class="lbl">{{ i18n.t('count_by') }}</span>
			<div class="seg">
				<button
					:class="{ on: filters.count_mode === 'speeches' }"
					@click="filters.count_mode = 'speeches'"
				>{{ i18n.t('speeches') }}</button>
				<button
					:class="{ on: filters.count_mode === 'occurrences' }"
					@click="filters.count_mode = 'occurrences'"
				>{{ i18n.t('occurrences') }}</button>
			</div>
		</section>
	</div>
</template>

<style scoped>
	.panel {
		display: flex;
		flex-direction: column;
		gap: 1.4rem;
	}
	.lbl {
		display: block;
		font-size: 0.78rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-3);
		margin-bottom: 0.5rem;
	}
	.kw,
	.range select {
		width: 100%;
		font: inherit;
		padding: 0.6rem 0.7rem;
		border: 1px solid var(--line-2);
		border-radius: var(--radius-sm);
		background: var(--card);
		color: var(--ink);
	}
	.kw {
		font-size: 1.05rem;
		font-weight: 500;
	}
	.suggestions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		margin-top: 0.5rem;
	}
	.suggestion {
		font: inherit;
		font-size: 0.74rem;
		padding: 0.2rem 0.6rem;
		border-radius: 999px;
		border: 1px solid var(--line-2);
		background: none;
		color: var(--ink-3);
		cursor: pointer;
		transition: color 0.15s, border-color 0.15s;
	}
	.suggestion:hover {
		color: var(--accent);
		border-color: var(--accent);
	}
	.range {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.dash {
		color: var(--ink-3);
	}
	.opts {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.seg {
		display: flex;
		gap: 0;
		border: 1px solid var(--line-2);
		border-radius: var(--radius-sm);
		overflow: hidden;
		margin-bottom: 0.4rem;
	}
	.seg button {
		flex: 1;
		font: inherit;
		font-size: 0.82rem;
		padding: 0.5rem;
		border: none;
		background: var(--card);
		color: var(--ink-2);
		cursor: pointer;
	}
	.seg button.on {
		background: var(--ink);
		color: var(--paper);
	}
</style>
