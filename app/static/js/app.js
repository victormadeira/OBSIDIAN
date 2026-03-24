// ============================================
// OBSIDIAN Main Application
// ============================================

const App = {
    currentView: 'welcome',

    async init() {
        Editor.init();
        await this.loadNoteList();

        // Route handling
        window.addEventListener('hashchange', () => this.route());
        this.route();

        // New note button
        document.getElementById('btn-new-note').addEventListener('click', () => this.showNewNoteModal());

        // Modal events
        document.getElementById('modal-close').addEventListener('click', () => this.hideModal());
        document.getElementById('modal-cancel').addEventListener('click', () => this.hideModal());
        document.getElementById('modal-create').addEventListener('click', () => this.createNote());
        document.getElementById('new-note-title').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.createNote();
        });

        // Sidebar search
        document.getElementById('sidebar-search').addEventListener('input', (e) => {
            const q = e.target.value.trim();
            if (q.length >= 2) {
                this.filterNoteList(q);
            } else {
                this.loadNoteList();
            }
        });

        document.getElementById('sidebar-search').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const q = e.target.value.trim();
                if (q) Search.perform(q);
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl+N: New note
            if (e.ctrlKey && e.key === 'n') {
                e.preventDefault();
                this.showNewNoteModal();
            }
            // Ctrl+P: Command palette
            if (e.ctrlKey && e.key === 'p') {
                e.preventDefault();
                this.openCommandPalette();
            }
            // Ctrl+S: Save
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                if (Editor.currentNoteId) Editor.save();
            }
            // Ctrl+G: Graph
            if (e.ctrlKey && e.key === 'g') {
                e.preventDefault();
                window.location.hash = '/graph';
            }
            // Escape: Close modals
            if (e.key === 'Escape') {
                this.hideModal();
                this.hideCommandPalette();
            }
        });

        // Command palette background click
        document.getElementById('command-palette').addEventListener('click', (e) => {
            if (e.target.id === 'command-palette') this.hideCommandPalette();
        });

        document.getElementById('modal-overlay').addEventListener('click', (e) => {
            if (e.target.id === 'modal-overlay') this.hideModal();
        });

        // Update stats
        this.updateStats();
    },

    // ---- Routing ----

    route() {
        const hash = window.location.hash.slice(1) || '/';
        const parts = hash.split('/').filter(Boolean);

        // Update nav active state
        document.querySelectorAll('.nav-item').forEach(el => {
            const view = el.dataset.view;
            const isActive = (hash === '/' && view === 'notes') ||
                             (parts[0] === view) ||
                             (parts[0] === 'note' && view === 'notes');
            el.classList.toggle('active', isActive);
        });

        if (parts[0] === 'note' && parts[1]) {
            this.showView('editor');
            Editor.open(parts[1]);
        } else if (parts[0] === 'graph') {
            this.showView('graph');
            setTimeout(() => Graph.render(), 50);
        } else if (parts[0] === 'context') {
            this.showView('context');
            ContextBuilder.init();
        } else if (parts[0] === 'tags') {
            this.showView('tags');
            this.loadTags();
        } else if (parts[0] === 'search') {
            this.showView('search');
        } else {
            this.showView('welcome');
        }
    },

    showView(viewName) {
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        const view = document.getElementById(`view-${viewName}`);
        if (view) view.classList.add('active');
        this.currentView = viewName;
    },

    // ---- Note List ----

    async loadNoteList() {
        try {
            const notes = await API.getNotes();
            const container = document.getElementById('note-list');

            if (notes.length === 0) {
                container.innerHTML = `
                    <div class="empty-state" style="padding:20px">
                        <p style="font-size:12px">Nenhuma nota ainda.<br>Crie sua primeira nota!</p>
                    </div>
                `;
            } else {
                container.innerHTML = notes.map(n => `
                    <div class="note-list-item ${Editor.currentNoteId === n.id ? 'active' : ''}"
                         data-id="${n.id}"
                         onclick="window.location.hash='/note/${n.id}'">
                        <div class="note-item-title">${this.escapeHtml(n.title)}</div>
                        <div class="note-item-meta">
                            ${n.tags.slice(0, 3).map(t => `<span class="note-item-tag">#${t}</span>`).join('')}
                            <span>${this.formatDate(n.updated_at)}</span>
                        </div>
                    </div>
                `).join('');
            }

            this.updateStats(notes.length);
        } catch (e) {
            console.error('Failed to load notes:', e);
        }
    },

    async filterNoteList(query) {
        try {
            const results = await API.search(query);
            const container = document.getElementById('note-list');
            container.innerHTML = results.map(r => `
                <div class="note-list-item" data-id="${r.id}"
                     onclick="window.location.hash='/note/${r.id}'">
                    <div class="note-item-title">${this.escapeHtml(r.title)}</div>
                </div>
            `).join('');
        } catch (e) {
            // Ignore search errors during typing
        }
    },

    // ---- Tags ----

    async loadTags() {
        try {
            const tags = await API.getTags();
            const container = document.getElementById('tags-container');

            if (tags.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>Nenhuma tag encontrada. Use #tag nas suas notas.</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = tags.map(t => `
                <div class="tag-card" onclick="App.showNotesByTag('${t.tag}')">
                    <span class="tag-name">#${t.tag}</span>
                    <span class="tag-count">${t.count} nota${t.count > 1 ? 's' : ''}</span>
                </div>
            `).join('');
        } catch (e) {
            console.error('Failed to load tags:', e);
        }
    },

    async showNotesByTag(tag) {
        Search.perform('#' + tag);
    },

    // ---- New Note Modal ----

    showNewNoteModal() {
        document.getElementById('modal-overlay').classList.remove('hidden');
        const titleInput = document.getElementById('new-note-title');
        titleInput.value = '';
        document.getElementById('new-note-tags').value = '';
        setTimeout(() => titleInput.focus(), 100);
    },

    hideModal() {
        document.getElementById('modal-overlay').classList.add('hidden');
    },

    async createNote() {
        const title = document.getElementById('new-note-title').value.trim();
        if (!title) {
            this.toast('Digite um titulo para a nota', 'error');
            return;
        }

        const tagsStr = document.getElementById('new-note-tags').value.trim();
        const tags = tagsStr ? tagsStr.split(',').map(t => t.trim().replace(/^#/, '')) : [];

        try {
            const note = await API.createNote(title, '', tags);
            this.hideModal();
            this.toast('Nota criada!', 'success');
            await this.loadNoteList();
            window.location.hash = `/note/${note.id}`;
        } catch (e) {
            this.toast('Erro ao criar nota: ' + e.message, 'error');
        }
    },

    // ---- Command Palette ----

    async openCommandPalette() {
        const notes = await API.getNotes();
        this.showCommandPalette(notes);
    },

    showCommandPalette(notes, onSelect = null) {
        const palette = document.getElementById('command-palette');
        const input = document.getElementById('command-input');
        const results = document.getElementById('command-results');

        palette.classList.remove('hidden');
        input.value = '';
        input.focus();

        const renderResults = (filtered) => {
            results.innerHTML = filtered.slice(0, 10).map(n => `
                <div class="command-result-item" data-id="${n.id}">
                    <span class="result-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14,2 14,8 20,8"/>
                        </svg>
                    </span>
                    <span class="result-text">${this.escapeHtml(n.title)}</span>
                    <span class="result-path">${n.tags.map(t => '#' + t).join(' ')}</span>
                </div>
            `).join('');

            // Click handlers
            results.querySelectorAll('.command-result-item').forEach(el => {
                el.addEventListener('click', () => {
                    const note = notes.find(n => n.id === el.dataset.id);
                    if (onSelect) {
                        onSelect(note);
                    } else {
                        window.location.hash = `/note/${el.dataset.id}`;
                    }
                    this.hideCommandPalette();
                });
            });
        };

        renderResults(notes);

        input.oninput = () => {
            const q = input.value.toLowerCase();
            const filtered = notes.filter(n =>
                n.title.toLowerCase().includes(q) ||
                n.tags.some(t => t.includes(q))
            );
            renderResults(filtered);
        };

        input.onkeydown = (e) => {
            if (e.key === 'Enter') {
                const first = results.querySelector('.command-result-item');
                if (first) first.click();
            }
            if (e.key === 'Escape') {
                this.hideCommandPalette();
            }
        };
    },

    hideCommandPalette() {
        document.getElementById('command-palette').classList.add('hidden');
    },

    // ---- Utilities ----

    toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    },

    updateStats(count) {
        const stats = document.getElementById('sidebar-stats');
        if (count !== undefined) {
            stats.textContent = `${count} nota${count !== 1 ? 's' : ''}`;
        }
    },

    formatDate(dateStr) {
        if (!dateStr) return '';
        try {
            const d = new Date(dateStr);
            return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
        } catch {
            return dateStr;
        }
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
};

// ---- Bootstrap ----
document.addEventListener('DOMContentLoaded', () => App.init());
