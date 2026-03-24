// ============================================
// OBSIDIAN Graph Visualization
// ============================================

const Graph = {
    simulation: null,
    svg: null,
    g: null,
    zoom: null,

    async render() {
        try {
            const data = await API.getGraph();
            this.draw(data);
        } catch (e) {
            console.error('Graph error:', e);
        }
    },

    draw(data) {
        const container = document.getElementById('graph-container');
        const svgEl = document.getElementById('graph-svg');

        // Clear previous
        svgEl.innerHTML = '';
        if (this.simulation) this.simulation.stop();

        const width = container.clientWidth;
        const height = container.clientHeight;

        this.svg = d3.select('#graph-svg')
            .attr('viewBox', [0, 0, width, height]);

        this.g = this.svg.append('g');

        // Zoom
        this.zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });

        this.svg.call(this.zoom);

        if (data.nodes.length === 0) {
            this.g.append('text')
                .attr('x', width / 2)
                .attr('y', height / 2)
                .attr('text-anchor', 'middle')
                .attr('fill', '#6c7086')
                .attr('font-size', '16px')
                .text('Crie notas com [[links]] para ver o grafo');
            return;
        }

        // Color scale based on tags
        const tagColors = [
            '#89b4fa', '#cba6f7', '#a6e3a1', '#f9e2af',
            '#f38ba8', '#94e2d5', '#fab387', '#f5c2e7',
            '#74c7ec', '#b4befe',
        ];

        const allTags = [...new Set(data.nodes.flatMap(n => n.tags || []))];
        const tagColor = (tags) => {
            if (!tags || tags.length === 0) return '#6c7086';
            const idx = allTags.indexOf(tags[0]) % tagColors.length;
            return tagColors[idx >= 0 ? idx : 0];
        };

        // Force simulation
        this.simulation = d3.forceSimulation(data.nodes)
            .force('link', d3.forceLink(data.edges).id(d => d.id).distance(80))
            .force('charge', d3.forceManyBody().strength(-200))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(30));

        // Links
        const link = this.g.append('g')
            .selectAll('line')
            .data(data.edges)
            .join('line')
            .attr('class', 'graph-link');

        // Nodes
        const node = this.g.append('g')
            .selectAll('g')
            .data(data.nodes)
            .join('g')
            .attr('class', 'graph-node')
            .call(d3.drag()
                .on('start', (event, d) => {
                    if (!event.active) this.simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on('drag', (event, d) => {
                    d.fx = event.x;
                    d.fy = event.y;
                })
                .on('end', (event, d) => {
                    if (!event.active) this.simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                })
            );

        // Node circles
        node.append('circle')
            .attr('r', d => Math.max(6, Math.min(20, 6 + (d.link_count || 0) * 2)))
            .attr('fill', d => d.phantom ? '#45475a' : tagColor(d.tags))
            .attr('stroke', d => d.phantom ? '#45475a' : tagColor(d.tags))
            .attr('stroke-opacity', 0.3)
            .attr('fill-opacity', d => d.phantom ? 0.3 : 0.8);

        // Node labels
        node.append('text')
            .attr('dx', d => Math.max(6, Math.min(20, 6 + (d.link_count || 0) * 2)) + 6)
            .attr('dy', 4)
            .text(d => d.title)
            .attr('font-size', '11px')
            .attr('fill', d => d.phantom ? '#45475a' : '#a6adc8');

        // Click to navigate
        node.on('click', (event, d) => {
            if (!d.phantom) {
                window.location.hash = `/note/${d.id}`;
            }
        });

        // Hover glow
        node.on('mouseenter', function(event, d) {
            d3.select(this).select('circle')
                .transition().duration(150)
                .attr('fill-opacity', 1)
                .attr('stroke-width', 3);
        });

        node.on('mouseleave', function(event, d) {
            d3.select(this).select('circle')
                .transition().duration(150)
                .attr('fill-opacity', d.phantom ? 0.3 : 0.8)
                .attr('stroke-width', 2);
        });

        // Simulation tick
        this.simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });

        // Populate tag filter
        this.populateTagFilter(allTags);
    },

    populateTagFilter(tags) {
        const select = document.getElementById('graph-filter-tag');
        select.innerHTML = '<option value="">Todas as tags</option>';
        tags.forEach(t => {
            select.innerHTML += `<option value="${t}">#${t}</option>`;
        });
    },

    resetZoom() {
        if (this.svg && this.zoom) {
            this.svg.transition().duration(500).call(
                this.zoom.transform,
                d3.zoomIdentity
            );
        }
    },
};

// Graph reset button
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('btn-graph-reset');
    if (btn) btn.addEventListener('click', () => Graph.resetZoom());
});
