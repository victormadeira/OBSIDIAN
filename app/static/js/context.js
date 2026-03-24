// ============================================
// OBSIDIAN AI Context Builder
// ============================================

const ContextBuilder = {
    notes: [],

    async init() {
        this.notes = await API.getNotes();
        this.renderNoteList();
        this.bindEvents();
    },

    renderNoteList(filter = '') {
        const container = document.getElementById('context-note-list');
        const filtered = filter
            ? this.notes.filter(n =>
                n.title.toLowerCase().includes(filter.toLowerCase()) ||
                n.tags.some(t => t.includes(filter.toLowerCase()))
            )
            : this.notes;

        container.innerHTML = filtered.map(n => `
            <div class="context-note-item">
                <input type="checkbox" id="ctx-note-${n.id}" value="${n.id}">
                <label for="ctx-note-${n.id}">
                    ${this.escapeHtml(n.title)}
                    ${n.tags.length ? '<span style="color:var(--text-muted);font-size:11px"> #' + n.tags.join(' #') + '</span>' : ''}
                </label>
            </div>
        `).join('');

        if (filtered.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>Nenhuma nota encontrada</p></div>';
        }
    },

    bindEvents() {
        // Search filter
        document.getElementById('context-search').addEventListener('input', (e) => {
            this.renderNoteList(e.target.value);
        });

        // Depth slider
        const depthSlider = document.getElementById('ctx-depth');
        const depthValue = document.getElementById('ctx-depth-value');
        depthSlider.addEventListener('input', () => {
            depthValue.textContent = depthSlider.value;
        });

        // Build button
        document.getElementById('btn-build-context').addEventListener('click', () => {
            this.build();
        });

        // Copy button
        document.getElementById('btn-copy-context').addEventListener('click', () => {
            this.copyOutput();
        });
    },

    async build() {
        const selected = [];
        document.querySelectorAll('#context-note-list input[type="checkbox"]:checked').forEach(cb => {
            selected.push(cb.value);
        });

        if (selected.length === 0) {
            App.toast('Selecione pelo menos uma nota', 'error');
            return;
        }

        const options = {
            note_ids: selected,
            include_linked: document.getElementById('ctx-include-linked').checked,
            depth: parseInt(document.getElementById('ctx-depth').value),
            format: document.getElementById('ctx-format').value,
            max_tokens_estimate: parseInt(document.getElementById('ctx-max-tokens').value),
            include_metadata: document.getElementById('ctx-include-metadata').checked,
        };

        try {
            const result = await API.buildContext(options);
            const output = document.getElementById('context-output');
            output.innerHTML = '';
            const code = document.createElement('code');
            code.textContent = result.content;
            output.appendChild(code);

            document.getElementById('context-stats').textContent =
                `${result.note_count} nota(s) | ~${result.estimated_tokens.toLocaleString()} tokens | ${result.format.toUpperCase()}`;

            App.toast('Contexto gerado!', 'success');
        } catch (e) {
            App.toast('Erro ao gerar contexto: ' + e.message, 'error');
        }
    },

    async copyOutput() {
        const output = document.getElementById('context-output');
        const text = output.textContent;
        if (!text || text === 'Selecione notas e clique em "Gerar Contexto"') {
            App.toast('Nada para copiar', 'error');
            return;
        }
        try {
            await navigator.clipboard.writeText(text);
            App.toast('Copiado!', 'success');
        } catch {
            // Fallback
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            App.toast('Copiado!', 'success');
        }
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
};
