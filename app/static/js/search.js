// ============================================
// OBSIDIAN Search Module
// ============================================

const Search = {
    async perform(query) {
        if (!query || query.trim().length === 0) return;

        try {
            const results = await API.search(query);
            this.renderResults(query, results);
            App.showView('search');
        } catch (e) {
            App.toast('Erro na busca', 'error');
        }
    },

    renderResults(query, results) {
        const display = document.getElementById('search-query-display');
        const container = document.getElementById('search-results');

        display.textContent = `"${query}" — ${results.length} resultado(s)`;

        if (results.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                    </svg>
                    <p>Nenhum resultado encontrado para "${query}"</p>
                </div>
            `;
            return;
        }

        container.innerHTML = results.map(r => `
            <div class="search-result-item" onclick="window.location.hash='/note/${r.id}'">
                <div class="result-title">${this.escapeHtml(r.title)}</div>
                <div class="result-snippet">${r.snippet}</div>
            </div>
        `).join('');
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
};
