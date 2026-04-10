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
        if (d.type === 'state_update') {
            this.onState(d);
        } else if (d.type === 'five_pattern_recommendation') {
            this.onFivePatternRecommendation(d.data);
        }
    }

    /* ── AI Recommendation ─────────────────── */
    onFivePatternRecommendation(data) {
        console.log("Received five_pattern_recommendation:", data);
        if (!this.aiHighlight) return;
        
        // 推奨手牌を保存
        this.aiRecommendations = data;
        
        // UIに表示
        this.renderFivePatternRec(data);
        
        // 手牌のハイライトを更新
        if (this.gameState && this.gameState.hand) {
            this.renderHand(this.gameState.hand);
        }
    }

    renderFivePatternRec(data) {
        const container = document.getElementById('ai-recommendations');
        if (!container) return;
        
        container.innerHTML = '';
        container.style.display = 'grid';
        container.style.gridTemplateColumns = 'repeat(auto-fit, minmax(300px, 1fr))';
        container.style.gap = '16px';
        container.style.padding = '16px';
        
        // 5パターンを表示
        const patterns = [
            data.pattern_1,
            data.pattern_2,
            data.pattern_3,
            data.pattern_4,
            data.pattern_5
        ];
        
        patterns.forEach((pattern, idx) => {
            if (pattern) {
                const panel = this.createPatternPanel(pattern, idx + 1);
                container.appendChild(panel);
            }
        });
    }

    createPatternPanel(pattern, num) {
        const panel = document.createElement('div');
        panel.className = 'rec-panel';
        panel.style.borderLeft = `4px solid ${this.getPatternColor(num)}`;
        
        const content = pattern.content;
        
        panel.innerHTML = `
            <div class="panel-header">
                <span class="panel-number">${num}</span>
                <span class="panel-title">${pattern.name}</span>
            </div>
            <div class="panel-body">
                ${this.renderPatternContent(content, num)}
            </div>
        `;
        
        return panel;
    }

    renderPatternContent(content, patternNum) {
        if (patternNum === 1) {
            return `
                <div class="rec-tile">${this.display(content.recommended_tile)}</div>
                <div class="rec-prob">確率: ${(content.probability * 100).toFixed(1)}%</div>
                <div class="rec-reasoning">${content.reasoning}</div>
                ${content.alternatives && content.alternatives.length > 0 ? `
                    <div class="rec-alternatives">
                        <strong>代替案:</strong>
                        ${content.alternatives.map(a => `${this.display(a.tile)} (${(a.prob * 100).toFixed(1)}%)`).join(', ')}
                    </div>
                ` : ''}
            `;
        } else if (patternNum === 2 || patternNum === 3) {
            return `
                <div class="rec-judgment ${content.judgment.toLowerCase()}">
                    ${content.judgment === 'PUSH' ? '⚔️ 攻め' : content.judgment === 'FOLD' ? '🛡️ 守り' : '⚖️ バランス'}
                </div>
                <div class="rec-tile">${this.display(content.recommended_tile)}</div>
                <div class="rec-reasoning">${content.reasoning}</div>
                ${content.rules_applied && content.rules_applied.length > 0 ? `
                    <div class="rec-rules">
                        <strong>適用ルール:</strong>
                        <ul>
                            ${content.rules_applied.map(r => `
                                <li><strong>${r.id}</strong>: ${r.name}</li>
                            `).join('')}
                        </ul>
                    </div>
                ` : ''}
            `;
        } else {
            return `
                <div class="rec-tile">${this.display(content.ai_tile)}</div>
                <div class="rec-reasoning">${content.interpretation}</div>
                <div class="rec-consistency">
                    定石一致度: ${(content.consistency_score * 100).toFixed(0)}%
                    (${content.matching_rules_count}ルール一致)
                </div>
                ${content.rule_references && content.rule_references.length > 0 ? `
                    <div class="rec-rule-refs">
                        <strong>一致したルール:</strong>
                        ${content.rule_references.map(r => `<div>• ${r.reasoning}</div>`).join('')}
                    </div>
                ` : ''}
            `;
        }
    }

    getPatternColor(num) {
        const colors = ['#4fc3f7', '#66bb6a', '#ffa726', '#ab47bc', '#ef5350'];
        return colors[num - 1] || '#666';
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
        // スプライトシートを使用するため要素内のテキストは不要
        return '';
    }

    cls(t) {
        if (!t) return 'tile-back';
        let r = -1, c = -1;
        
        // 10x4 spritesheet: Row 0 is Honors, Row 1 is Manzu, Row 2 is Souzu, Row 3 is Pinzu.
        if (t[1] === 'm') { r = 1; }
        else if (t[1] === 's') { r = 2; }
        else if (t[1] === 'p') { r = 3; }
        else {
            const H2I = { E: 0, S: 1, W: 2, N: 3, P: 4, F: 5, C: 6 };
            if (H2I[t] !== undefined) {
                r = 0;
                c = H2I[t];
            }
        }
        
        if (r !== 0 && r !== -1) {
            if (t[0] === '0') {
                c = 5; // Akadora (Red 5)
            } else {
                let num = parseInt(t[0]);
                if (num <= 5) c = num - 1;
                else c = num; // Number >= 6 jumps over red 5
            }
        }

        if (r === -1) return 'tile-back';
        
        return `tile-sprite row-${r} col-${c}`;
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

        const currentHand = [...hand];
        let normalTiles = [];
        let tsumoTile = null;

        if (currentHand.length % 3 === 2) {
            tsumoTile = currentHand.pop();
            normalTiles = currentHand.sort((a, b) => this.tileOrder(a) - this.tileOrder(b));
        } else {
            normalTiles = currentHand.sort((a, b) => this.tileOrder(a) - this.tileOrder(b));
        }

        const recommendedTiles = new Set();
        if (this.aiRecommendations?.pattern_1?.content?.recommended_tile && this.aiRecommendations.pattern_1.content.recommended_tile !== "unknown") {
            recommendedTiles.add(this.aiRecommendations.pattern_1.content.recommended_tile);
        }
        if (this.aiRecommendations?.pattern_1?.content?.alternatives) {
            this.aiRecommendations.pattern_1.content.alternatives.forEach(alt => {
                if (alt.tile !== "unknown") {
                    recommendedTiles.add(alt.tile);
                }
            });
        }

        normalTiles.forEach((tile, i) => {
            const d = document.createElement('div');
            d.className = `tile ${this.cls(tile)}`;
            
            if (recommendedTiles.has(tile)) {
                d.classList.add('ai-recommended');
            }
            
            d.innerHTML = this.tileHTML(tile);
            d.dataset.i = i;
            d.dataset.t = tile;
            d.addEventListener('click', () => this.clickTile(i, tile, d));
            el.appendChild(d);
        });

        if (tsumoTile) {
            const d = document.createElement('div');
            d.className = `tile ${this.cls(tsumoTile)} tsumo-tile`;
            
            if (recommendedTiles.has(tsumoTile)) {
                d.classList.add('ai-recommended');
            }
            
            d.innerHTML = this.tileHTML(tsumoTile);
            d.dataset.i = normalTiles.length;
            d.dataset.t = tsumoTile;
            d.addEventListener('click', () => this.clickTile(normalTiles.length, tsumoTile, d));
            el.appendChild(d);
        }
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
