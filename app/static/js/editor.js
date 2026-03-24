// ============================================
// OBSIDIAN Editor Module
// ============================================

const Editor = {
    currentNoteId: null,
    isDirty: false,
    autoSaveTimer: null,
    previewVisible: true,

    els: {},

    init() {
        this.els = {
            title: document.getElementById('editor-title'),
            textarea: document.getElementById('editor-textarea'),
            preview: document.getElementById('preview-content'),
            previewPane: document.getElementById('preview-pane'),
            editorPane: document.getElementById('editor-pane'),
            tagsDisplay: document.getElementById('editor-tags-display'),
            backlinks: document.getElementById('editor-backlinks'),
            btnSave: document.getElementById('btn-save-note'),
            btnDelete: document.getElementById('btn-delete-note'),
            btnTogglePreview: document.getElementById('btn-toggle-preview'),
        };

        // Configure marked
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,
                gfm: true,
            });
        }

        this.els.textarea.addEventListener('input', () => {
            this.isDirty = true;
            this.renderPreview();
            this.scheduleAutoSave();
        });

        this.els.textarea.addEventListener('keydown', (e) => {
            // Tab support
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = e.target.selectionStart;
                const end = e.target.selectionEnd;
                e.target.value = e.target.value.substring(0, start) + '    ' + e.target.value.substring(end);
                e.target.selectionStart = e.target.selectionEnd = start + 4;
                this.isDirty = true;
                this.renderPreview();
            }

            // [[ autocomplete trigger
            if (e.key === '[') {
                const pos = e.target.selectionStart;
                const before = e.target.value.substring(Math.max(0, pos - 1), pos);
                if (before === '[') {
                    setTimeout(() => this.showLinkAutocomplete(), 50);
                }
            }
        });

        this.els.btnSave.addEventListener('click', () => this.save());
        this.els.btnDelete.addEventListener('click', () => this.deleteNote());
        this.els.btnTogglePreview.addEventListener('click', () => this.togglePreview());

        this.els.title.addEventListener('input', () => {
            this.isDirty = true;
        });
    },

    async open(noteId) {
        if (this.isDirty && this.currentNoteId) {
            await this.save();
        }

        try {
            const note = await API.getNote(noteId);
            this.currentNoteId = note.id;
            this.els.title.value = note.title;
            this.els.textarea.value = note.content;
            this.isDirty = false;

            // Tags
            this.els.tagsDisplay.innerHTML = note.tags
                .map(t => `<span class="tag-badge">#${t}</span>`)
                .join('');

            // Backlinks
            this.renderBacklinks(note.backlinks);

            // Preview
            this.renderPreview();

            // Update sidebar active
            document.querySelectorAll('.note-list-item').forEach(el => {
                el.classList.toggle('active', el.dataset.id === noteId);
            });

        } catch (e) {
            App.toast('Nota nao encontrada', 'error');
        }
    },

    renderPreview() {
        const content = this.els.textarea.value;
        // Process wikilinks before markdown
        const processed = this.processWikilinks(content);
        if (typeof marked !== 'undefined') {
            this.els.preview.innerHTML = marked.parse(processed);
        }

        // Make wikilinks clickable in preview
        this.els.preview.querySelectorAll('a.wikilink').forEach(a => {
            a.addEventListener('click', (e) => {
                e.preventDefault();
                const target = a.dataset.target;
                window.location.hash = `/note/${target}`;
            });
        });
    },

    processWikilinks(content) {
        return content.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (match, target, alias) => {
            const display = alias ? alias.trim() : target.trim();
            const slug = this.slugify(target.trim());
            return `<a href="#/note/${slug}" class="wikilink" data-target="${slug}">${display}</a>`;
        });
    },

    slugify(text) {
        return text.toLowerCase()
            .normalize('NFKD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/[^\w\s-]/g, '')
            .replace(/[-\s]+/g, '-')
            .replace(/^-+|-+$/g, '') || 'untitled';
    },

    renderBacklinks(backlinks) {
        if (!backlinks || backlinks.length === 0) {
            this.els.backlinks.innerHTML = '';
            return;
        }
        let html = '<div class="backlink-title">Backlinks</div>';
        backlinks.forEach(bl => {
            const title = bl.source_title || bl.source_id;
            html += `<span class="backlink-item" onclick="window.location.hash='/note/${bl.source_id}'">${title}</span>`;
        });
        this.els.backlinks.innerHTML = html;
    },

    async save() {
        if (!this.currentNoteId) return;
        try {
            await API.updateNote(this.currentNoteId, {
                title: this.els.title.value,
                content: this.els.textarea.value,
            });
            this.isDirty = false;
            App.toast('Nota salva!', 'success');
            App.loadNoteList();
        } catch (e) {
            App.toast('Erro ao salvar: ' + e.message, 'error');
        }
    },

    async deleteNote() {
        if (!this.currentNoteId) return;
        if (!confirm('Tem certeza que deseja deletar esta nota?')) return;
        try {
            await API.deleteNote(this.currentNoteId);
            this.currentNoteId = null;
            this.els.title.value = '';
            this.els.textarea.value = '';
            this.els.preview.innerHTML = '';
            this.els.backlinks.innerHTML = '';
            App.toast('Nota deletada', 'success');
            App.loadNoteList();
            window.location.hash = '/';
        } catch (e) {
            App.toast('Erro ao deletar', 'error');
        }
    },

    togglePreview() {
        this.previewVisible = !this.previewVisible;
        this.els.previewPane.style.display = this.previewVisible ? '' : 'none';
        this.els.editorPane.style.flex = this.previewVisible ? '1' : '1 1 100%';
    },

    scheduleAutoSave() {
        clearTimeout(this.autoSaveTimer);
        this.autoSaveTimer = setTimeout(() => {
            if (this.isDirty && this.currentNoteId) {
                this.save();
            }
        }, 2000);
    },

    async showLinkAutocomplete() {
        // Simple implementation: show command palette with notes
        const notes = await API.getNotes();
        App.showCommandPalette(notes, (note) => {
            const ta = this.els.textarea;
            const pos = ta.selectionStart;
            const before = ta.value.substring(0, pos);
            const after = ta.value.substring(pos);
            // Find the [[ before cursor
            const lastBrackets = before.lastIndexOf('[[');
            if (lastBrackets >= 0) {
                ta.value = before.substring(0, lastBrackets) + `[[${note.title}]]` + after;
                const newPos = lastBrackets + note.title.length + 4;
                ta.selectionStart = ta.selectionEnd = newPos;
            }
            ta.focus();
            this.isDirty = true;
            this.renderPreview();
        });
    },
};
