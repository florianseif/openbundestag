<script lang="ts">
	import { i18n } from '$lib/i18n.svelte';

	const de = {
		title: 'Über das Projekt',
		subtitle: 'OpenBundestag macht 76 Jahre parlamentarische Sprache durchsuchbar.',
		what_title: 'Was ist OpenBundestag?',
		what: 'OpenBundestag ist ein unabhängiges Open-Source-Projekt, das alle Plenarprotokolle des Deutschen Bundestags von 1949 bis heute aufbereitet und in einer Datenbank zusammenführt. Rund 760.000 Redebeiträge aus 21 Wahlperioden können nach Stichwörtern, Parteien, Zeitraum und Rednerin durchsucht werden — kostenlos und ohne Anmeldung.',
		data_title: 'Datenquellen',
		data: 'Die Redetexte stammen aus den offiziellen Plenarprotokollen des Deutschen Bundestags, veröffentlicht über das Open-Data-Portal des Bundestags. Als amtliche Werke (§ 5 Abs. 1 UrhG) sind sie urheberrechtsfrei. Ministerdaten (Kabinettsmitglieder und Amtszeiten) werden von Wikipedia bezogen (CC BY-SA 4.0).',
		pipeline_title: 'Wie funktioniert es?',
		pipeline: 'Eine Python-Pipeline lädt die XML-Quelldaten herunter, parst Redner und Redebeiträge, normalisiert Parteizugehörigkeiten und schreibt alles in eine einzige DuckDB-Datei (~4 GB). Die Webanwendung liest diese Datei live — kein Backend-Server, keine Datenbank-Infrastruktur. Das vollständige Dataset steht auf HuggingFace zum freien Download bereit.',
		stack_title: 'Technik',
		stack_items: [
			['Pipeline', 'Python · DuckDB · Playwright'],
			['API', 'FastAPI · DuckDB · HuggingFace Spaces'],
			['Web', 'SvelteKit 5 · d3 · Cloudflare Pages'],
			['Daten-Hosting', 'HuggingFace Dataset (öffentlich)'],
		] as [string, string][],
		inspiration: 'OpenBundestag ist eine unabhängige Neuimplementierung, inspiriert von Open Discourse (opendiscourse.de).',
		cta: 'Daten erkunden',
		github: 'Quellcode auf GitHub',
		dataset: 'Dataset auf HuggingFace',
	};

	const en = {
		title: 'About',
		subtitle: 'OpenBundestag makes 76 years of parliamentary language searchable.',
		what_title: 'What is OpenBundestag?',
		what: 'OpenBundestag is an independent open-source project that processes all plenary protocols of the German Bundestag from 1949 to the present and consolidates them into a single database. Around 760,000 speeches across 21 electoral terms can be searched by keyword, party, date range, and speaker — for free, no sign-up required.',
		data_title: 'Data sources',
		data: 'Speech texts come from the official plenary protocols of the German Bundestag, published via the Bundestag Open Data portal. As official government documents (§ 5 (1) UrhG) they are in the public domain. Minister data (cabinet members and tenures) is sourced from Wikipedia (CC BY-SA 4.0).',
		pipeline_title: 'How does it work?',
		pipeline: 'A Python pipeline downloads the raw XML source files, parses speakers and speech segments, normalises party affiliations, and writes everything into a single DuckDB file (~4 GB). The web application reads this file directly — no backend server, no database infrastructure required. The complete dataset is freely available for download on HuggingFace.',
		stack_title: 'Technology',
		stack_items: [
			['Pipeline', 'Python · DuckDB · Playwright'],
			['API', 'FastAPI · DuckDB · HuggingFace Spaces'],
			['Web', 'SvelteKit 5 · d3 · Cloudflare Pages'],
			['Data hosting', 'HuggingFace Dataset (public)'],
		] as [string, string][],
		inspiration: 'OpenBundestag is an independent reimplementation inspired by Open Discourse (opendiscourse.de).',
		cta: 'Explore the data',
		github: 'Source code on GitHub',
		dataset: 'Dataset on HuggingFace',
	};

	const c = $derived(i18n.lang === 'de' ? de : en);
</script>

<svelte:head><title>{c.title} · OpenBundestag</title></svelte:head>

<div class="about wrap">
	<header class="about-head">
		<span class="eyebrow">OpenBundestag</span>
		<h1>{c.title}</h1>
		<p class="subtitle">{c.subtitle}</p>
	</header>

	<div class="body">
		<section class="section">
			<h2>{c.what_title}</h2>
			<p>{c.what}</p>
		</section>

		<section class="section">
			<h2>{c.data_title}</h2>
			<p>{c.data}</p>
		</section>

		<section class="section">
			<h2>{c.pipeline_title}</h2>
			<p>{c.pipeline}</p>
		</section>

		<section class="section">
			<h2>{c.stack_title}</h2>
			<table class="stack-table">
				<tbody>
					{#each c.stack_items as [label, value]}
						<tr>
							<td class="stack-label">{label}</td>
							<td class="stack-value">{value}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</section>

		<section class="section inspiration">
			<p>{c.inspiration}</p>
		</section>

		<div class="cta-row">
			<a class="btn" href="/explore">{c.cta} →</a>
			<a class="btn--ghost btn" href="https://github.com/florianseif/openbundestag" target="_blank" rel="noopener noreferrer">{c.github} ↗</a>
			<a class="btn--ghost btn" href="https://huggingface.co/datasets/MissionJupiter/openbundestag-db" target="_blank" rel="noopener noreferrer">{c.dataset} ↗</a>
		</div>
	</div>
</div>

<style>
	.about {
		padding-top: 4rem;
		padding-bottom: 6rem;
		max-width: 780px;
	}
	.about-head {
		margin-bottom: 3.5rem;
	}
	.about-head h1 {
		font-size: clamp(2.4rem, 5vw, 3.6rem);
		margin: 0.3rem 0 0.8rem;
	}
	.subtitle {
		font-size: 1.15rem;
		color: var(--ink-2);
		margin: 0;
		line-height: 1.5;
	}
	.body {
		display: flex;
		flex-direction: column;
		gap: 2.8rem;
	}
	.section h2 {
		font-size: 1.1rem;
		font-family: var(--display);
		margin: 0 0 0.75rem;
		color: var(--ink);
	}
	.section p {
		color: var(--ink-2);
		line-height: 1.75;
		margin: 0;
		font-size: 0.97rem;
	}
	.stack-table {
		border-collapse: collapse;
		width: 100%;
	}
	.stack-table tr {
		border-bottom: 1px solid var(--line);
	}
	.stack-table tr:last-child {
		border-bottom: none;
	}
	.stack-label {
		padding: 0.6rem 1.2rem 0.6rem 0;
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--ink-3);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		white-space: nowrap;
		width: 140px;
	}
	.stack-value {
		padding: 0.6rem 0;
		font-size: 0.9rem;
		color: var(--ink-2);
	}
	.inspiration {
		border-left: 3px solid var(--accent);
		padding-left: 1.2rem;
	}
	.inspiration p {
		font-style: italic;
	}
	.cta-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.85rem;
		padding-top: 1rem;
	}
</style>
