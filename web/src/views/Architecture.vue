<script setup lang="ts">
import { onMounted } from 'vue';
import PipelineArchitecture from '$lib/components/PipelineArchitecture.vue';

onMounted(() => {
	document.title = 'Architecture — OpenBundestag';
});
</script>

<template>
	<div class="hero">
		<h1>Pipeline Architecture</h1>
		<p>How raw Bundestag XML becomes a queryable database in six phases</p>
	</div>

	<div class="diagram-section">
		<PipelineArchitecture />
	</div>

	<section class="phases">
		<h2>The Phases</h2>

		<div class="phase-grid">
			<div class="phase-card">
				<div class="phase-icon">📥</div>
				<h3>Extract</h3>
				<p><strong>Module:</strong> <code>src/extract.py</code></p>
				<p>
					Downloads raw XML and ZIP files from the official Bundestag open-data endpoints. Uses
					Playwright to handle bot protection. Idempotent — already-downloaded files are skipped.
				</p>
			</div>

			<div class="phase-card">
				<div class="phase-icon">🔄</div>
				<h3>Transform</h3>
				<p><strong>Module:</strong> <code>src/transform.py</code></p>
				<p>
					Parses XML into two DataFrames: <code>speakers</code> and <code>speeches</code>.
					Auto-detects modern (terms 19–21, structured XML) vs legacy (terms 1–18, text-heavy XML)
					and applies the correct parser.
				</p>
			</div>

			<div class="phase-card">
				<div class="phase-icon">📝</div>
				<h3>Load</h3>
				<p><strong>Module:</strong> <code>src/load.py</code></p>
				<p>
					Writes the speakers and speeches DataFrames into DuckDB. Creates the database schema on
					first run, then appends data by electoral term.
				</p>
			</div>

			<div class="phase-card">
				<div class="phase-icon">👨‍⚖️</div>
				<h3>Ministers</h3>
				<p><strong>Module:</strong> <code>src/scrape_ministers.py</code></p>
				<p>
					Scrapes German federal minister biographical data from Wikipedia (CC BY-SA). Runs in
					parallel with Load. Required by Finalize for the faction fallback.
				</p>
			</div>

			<div class="phase-card">
				<div class="phase-icon">✨</div>
				<h3>Finalize</h3>
				<p><strong>Module:</strong> <code>src/load.py</code></p>
				<p>
					Materializes two derived columns the app queries at runtime: <code>faction_normalized</code>
					(resolved party) and <code>search_text</code> (lowercased speech content). ~5× faster than
					computing on-the-fly. Must run after Load and Ministers.
				</p>
			</div>

			<div class="phase-card">
				<div class="phase-icon">💬</div>
				<h3>Zwischenrufe</h3>
				<p><strong>Module:</strong> <code>src/zwischenrufe.py</code></p>
				<p>
					Extracts parliamentary interjections (heckling, applause, remarks) into a dedicated table.
					Reads XML for modern terms, parses parenthetical remarks for legacy terms. Must run after
					Finalize.
				</p>
			</div>
		</div>
	</section>

	<section class="details">
		<h2>Key Details</h2>

		<div class="detail-box">
			<h3>Input & Output</h3>
			<ul>
				<li><strong>Input:</strong> Bundestag Open Data XML/ZIP files + Wikipedia minister data</li>
				<li>
					<strong>Output:</strong> <code>openbundestag-data.db</code> (~2 GB, all 21 terms, ready for
					querying)
				</li>
				<li><strong>Format:</strong> DuckDB — no Docker, no PostgreSQL, no setup required</li>
			</ul>
		</div>

		<div class="detail-box">
			<h3>Dependencies</h3>
			<ul>
				<li><strong>Extract → Transform:</strong> Raw files must be downloaded first</li>
				<li><strong>Transform + Load → Finalize:</strong> Speeches table must exist</li>
				<li><strong>Ministers → Finalize:</strong> Ministers table needed for faction fallback</li>
				<li><strong>Finalize → Zwischenrufe:</strong> faction_normalized column required</li>
			</ul>
		</div>

		<div class="detail-box">
			<h3>Idempotence</h3>
			<p>
				Extract, Finalize, and Zwischenrufe are idempotent — running them multiple times is safe.
				Transform and Load can be re-run per term to refresh data.
			</p>
		</div>
	</section>
</template>

<style scoped>
.hero {
	text-align: center;
	margin-bottom: 4rem;
}

.hero h1 {
	font-size: 2.5rem;
	margin-bottom: 0.5rem;
	background: var(--grad);
	-webkit-background-clip: text;
	-webkit-text-fill-color: transparent;
	background-clip: text;
}

.hero p {
	font-size: 1.125rem;
	color: var(--ink-2);
}

.diagram-section {
	margin-bottom: 4rem;
	padding: 1.5rem;
	background: var(--surface);
	border-radius: var(--radius);
	border: 1px solid var(--line);
}

.phases {
	margin-bottom: 3rem;
}

.phases h2 {
	margin-bottom: 2rem;
}

.phase-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
	gap: 1.5rem;
	margin-bottom: 2rem;
}

.phase-card {
	padding: 1.5rem;
	background: var(--surface);
	border: 1px solid var(--line);
	border-radius: var(--radius-sm);
	transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.phase-card:hover {
	border-color: var(--accent);
	box-shadow: var(--shadow), 0 0 20px rgba(107, 145, 255, 0.15);
}

.phase-icon {
	font-size: 2.5rem;
	margin-bottom: 1rem;
}

.phase-card h3 {
	margin-top: 0;
	margin-bottom: 0.75rem;
	color: var(--ink);
}

.phase-card p {
	margin: 0.5rem 0;
	font-size: 0.95rem;
	line-height: 1.5;
	color: var(--ink-2);
}

.phase-card code {
	background: var(--bg);
	padding: 0.25rem 0.5rem;
	border-radius: 4px;
	font-family: 'Monaco', 'Courier New', monospace;
	font-size: 0.875rem;
	color: var(--accent);
}

.details {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
	gap: 1.5rem;
	margin-top: 2rem;
}

.details h2 {
	grid-column: 1 / -1;
	margin-bottom: 1rem;
}

.detail-box {
	padding: 1.5rem;
	background: var(--surface);
	border: 1px solid var(--line);
	border-radius: var(--radius-sm);
}

.detail-box h3 {
	margin-top: 0;
	margin-bottom: 1rem;
	color: var(--accent);
}

.detail-box ul {
	margin: 0;
	padding-left: 1.5rem;
}

.detail-box li {
	margin-bottom: 0.75rem;
	color: var(--ink-2);
	line-height: 1.6;
}

.detail-box p {
	margin: 0;
	color: var(--ink-2);
	line-height: 1.6;
}
</style>
