<script lang="ts">
	interface Stat {
		value: string | number;
		label: string;
	}

	let {
		title,
		subtitle,
		stats = []
	}: { title: string; subtitle: string; stats?: Stat[] } = $props();
</script>

<header class="page-hero">
	<div class="hero-glow" aria-hidden="true"></div>
	<div class="hero-top">
		<div class="hero-text">
			<h1 class="grad-text">{title}</h1>
			<p class="hero-sub">{subtitle}</p>
		</div>
	</div>

	{#if stats.length}
		<div class="hero-stats">
			{#each stats as s (s.label + s.value)}
				<span class="stat-chip">
					<span class="stat-val">{s.value}</span>
					{#if s.label}<span class="stat-lbl">{s.label}</span>{/if}
				</span>
			{/each}
		</div>
	{/if}
</header>

<style>
	.page-hero {
		position: relative;
		margin-bottom: 1.4rem;
	}
	/* soft aurora bloom behind the title */
	.hero-glow {
		position: absolute;
		inset: -40% -10% auto -10%;
		height: 220px;
		background: radial-gradient(
			60% 100% at 20% 0%,
			rgba(107, 145, 255, 0.16),
			rgba(169, 139, 255, 0.08) 45%,
			transparent 72%
		);
		filter: blur(8px);
		pointer-events: none;
		z-index: 0;
	}
	.hero-top {
		position: relative;
		z-index: 1;
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
	}
	.hero-text {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	h1 {
		font-family: var(--display);
		font-size: clamp(2.2rem, 5vw, 3.4rem);
		line-height: 1;
		margin: 0;
		letter-spacing: -0.01em;
	}
	.hero-sub {
		color: var(--ink-2);
		font-size: 1rem;
		margin: 0;
		max-width: 52ch;
	}
	.hero-stats {
		position: relative;
		z-index: 1;
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 1rem;
	}
	.stat-chip {
		display: inline-flex;
		align-items: baseline;
		gap: 0.4rem;
		padding: 0.34rem 0.7rem;
		border-radius: 999px;
		background: var(--surface-2);
		border: 1px solid var(--line);
	}
	.stat-val {
		font-family: var(--display);
		font-weight: 600;
		font-size: 0.95rem;
		color: var(--ink);
		font-variant-numeric: tabular-nums;
	}
	.stat-lbl {
		font-size: 0.74rem;
		font-weight: 500;
		letter-spacing: 0.04em;
		color: var(--ink-3);
		text-transform: uppercase;
	}
</style>
