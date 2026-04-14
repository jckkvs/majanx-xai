/**
 * MajanX-XAI v2 — Game Client
 * WebSocket client + UI controller
 */

class MahjongGame {
    constructor() {
        this.ws = null;
        this.gameState = null;
        this.selectedIdx = null;
        this.selectedTile = null;
        this.playerId = 0;
        this.isMyTurn = false;
        this.reconnectTimer = null;
        this.prevDiscardCounts = [0, 0, 0, 0];
        this.aiRecommendations = null;
        this.customOrder = null;

        // Settings (persisted in localStorage)
        this.doubleClickMode = localStorage.getItem('v2_doubleClick') === 'true';
        this.aiHighlight = localStorage.getItem('v2_aiHighlight') !== 'false';
        this.autoRipai = localStorage.getItem('v2_autoRipai') !== 'false';

        this.init();
    }

    init() {
        this.connectWebSocket();
        this.bindEvents();
        this.initSettings();
        this.loadCpuStrength();
    }

    /* ── WebSocket ─────────────────────────── */
    connectWebSocket() {
        if (this.ws) {
            this.ws.onclose = null;
            this.ws.close();
        }
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${proto}//${location.host}/ws_ui?new_game=true`;
        Renderer.setLoadingMsg('サーバーに接続中...');
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            Renderer.setLoadingMsg('対局を準備中...');
            this.ws.send(JSON.stringify({ type: 'join' }));
        };
        this.ws.onmessage = (e) => {
            try { this.onMessage(JSON.parse(e.data)); }
            catch (err) { console.error('Parse error', err); }
        };
        this.ws.onclose = () => {
            Renderer.showMsg('接続が切れました — 再接続中...');
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = setTimeout(() => this.connectWebSocket(), 3000);
        };
        this.ws.onerror = () => {};
    }

    /* ── Message Router ────────────────────── */
    onMessage(d) {
        // Handle all message types
        if (d.type === 'state_update') {
            this.onState(d);
        } else if (d.type === 'five_pattern_recommendation') {
            this.onAIRecommendation(d.data);
        } else if (d.type === 'waiting_next_round') {
            Renderer.showMsg('次局の開始を待っています...');
        } else if (d.type === 'hora' || d.type === 'agari') {
            this.showWinModal(d);
        }
    }

    /* ── AI Recommendation ─────────────────── */
    onAIRecommendation(data) {
        if (!this.aiHighlight) return;
        this.aiRecommendations = data;
        if (this.gameState && this.gameState.hand) {
            this.renderMyHand(this.gameState.hand);
        }
    }

    /* ── State Update ─────────────────────── */
    onState(d) {
        this.gameState = d;
        Renderer.showGame();

        this.renderMyHand(d.hand || []);
        Renderer.renderOpponents(d.hand_counts || [0, 13, 13, 13], d.open_melds || []);
        this.prevDiscardCounts = Renderer.renderRivers(d.discards || [], this.prevDiscardCounts);
        Renderer.renderDora(d.dora_indicator);
        Renderer.renderScores(d.scores || [25000, 25000, 25000, 25000]);
        Renderer.renderTurnHighlight(d.current_player);
        Renderer.renderRemaining(d);
        Renderer.renderCenterShield(d);
        Renderer.renderMelds(d.open_melds || []);

        this.isMyTurn = (d.current_player === this.playerId && d.game_state === 'DISCARDING');
        this.updateKanButton(d.available_actions || []);

        if (d.game_state === 'ROUND_END') {
            Renderer.showMsg('流局');
            this.setControls(false);
        } else if (this.isMyTurn) {
            Renderer.showMsg('あなたの番です');
            this.setControls(true);
        } else {
            const names = ['', '下家', '対面', '上家'];
            Renderer.showMsg(`${names[d.current_player]}思考中...`);
            this.setControls(false);
        }
    }

    /* ── WIN Modal ────────────────────────── */
    showWinModal(data) {
        const modal = document.getElementById('win-modal');
        const titleEl = document.getElementById('win-title');
        const details = document.getElementById('win-details');
        if (!modal || !details) return;

        const winner = data.winner !== undefined ? data.winner : (this.gameState ? this.gameState.current_player : 0);
        const names = ['自家', '下家', '対面', '上家'];

        titleEl.textContent = (winner === this.playerId) ? '和了 (Win)!' : '放銃 (Loss)...';
        
        let html = `<p><b>${names[winner]}</b> の和了です。</p>`;
        if (data.hand_value) {
            html += `<p>役: ${data.hand_value.yaku?.join(', ') || 'なし'}</p>`;
            html += `<p>点数: ${data.hand_value.score || data.score || '--'}点</p>`;
        }
        
        details.innerHTML = html;
        modal.classList.remove('hidden');
    }

    /* ── Render Hand (delegates to Renderer) ─ */
    renderMyHand(hand) {
        const recommendedTiles = new Set();
        if (this.aiHighlight && this.aiRecommendations) {
            const rec = this.aiRecommendations;
            if (rec.pattern_1?.content?.recommended_tile && rec.pattern_1.content.recommended_tile !== 'unknown') {
                recommendedTiles.add(rec.pattern_1.content.recommended_tile);
            }
        }

        const orderedTiles = Renderer.renderHand('hand-0', hand, {
            isMyTurn: this.isMyTurn,
            autoRipai: this.autoRipai,
            customOrder: this.customOrder,
            recommendedTiles,
            onTileClick: (idx, tile, el) => this.clickTile(idx, tile, el),
        });

        // Track custom order for drag reordering
        if (!this.autoRipai) {
            if (!this.customOrder || this.customOrder.length !== orderedTiles.length) {
                this.customOrder = [...orderedTiles];
            }
        }

        // Make draggable if manual ripai
        if (!this.autoRipai) {
            const container = document.getElementById('hand-0');
            container.querySelectorAll('.hand-tile').forEach((tileEl, i) => {
                if (tileEl.dataset.tsumo) return; // Don't drag tsumo tile
                this.makeDraggable(tileEl, i, container);
            });
        }
    }

    /* ── Drag & Drop ──────────────────────── */
    makeDraggable(tileEl, idx, container) {
        tileEl.classList.add('drag-handle');
        tileEl.draggable = true;

        tileEl.addEventListener('dragstart', (e) => {
            tileEl.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', idx.toString());
        });
        tileEl.addEventListener('dragend', () => {
            tileEl.classList.remove('dragging');
            container.querySelectorAll('.hand-tile').forEach(t => t.classList.remove('drag-over'));
        });
        tileEl.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            tileEl.classList.add('drag-over');
        });
        tileEl.addEventListener('dragleave', () => tileEl.classList.remove('drag-over'));
        tileEl.addEventListener('drop', (e) => {
            e.preventDefault();
            tileEl.classList.remove('drag-over');
            const fromIdx = parseInt(e.dataTransfer.getData('text/plain'));
            const toIdx = idx;
            if (fromIdx !== toIdx && this.customOrder) {
                const temp = this.customOrder[fromIdx];
                this.customOrder.splice(fromIdx, 1);
                this.customOrder.splice(toIdx, 0, temp);
                this.renderMyHand(this.gameState.hand);
            }
        });
    }

    /* ── Kan Button ────────────────────────── */
    updateKanButton(actions) {
        const kanBtn = document.getElementById('btn-kan');
        if (!kanBtn) return;
        const kanAction = actions.find(a => a.type === 'kan');
        if (kanAction && kanAction.tiles && kanAction.tiles.length > 0) {
            kanBtn.disabled = false;
            kanBtn.dataset.kanTiles = JSON.stringify(kanAction.tiles);
        } else {
            kanBtn.disabled = true;
            delete kanBtn.dataset.kanTiles;
        }
    }

    doKan(tile) {
        if (!this.isMyTurn || !tile) return;
        this.ws.send(JSON.stringify({ type: 'action_request', action: 'kan', tile }));
    }

    showKanModal(tiles) {
        if (tiles.length === 1) { this.doKan(tiles[0]); return; }
        const modal = document.getElementById('kan-modal');
        const choices = document.getElementById('kan-choices');
        if (!modal || !choices) return;
        choices.innerHTML = '';
        tiles.forEach(tile => {
            const btn = document.createElement('button');
            btn.className = 'modal-btn accent';
            btn.textContent = `${TileMap.displayName(tile)} × 4`;
            btn.addEventListener('click', () => {
                modal.classList.add('hidden');
                this.doKan(tile);
            });
            choices.appendChild(btn);
        });
        modal.classList.remove('hidden');
    }

    /* ── Tile Interaction ──────────────────── */
    clickTile(idx, tile, el) {
        if (!this.isMyTurn) return;

        if (this.doubleClickMode) {
            if (this.selectedIdx === idx) {
                this.doDiscard(tile, el);
                return;
            }
            this.deselect();
            this.selectedIdx = idx;
            this.selectedTile = tile;
            el.classList.add('selected');
        } else {
            this.doDiscard(tile, el);
        }
    }

    deselect() {
        if (this.selectedIdx === null) return;
        document.querySelectorAll('#hand-0 .hand-tile').forEach(t => t.classList.remove('selected'));
        this.selectedIdx = null;
        this.selectedTile = null;
    }

    doDiscard(tile, tileEl) {
        if (!this.isMyTurn || !tile) return;
        this.isMyTurn = false;
        this.deselect();
        this.setControls(false);
        this.customOrder = null;

        if (tileEl) {
            tileEl.classList.add('discarding');
            tileEl.addEventListener('animationend', () => {
                Renderer.showMsg('打牌中...');
                this.ws.send(JSON.stringify({ type: 'action_request', action: 'discard', tile }));
            }, { once: true });
        } else {
            Renderer.showMsg('打牌中...');
            this.ws.send(JSON.stringify({ type: 'action_request', action: 'discard', tile }));
        }
    }

    setControls(on) {
        const btn = document.getElementById('btn-tsumo');
        if (btn) btn.disabled = !on;
        ['btn-riichi', 'btn-ron'].forEach(id => {
            const b = document.getElementById(id);
            if (b) b.disabled = true;
        });
    }

    /* ── Settings ──────────────────────────── */
    initSettings() {
        const dcToggle = document.getElementById('setting-doubleclick');
        const aiToggle = document.getElementById('setting-ai-highlight');
        const ripaiToggle = document.getElementById('setting-autoripai');

        if (dcToggle) {
            dcToggle.checked = this.doubleClickMode;
            dcToggle.addEventListener('change', () => {
                this.doubleClickMode = dcToggle.checked;
                localStorage.setItem('v2_doubleClick', this.doubleClickMode);
            });
        }
        if (aiToggle) {
            aiToggle.checked = this.aiHighlight;
            aiToggle.addEventListener('change', () => {
                this.aiHighlight = aiToggle.checked;
                localStorage.setItem('v2_aiHighlight', this.aiHighlight);
            });
        }
        if (ripaiToggle) {
            ripaiToggle.checked = this.autoRipai;
            ripaiToggle.addEventListener('change', () => {
                this.autoRipai = ripaiToggle.checked;
                localStorage.setItem('v2_autoRipai', this.autoRipai);
                this.customOrder = null;
                if (this.gameState && this.gameState.hand) {
                    this.renderMyHand(this.gameState.hand);
                }
            });
        }
    }

    async loadCpuStrength() {
        try {
            const res = await fetch('/api/settings');
            const data = await res.json();
            const slider = document.getElementById('setting-cpu-strength');
            const valEl = document.getElementById('cpu-strength-val');
            if (slider) {
                slider.value = Math.round(data.cpu_strength * 100);
                if (valEl) valEl.textContent = slider.value + '%';
            }
        } catch (e) { /* ignore */ }
    }

    async updateCpuStrength(value) {
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cpu_strength: value / 100 }),
            });
        } catch (e) { /* ignore */ }
    }

    toggleSettings() {
        const panel = document.getElementById('settings-panel');
        const overlay = document.getElementById('settings-overlay');
        if (!panel) return;
        const isOpen = !panel.classList.contains('hidden');
        panel.classList.toggle('hidden', isOpen);
        overlay?.classList.toggle('hidden', isOpen);
    }

    /* ── Event Bindings ────────────────────── */
    bindEvents() {
        document.getElementById('btn-tsumo')?.addEventListener('click', () => {
            if (this.doubleClickMode && this.selectedTile) {
                this.doDiscard(this.selectedTile);
            } else if (!this.doubleClickMode) {
                Renderer.showMsg('牌をクリックして打牌');
            } else {
                Renderer.showMsg('牌を選択してください');
            }
        });

        document.getElementById('btn-kan')?.addEventListener('click', () => {
            const kanBtn = document.getElementById('btn-kan');
            if (kanBtn?.dataset.kanTiles) {
                try {
                    this.showKanModal(JSON.parse(kanBtn.dataset.kanTiles));
                } catch (e) { console.error('Kan parse error', e); }
            }
        });

        document.getElementById('kan-cancel')?.addEventListener('click', () => {
            document.getElementById('kan-modal')?.classList.add('hidden');
        });

        document.getElementById('btn-menu')?.addEventListener('click', () => this.toggleSettings());
        document.getElementById('settings-close')?.addEventListener('click', () => this.toggleSettings());
        document.getElementById('settings-overlay')?.addEventListener('click', () => this.toggleSettings());

        // Win Modal buttons
        document.getElementById('btn-next-kyoku')?.addEventListener('click', () => {
            this.ws.send(JSON.stringify({ type: 'join' })); // Restart/Next
            closeWinModal();
        });
        document.getElementById('btn-close-win')?.addEventListener('click', () => closeWinModal());

        // CPU strength slider
        const slider = document.getElementById('setting-cpu-strength');
        const valEl = document.getElementById('cpu-strength-val');
        if (slider) {
            slider.addEventListener('input', () => {
                if (valEl) valEl.textContent = slider.value + '%';
            });
            slider.addEventListener('change', () => {
                this.updateCpuStrength(parseInt(slider.value));
            });
        }

        // Keyboard
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.deselect();
                const panel = document.getElementById('settings-panel');
                if (panel && !panel.classList.contains('hidden')) this.toggleSettings();
                document.getElementById('kan-modal')?.classList.add('hidden');
                closeWinModal();
            }
            if (e.key === 'Enter' && this.selectedTile && this.doubleClickMode) {
                this.doDiscard(this.selectedTile);
            }
        });
    }
}

/* ── Global ────────────────────────────── */
function closeWinModal() {
    document.getElementById('win-modal')?.classList.add('hidden');
}

let game;
document.addEventListener('DOMContentLoaded', () => {
    game = new MahjongGame();
});
