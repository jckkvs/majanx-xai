/**
 * MAJANX-XAI — Game Client v4
 * 雀魂風: Center rivers, discard animation, last-discard highlight
 *
 * Protocol (server -> client):
 *   { type:"state_update", game_state, current_player, turn, hand[],
 *     discards[][], dora_indicator, scores[], remaining_tiles? }
 *
 * Protocol (client -> server):
 *   { type:"join" }
 *   { type:"action_request", action:"discard", tile:"1m" }
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
        this.prevDiscardCounts = [0, 0, 0, 0]; // Track previous discard counts for animation

        // Settings
        this.doubleClickMode = localStorage.getItem('doubleClickMode') === 'true';
        this.aiHighlight = localStorage.getItem('aiHighlight') !== 'false';

        this.init();
    }

    /* ── Bootstrap ─────────────────────────── */
    init() {
        this.connectWebSocket();
        this.bindEvents();
        this.initSettings();
    }

    /* ── WebSocket ─────────────────────────── */
    connectWebSocket() {
        if (this.ws) {
            this.ws.onclose = null;
            this.ws.close();
        }
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${proto}//${location.host}/ws_ui?new_game=true`;
        this.setLoading('サーバーに接続中...');
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            this.setLoading('対局を準備中...');
            this.ws.send(JSON.stringify({ type: 'join' }));
        };
        this.ws.onmessage = (e) => {
            try { this.onMessage(JSON.parse(e.data)); }
            catch (err) { console.error('Parse error', err); }
        };
        this.ws.onclose = () => {
            this.showMsg('接続が切れました — 再接続中...');
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = setTimeout(() => this.connectWebSocket(), 3000);
        };
        this.ws.onerror = () => {};
    }

    /* ── Message Router ────────────────────── */
    onMessage(d) {
        if (d.type === 'state_update') this.onState(d);
    }

    onState(d) {
        this.gameState = d;
        this.showGame();

        this.renderHand(d.hand || []);
        this.renderOpponents();
        this.renderRivers(d.discards || []);
        this.renderDora(d.dora_indicator);
        this.renderScores(d.scores || [25000, 25000, 25000, 25000]);
        this.renderTurnHighlight(d.current_player);
        this.renderRemaining(d);
        this.renderCenterShield(d);

        this.isMyTurn = (d.current_player === this.playerId && d.game_state === 'DISCARDING');

        if (d.game_state === 'ROUND_END') {
            this.showMsg('流局');
            this.setControls(false);
        } else if (this.isMyTurn) {
            this.showMsg('あなたの番です');
            this.setControls(true);
        } else {
            const names = ['', '下家', '対面', '上家'];
            this.showMsg(`${names[d.current_player]}思考中...`);
            this.setControls(false);
        }
    }

    /* ── Tile helpers ──────────────────────── */
    display(t) {
        if (!t) return '?';
        const H = { E: '東', S: '南', W: '西', N: '北', C: '中', F: '發', P: '白' };
        if (H[t]) return H[t];
        const N = { 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八', 9: '九' };
        const S = { m: '萬', p: '筒', s: '索' };
        const n = t[0], s = t[1];
        return (N[n] && S[s]) ? N[n] + S[s] : t;
    }

    tileHTML(t) {
        const txt = this.display(t);
        if (txt.length <= 1) {
            if (t === 'C') return `<span class="char-c">${txt}</span>`;
            if (t === 'F') return `<span class="char-f">${txt}</span>`;
            return `<span>${txt}</span>`;
        }
        return txt.split('').map(c => `<span>${c}</span>`).join('');
    }

    cls(t) {
        if (!t) return '';
        if ('ESWNC'.includes(t[0]) && t.length === 1) return 'jihai';
        if (t === 'F' || t === 'P') return 'jihai';
        return { m: 'manzu', p: 'pinzu', s: 'souzu' }[t[1]] || '';
    }

    tileOrder(t) {
        const ho = { E: 100, S: 101, W: 102, N: 103, C: 104, F: 105, P: 106 };
        if (ho[t]) return ho[t];
        const so = { m: 0, p: 10, s: 20 };
        return (so[t[1]] || 30) + parseInt(t[0]);
    }

    /* ── Hand ──────────────────────────────── */
    renderHand(hand) {
        const el = document.getElementById('hand-0');
        if (!el) return;
        el.innerHTML = '';
        this.selectedIdx = null;
        this.selectedTile = null;

        const sorted = [...hand].sort((a, b) => this.tileOrder(a) - this.tileOrder(b));

        sorted.forEach((tile, i) => {
            const d = document.createElement('div');
            d.className = `tile ${this.cls(tile)}`;
            if (sorted.length % 3 === 2 && i === sorted.length - 1) {
                d.classList.add('tsumo-tile');
            }
            d.innerHTML = this.tileHTML(tile);
            d.dataset.i = i;
            d.dataset.t = tile;
            d.addEventListener('click', () => this.clickTile(i, tile, d));
            el.appendChild(d);
        });
    }

    /* ── Opponents ─────────────────────────── */
    renderOpponents() {
        for (let p = 1; p <= 3; p++) {
            const el = document.getElementById(`hand-${p}`);
            if (!el) continue;
            el.innerHTML = '';
            for (let j = 0; j < 13; j++) {
                const b = document.createElement('div');
                b.className = 'tile-back';
                el.appendChild(b);
            }
        }
    }

    /* ── Rivers (center cross pattern) ────── */
    renderRivers(discards) {
        for (let p = 0; p < 4; p++) {
            const el = document.getElementById(`river-${p}`);
            if (!el) continue;

            const arr = discards[p] || [];
            const prevCount = this.prevDiscardCounts[p];

            el.innerHTML = '';
            arr.forEach((t, idx) => {
                const d = document.createElement('div');
                d.className = `river-tile ${this.cls(t)}`;
                d.innerHTML = this.tileHTML(t);
                // Last discard of each player gets highlight
                if (idx === arr.length - 1) {
                    d.classList.add('last-discard');
                }
                // New tiles get animation
                if (idx >= prevCount) {
                    d.style.animation = 'tilePlace 0.25s ease-out';
                }
                el.appendChild(d);
            });

            this.prevDiscardCounts[p] = arr.length;
        }
    }

    /* ── Dora ──────────────────────────────── */
    renderDora(indicator) {
        const el = document.getElementById('dora-tiles');
        if (!el) return;
        el.innerHTML = '';
        if (indicator) {
            const d = document.createElement('div');
            d.className = `tile ${this.cls(indicator)}`;
            d.style.cssText = 'width:var(--tw-sm);height:var(--th-sm);font-size:0.55rem;cursor:default;border-radius:4px';
            d.innerHTML = this.tileHTML(indicator);
            el.appendChild(d);
        }
    }

    /* ── Scores ────────────────────────────── */
    renderScores(scores) {
        scores.forEach((s, i) => {
            const el = document.getElementById(`score-val-${i}`);
            if (el) el.textContent = s.toLocaleString();
        });
    }

    /* ── Turn highlight ────────────────────── */
    renderTurnHighlight(cp) {
        for (let i = 0; i < 4; i++) {
            const chip = document.getElementById(`score-${i}`);
            if (chip) chip.classList.toggle('active', i === cp);
        }
    }

    /* ── Remaining ─────────────────────────── */
    renderRemaining(d) {
        const remaining = Math.max(0, 136 - 14 - 52 - (d.turn || 0));
        // Top bar
        const el = document.getElementById('remain-count');
        if (el) el.textContent = remaining;
        // Center shield
        const shieldEl = document.getElementById('shield-remain');
        if (shieldEl) shieldEl.textContent = remaining;
    }

    /* ── Center Shield ────────────────────── */
    renderCenterShield(d) {
        const roundEl = document.getElementById('shield-round');
        if (roundEl) {
            const winds = ['東', '南', '西', '北'];
            const roundNum = (d.round_number || 0);
            const wind = winds[Math.floor(roundNum / 4)] || '東';
            const num = (roundNum % 4) + 1;
            roundEl.textContent = `${wind}${num}局`;
        }
    }

    /* ── Tile interaction ──────────────────── */
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
            // Single-click: animate then discard
            this.doDiscard(tile, el);
        }
    }

    deselect() {
        if (this.selectedIdx === null) return;
        document.querySelectorAll('#hand-0 .tile').forEach(t => t.classList.remove('selected'));
        this.selectedIdx = null;
        this.selectedTile = null;
    }

    doDiscard(tile, tileEl) {
        if (!this.isMyTurn || !tile) return;
        this.isMyTurn = false;
        this.deselect();
        this.setControls(false);

        // Animate the tile out
        if (tileEl) {
            tileEl.classList.add('discarding');
            tileEl.addEventListener('animationend', () => {
                this.showMsg('打牌中...');
                this.ws.send(JSON.stringify({ type: 'action_request', action: 'discard', tile }));
            }, { once: true });
        } else {
            this.showMsg('打牌中...');
            this.ws.send(JSON.stringify({ type: 'action_request', action: 'discard', tile }));
        }
    }

    /* ── UI helpers ────────────────────────── */
    showGame() {
        const ls = document.getElementById('loading-screen');
        const gs = document.getElementById('game-screen');
        if (ls && !ls.classList.contains('fade-out')) {
            ls.classList.add('fade-out');
            setTimeout(() => ls.classList.add('hidden'), 600);
        }
        if (gs) gs.classList.remove('hidden');
    }

    setLoading(msg) {
        const el = document.getElementById('loading-msg');
        if (el) el.textContent = msg;
    }

    showMsg(text) {
        const el = document.getElementById('game-message');
        if (el) el.textContent = text;
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

        if (dcToggle) {
            dcToggle.checked = this.doubleClickMode;
            dcToggle.addEventListener('change', () => {
                this.doubleClickMode = dcToggle.checked;
                localStorage.setItem('doubleClickMode', this.doubleClickMode);
            });
        }
        if (aiToggle) {
            aiToggle.checked = this.aiHighlight;
            aiToggle.addEventListener('change', () => {
                this.aiHighlight = aiToggle.checked;
                localStorage.setItem('aiHighlight', this.aiHighlight);
            });
        }
    }

    toggleSettings() {
        const panel = document.getElementById('settings-panel');
        const overlay = document.getElementById('settings-overlay');
        if (!panel) return;
        const isOpen = !panel.classList.contains('hidden');
        panel.classList.toggle('hidden', isOpen);
        overlay?.classList.toggle('hidden', isOpen);
    }

    /* ── Events ────────────────────────────── */
    bindEvents() {
        document.getElementById('btn-tsumo')?.addEventListener('click', () => {
            if (this.doubleClickMode && this.selectedTile) {
                this.doDiscard(this.selectedTile);
            } else if (!this.doubleClickMode) {
                this.showMsg('牌をクリックして打牌');
            } else {
                this.showMsg('牌を選択してください');
            }
        });

        document.getElementById('btn-menu')?.addEventListener('click', () => {
            this.toggleSettings();
        });

        document.getElementById('settings-close')?.addEventListener('click', () => {
            this.toggleSettings();
        });
        document.getElementById('settings-overlay')?.addEventListener('click', () => {
            this.toggleSettings();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.deselect();
                const panel = document.getElementById('settings-panel');
                if (panel && !panel.classList.contains('hidden')) this.toggleSettings();
            }
            if (e.key === 'Enter' && this.selectedTile && this.doubleClickMode) {
                this.doDiscard(this.selectedTile);
            }
        });
    }
}

/* ── Global ────────────────────────────── */
function closeWinModal() { document.getElementById('win-modal')?.classList.add('hidden'); }

let game;
document.addEventListener('DOMContentLoaded', () => { game = new MahjongGame(); });
