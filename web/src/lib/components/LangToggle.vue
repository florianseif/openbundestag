<script setup lang="ts">
// REFERENCE PORT — mirrors LangToggle.svelte.
//   onclick={fn}          -> @click="fn"
//   class:on={cond}       -> :class="{ on: cond }"
//   <style> (auto-scoped) -> <style scoped>
import { i18n } from '$lib/i18n';
</script>

<template>
	<button class="lang" @click="i18n.toggle()" aria-label="Toggle language">
		<span :class="{ on: i18n.lang === 'de' }">DE</span>
		<span class="sep">/</span>
		<span :class="{ on: i18n.lang === 'en' }">EN</span>
	</button>
</template>

<style scoped>
.lang {
	font: inherit;
	font-size: 0.82rem;
	font-weight: 600;
	letter-spacing: 0.04em;
	background: none;
	border: 1px solid var(--line-2);
	border-radius: 999px;
	padding: 0.34rem 0.8rem;
	color: var(--ink-3);
	cursor: pointer;
}
.lang .on {
	color: var(--ink);
}
.sep {
	margin: 0 0.2rem;
	color: var(--line-2);
}
</style>
