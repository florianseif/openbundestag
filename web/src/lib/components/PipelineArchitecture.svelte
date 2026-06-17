<script lang="ts">
	interface Node {
		id: string;
		label: string;
		icon: string;
		x: number;
		y: number;
		width: number;
		height: number;
		color: string;
		description: string;
	}

	interface Edge {
		from: string;
		to: string;
		label: string;
	}

	let hoveredNode = $state<string | null>(null);
	let hoveredEdge = $state<string | null>(null);

	const nodes: Node[] = [
		{
			id: 'bundestag',
			label: 'Bundestag<br/>Open Data',
			icon: '🌐',
			x: 50,
			y: 100,
			width: 140,
			height: 80,
			color: '#e1f5ff',
			description: 'XML files & ZIP archives (terms 1–21)'
		},
		{
			id: 'extract',
			label: 'EXTRACT',
			icon: '📥',
			x: 250,
			y: 50,
			width: 140,
			height: 80,
			color: '#fff3e0',
			description: 'src/extract.py + Playwright downloader'
		},
		{
			id: 'cache',
			label: 'Cache',
			icon: '📂',
			x: 250,
			y: 180,
			width: 140,
			height: 60,
			color: '#f5f5f5',
			description: 'data/term_XX/ (raw XML)'
		},
		{
			id: 'transform',
			label: 'TRANSFORM',
			icon: '🔄',
			x: 450,
			y: 100,
			width: 140,
			height: 80,
			color: '#fff3e0',
			description: 'Modern & legacy XML parsing'
		},
		{
			id: 'load',
			label: 'LOAD',
			icon: '📝',
			x: 650,
			y: 100,
			width: 140,
			height: 80,
			color: '#fff3e0',
			description: 'Write to DuckDB'
		},
		{
			id: 'duckdb',
			label: 'DuckDB',
			icon: '🗄️',
			x: 850,
			y: 100,
			width: 140,
			height: 80,
			color: '#c8e6c9',
			description: 'openbundestag-data.db'
		},
		{
			id: 'wikipedia',
			label: 'Wikipedia',
			icon: '🌍',
			x: 650,
			y: 280,
			width: 140,
			height: 80,
			color: '#e1f5ff',
			description: 'Minister biographical data'
		},
		{
			id: 'ministers',
			label: 'MINISTERS',
			icon: '👨‍⚖️',
			x: 850,
			y: 280,
			width: 140,
			height: 80,
			color: '#fff3e0',
			description: 'src/scrape_ministers.py'
		},
		{
			id: 'finalize',
			label: 'FINALIZE',
			icon: '✨',
			x: 1050,
			y: 100,
			width: 140,
			height: 80,
			color: '#fff3e0',
			description: 'Materialize derived columns'
		},
		{
			id: 'ready',
			label: 'READY',
			icon: '✅',
			x: 1250,
			y: 100,
			width: 140,
			height: 80,
			color: '#c8e6c9',
			description: 'speeches + speakers + zwischenrufe'
		},
		{
			id: 'app',
			label: 'App & Website',
			icon: '📊',
			x: 1250,
			y: 280,
			width: 140,
			height: 80,
			color: '#ffe0b2',
			description: 'Streamlit + SvelteKit'
		}
	];

	const edges: Edge[] = [
		{ from: 'bundestag', to: 'extract', label: 'download' },
		{ from: 'extract', to: 'cache', label: 'save' },
		{ from: 'cache', to: 'transform', label: 'parse XML' },
		{ from: 'transform', to: 'load', label: 'speakers_df\nspeaches_df' },
		{ from: 'load', to: 'duckdb', label: 'create schema' },
		{ from: 'wikipedia', to: 'ministers', label: 'scrape' },
		{ from: 'ministers', to: 'duckdb', label: 'load tables' },
		{ from: 'duckdb', to: 'finalize', label: 'read faction' },
		{ from: 'finalize', to: 'ready', label: 'faction_normalized\nsearch_text' },
		{ from: 'ready', to: 'app', label: 'full-text search' }
	];

	const getEdgeId = (edge: Edge) => `${edge.from}-${edge.to}`;
</script>

