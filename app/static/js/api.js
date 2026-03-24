// ============================================
// OBSIDIAN API Client
// ============================================

const API = {
    base: '/api',

    async request(path, options = {}) {
        const url = this.base + path;
        const config = {
            headers: { 'Content-Type': 'application/json' },
            ...options,
        };
        try {
            const res = await fetch(url, config);
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || 'Request failed');
            }
            return await res.json();
        } catch (e) {
            console.error(`API Error [${path}]:`, e);
            throw e;
        }
    },

    // Notes
    getNotes() {
        return this.request('/notes');
    },

    getNote(id) {
        return this.request(`/notes/${encodeURIComponent(id)}`);
    },

    createNote(title, content = '', tags = []) {
        return this.request('/notes', {
            method: 'POST',
            body: JSON.stringify({ title, content, tags }),
        });
    },

    updateNote(id, data) {
        return this.request(`/notes/${encodeURIComponent(id)}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    },

    deleteNote(id) {
        return this.request(`/notes/${encodeURIComponent(id)}`, {
            method: 'DELETE',
        });
    },

    // Search
    search(query) {
        return this.request(`/search?q=${encodeURIComponent(query)}`);
    },

    // Graph
    getGraph() {
        return this.request('/graph');
    },

    getEgoGraph(id, depth = 1) {
        return this.request(`/graph/${encodeURIComponent(id)}?depth=${depth}`);
    },

    // Tags
    getTags() {
        return this.request('/tags');
    },

    getNotesByTag(tag) {
        return this.request(`/tags/${encodeURIComponent(tag)}/notes`);
    },

    // Context Builder
    buildContext(options) {
        return this.request('/context/build', {
            method: 'POST',
            body: JSON.stringify(options),
        });
    },

    // Vault
    scanVault() {
        return this.request('/vault/scan', { method: 'POST' });
    },
};