<div class="architecture-container">
	<svg viewBox="0 0 1450 420" class="architecture-svg">
		<!-- Grid background -->
		<defs>
			<pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
				<path d="M 50 0 L 0 0 0 50" fill="none" stroke="var(--line)" stroke-width="0.5" />
			</pattern>
			<marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
				<polygon points="0 0, 10 3, 0 6" fill="var(--accent)" />
			</marker>
		</defs>

		<rect width="1450" height="420" fill="var(--bg)" />
		<rect width="1450" height="420" fill="url(#grid)" />

		<!-- Edges (paths first, so they appear behind nodes) -->
		<g class="edges">
			{#each edges as edge}
				{@const edgeId = getEdgeId(edge)}
				{@const fromNode = nodes.find((n) => n.id === edge.from)}
				{@const toNode = nodes.find((n) => n.id === edge.to)}
				{#if fromNode && toNode}
					{@const x1 = fromNode.x + fromNode.width / 2}
					{@const y1 = fromNode.y + fromNode.height / 2}
					{@const x2 = toNode.x + toNode.width / 2}
					{@const y2 = toNode.y + toNode.height / 2}
					{@const isHovered = hoveredEdge === edgeId}
					<g
						class="edge-group"
						class:hovered={isHovered}
						role="presentation"
						onmouseenter={() => (hoveredEdge = edgeId)}
						onmouseleave={() => (hoveredEdge = null)}
					>
						<line
							x1={x1}
							y1={y1}
							x2={x2}
							y2={y2}
							stroke="var(--line-2)"
							stroke-width="2"
							marker-end="url(#arrowhead)"
							class="edge-line"
						/>
						<text
							x={(x1 + x2) / 2}
							y={(y1 + y2) / 2 - 8}
							text-anchor="middle"
							font-size="11"
							fill="var(--ink-2)"
							class="edge-label"
						>
							{edge.label}
						</text>
					</g>
				{/if}
			{/each}
		</g>

		<!-- Nodes -->
		<g class="nodes">
			{#each nodes as node}
				{@const isHovered = hoveredNode === node.id}
				<g
					class="node-group"
					class:hovered={isHovered}
					onmouseenter={() => (hoveredNode = node.id)}
					onmouseleave={() => (hoveredNode = null)}
					onfocus={() => (hoveredNode = node.id)}
					onblur={() => (hoveredNode = null)}
					role="button"
					tabindex="0"
				>
					<!-- Node background -->
					<rect
						x={node.x}
						y={node.y}
						width={node.width}
						height={node.height}
						rx="8"
						fill={node.color}
						stroke={isHovered ? 'var(--accent)' : 'var(--line-2)'}
						stroke-width={isHovered ? '2' : '1'}
						class="node-rect"
					/>

					<!-- Icon -->
					<text
						x={node.x + node.width / 2}
						y={node.y + 24}
						text-anchor="middle"
						font-size="24"
						class="node-icon"
					>
						{node.icon}
					</text>

					<!-- Label -->
					<text
						x={node.x + node.width / 2}
						y={node.y + node.height - 14}
						text-anchor="middle"
						font-size="12"
						font-weight="600"
						fill="#000"
						font-family="var(--display)"
					>
						{@html node.label}
					</text>

					<!-- Tooltip -->
					{#if isHovered}
						<g class="tooltip">
							<rect
								x={node.x - 10}
								y={node.y - 55}
								width="180"
								rx="6"
								height="50"
								fill="var(--surface)"
								stroke="var(--accent)"
								stroke-width="1"
							/>
							<text
								x={node.x + 80}
								y={node.y - 20}
								font-size="11"
								fill="var(--ink)"
								font-family="var(--sans)"
								text-anchor="middle"
							>
								{node.description}
							</text>
						</g>
					{/if}
				</g>
			{/each}
		</g>
	</svg>

	<div class="legend">
		<div class="legend-item">
			<div class="color-box" style="background: #e1f5ff;"></div>
			<span>External Data Source</span>
		</div>
		<div class="legend-item">
			<div class="color-box" style="background: #fff3e0;"></div>
			<span>Processing Step</span>
		</div>
		<div class="legend-item">
			<div class="color-box" style="background: #c8e6c9;"></div>
			<span>Database State</span>
		</div>
		<div class="legend-item">
			<div class="color-box" style="background: #f5f5f5;"></div>
			<span>Intermediate Cache</span>
		</div>
	</div>
</div>

<style>
	.architecture-container {
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.architecture-svg {
		width: 100%;
		max-width: 1400px;
		height: auto;
		background: var(--bg);
		border-radius: var(--radius);
		border: 1px solid var(--line);
		overflow: visible;
	}

	:global(.node-group) {
		cursor: pointer;
		transition: all 0.2s cubic-bezier(0.22, 1, 0.36, 1);
	}

	:global(.node-group.hovered .node-rect) {
		filter: drop-shadow(0 0 20px rgba(107, 145, 255, 0.4));
	}

	:global(.edge-group) {
		transition: all 0.2s cubic-bezier(0.22, 1, 0.36, 1);
		opacity: 0.6;
	}

	:global(.edge-group.hovered) {
		opacity: 1;
	}

	:global(.edge-group.hovered .edge-line) {
		stroke: var(--accent);
		stroke-width: 3;
	}

	:global(.edge-group.hovered .edge-label) {
		fill: var(--accent);
		font-weight: 600;
	}

	:global(.edge-line) {
		transition: all 0.2s cubic-bezier(0.22, 1, 0.36, 1);
	}

	:global(.edge-label) {
		transition: all 0.2s cubic-bezier(0.22, 1, 0.36, 1);
		pointer-events: none;
	}

	.legend {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 1rem;
		padding: 1rem 0;
	}

	.legend-item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		font-size: 0.875rem;
		color: var(--ink-2);
	}

	.color-box {
		width: 24px;
		height: 24px;
		border-radius: 4px;
		border: 1px solid var(--line-2);
		flex-shrink: 0;
	}
</style>
