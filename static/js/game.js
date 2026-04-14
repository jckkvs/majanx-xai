/**
 * MAJANX-XAI — Game Client v6
 * 雀魂風: 3D裏面牌 + 中央河 + カン + ドラッグ理牌
 *
 * Protocol (server -> client):
 *   { type:"state_update", game_state, current_player, turn, hand[],
 *     discards[][], hand_counts[], open_melds[][], dora_indicator,
 *     scores[], round_number, available_actions[] }
 *
 * Protocol (client -> server):
 *   { type:"join" }
 *   { type:"action_request", action:"discard", tile:"1m" }
 *   { type:"action_request", action:"kan", tile:"1m" }
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

        // 手牌のカスタム並び順（ドラッグ用）
        this.customOrder = null;

        // Settings
        this.doubleClickMode = localStorage.getItem('doubleClickMode') === 'true';
        this.aiHighlight = localStorage.getItem('aiHighlight') !== 'false';
        this.autoRipai = localStorage.getItem('autoRipai') !== 'false';

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
        const url = `ws://localhost:8001/ws_ui?new_game=true`;
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
        this.aiRecommendations = data;
        this.renderFivePatternRec(data);
        if (this.gameState && this.gameState.hand) {
            this.renderHand(this.gameState.hand);
        }
    }

    renderFivePatternRec(data) {
        const container = document.getElementById('ai-recommendations');
        if (!container) return;
        container.innerHTML = '';
        container.style.display = 'grid';

        const patterns = [data.pattern_1, data.pattern_2, data.pattern_3, data.pattern_4, data.pattern_5];
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
            const judgmentClass = (content.judgment || 'BALANCE').toLowerCase();
            const judgmentLabels = {
                'push': '⚔️ 攻め', 'fold': '🛡️ 守り', 'balance': '⚖️ バランス',
                'aggressive': '🔥 超攻め', 'defensive': '🛡️ 守備'
            };
            return `
                <div class="rec-judgment ${judgmentClass}">
                    ${judgmentLabels[judgmentClass] || judgmentClass}
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

    /* ── State Update ─────────────────────── */
    onState(d) {
        this.gameState = d;
        this.showGame();

        this.renderHand(d.hand || []);
        this.renderOpponents(d.hand_counts || [0, 13, 13, 13], d.open_melds || []);
        this.renderRivers(d.discards || []);
        this.renderDora(d.dora_indicator);
        this.renderScores(d.scores || [25000, 25000, 25000, 25000]);
        this.renderTurnHighlight(d.current_player);
        this.renderRemaining(d);
        this.renderCenterShield(d);
        this.renderMelds(d.open_melds || []);

        this.isMyTurn = (d.current_player === this.playerId && d.game_state === 'DISCARDING');

        // カンボタンの制御
        this.updateKanButton(d.available_actions || []);

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
        const H = { E: '東', S: '南', W: '西', N: '北', Wh: '白', Gr: '發', Rd: '中', C: '中', F: '發', P: '白' };
        if (H[t]) return H[t];
        const N = { 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八', 9: '九', 0: '五' };
        const S = { m: '萬', p: '筒', s: '索' };
        const n = t[0], s = t[1];
        return (N[n] && S[s]) ? N[n] + S[s] : t;
    }

    tileHTML(t) {
        return '';
    }

    cls(t) {
        if (!t) return 'tile-back';
        let r = -1, c = -1;

        if (t[1] === 'm') { r = 1; }
        else if (t[1] === 's') { r = 2; }
        else if (t[1] === 'p') { r = 3; }
        else {
            const H2I = { E: 0, S: 1, W: 2, N: 3, P: 4, Wh: 4, F: 5, Gr: 5, C: 6, Rd: 6 };
            if (H2I[t] !== undefined) {
                r = 0;
                c = H2I[t];
            }
        }

        if (r !== 0 && r !== -1) {
            if (t[0] === '0') {
                c = 5;
            } else {
                let num = parseInt(t[0]);
                if (num <= 5) c = num - 1;
                else c = num;
            }
        }

        if (r === -1) return 'tile-back';
        return `tile-sprite row-${r} col-${c}`;
    }

    tileOrder(t) {
        const ho = { E: 100, S: 101, W: 102, N: 103, Wh: 104, Gr: 105, Rd: 106, C: 104, F: 105, P: 106 };
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

        let currentHand = [...hand];
        let normalTiles = [];
        let tsumoTile = null;

        if (currentHand.length % 3 === 2) {
            tsumoTile = currentHand.pop();
            normalTiles = this.autoRipai
                ? currentHand.sort((a, b) => this.tileOrder(a) - this.tileOrder(b))
                : (this.customOrder && this.customOrder.length === currentHand.length ? this.customOrder : currentHand);
        } else {
            normalTiles = this.autoRipai
                ? currentHand.sort((a, b) => this.tileOrder(a) - this.tileOrder(b))
                : currentHand;
        }

        // カスタムオーダーをリセット（新しい手牌の場合）
        if (!this.autoRipai && (!this.customOrder || this.customOrder.length !== normalTiles.length)) {
            this.customOrder = [...normalTiles];
        }

        const recommendedTiles = new Set();
        if (this.aiRecommendations?.pattern_1?.content?.recommended_tile && this.aiRecommendations.pattern_1.content.recommended_tile !== "unknown") {
            recommendedTiles.add(this.aiRecommendations.pattern_1.content.recommended_tile);
        }

        normalTiles.forEach((tile, i) => {
            const d = this.createTileElement(tile, i, recommendedTiles);
            if (!this.autoRipai) {
                this.makeDraggable(d, i, el);
            }
            el.appendChild(d);
        });

        if (tsumoTile) {
            const d = this.createTileElement(tsumoTile, normalTiles.length, recommendedTiles);
            d.classList.add('tsumo-tile');
            el.appendChild(d);
        }
    }

    createTileElement(tile, idx, recommendedTiles) {
        const d = document.createElement('div');
        d.className = `tile ${this.cls(tile)}`;
        if (recommendedTiles.has(tile)) {
            d.classList.add('ai-recommended');
        }
        d.innerHTML = this.tileHTML(tile);
        d.dataset.i = idx;
        d.dataset.t = tile;
        d.addEventListener('click', () => this.clickTile(idx, tile, d));
        return d;
    }

    /* ── Drag & Drop (manual ripai) ────────── */
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
            container.querySelectorAll('.tile').forEach(t => t.classList.remove('drag-over'));
        });

        tileEl.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            tileEl.classList.add('drag-over');
        });

        tileEl.addEventListener('dragleave', () => {
            tileEl.classList.remove('drag-over');
        });

        tileEl.addEventListener('drop', (e) => {
            e.preventDefault();
            tileEl.classList.remove('drag-over');
            const fromIdx = parseInt(e.dataTransfer.getData('text/plain'));
            const toIdx = idx;
            if (fromIdx !== toIdx && this.customOrder) {
                // Swap tiles in custom order
                const temp = this.customOrder[fromIdx];
                this.customOrder.splice(fromIdx, 1);
                this.customOrder.splice(toIdx, 0, temp);
                this.renderHand(this.gameState.hand);
            }
        });
    }

    /* ── Opponents (3D standing tiles) ─────── */
    renderOpponents(handCounts, openMelds) {
        for (let p = 1; p <= 3; p++) {
            const el = document.getElementById(`hand-${p}`);
            if (!el) continue;
            el.innerHTML = '';

            const meldCount = (openMelds[p] || []).length;
            const tileCount = (handCounts[p] || 13);

            for (let j = 0; j < tileCount; j++) {
                const b = document.createElement('div');
                b.className = 'tile-back-3d';
                // ツモ牌（14枚目）に隙間を入れる
                if (j === tileCount - 1 && tileCount % 3 === 2) {
                    b.classList.add('tsumo-gap');
                }
                el.appendChild(b);
            }
        }
    }

    /* ── Melds (open melds display) ─────────── */
    renderMelds(openMelds) {
        for (let p = 0; p < 4; p++) {
            const el = document.getElementById(`melds-${p}`);
            if (!el) continue;
            el.innerHTML = '';

            const melds = openMelds[p] || [];
            melds.forEach(meld => {
                const group = document.createElement('div');
                group.className = 'meld-group';
                meld.forEach(tile => {
                    const t = document.createElement('div');
                    if (p === 0) {
                        // 自分の暗槓は表向きだが端2枚は裏
                        // 簡易表示: 全部表向き
                        t.className = `tile ${this.cls(tile)}`;
                        t.style.cssText = `width:var(--tw-sm);height:var(--th-sm);cursor:default;margin:0`;
                    } else {
                        t.className = 'tile-back-3d';
                    }
                    group.appendChild(t);
                });
                el.appendChild(group);
            });
        }
    }

    /* ── Rivers (6 tiles per row) ────────────── */
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
            d.style.cssText = 'width:var(--tw-sm);height:var(--th-sm);font-size:0.55rem;cursor:default;border-radius:4px;margin:0';
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

        // Compass highlight
        const compassMap = { 0: 'compass-s', 1: 'compass-e', 2: 'compass-n', 3: 'compass-w' };
        ['compass-n', 'compass-s', 'compass-e', 'compass-w'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.remove('active');
        });
        const activeCompass = document.getElementById(compassMap[cp]);
        if (activeCompass) activeCompass.classList.add('active');
    }

    /* ── Remaining ─────────────────────────── */
    renderRemaining(d) {
        const remaining = Math.max(0, 136 - 14 - 52 - (d.turn || 0));
        const el = document.getElementById('remain-count');
        if (el) el.textContent = remaining;
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

            // Update top bar too
            const topRoundEl = document.getElementById('round-display');
            if (topRoundEl) topRoundEl.textContent = `${wind}${num}局`;
        }
    }

    /* ── Kan Button Control ─────────────────── */
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
        if (tiles.length === 1) {
            // 1種類のみ → 直接カン
            this.doKan(tiles[0]);
            return;
        }
        // 複数種類 → モーダル表示
        const modal = document.getElementById('kan-modal');
        const choices = document.getElementById('kan-choices');
        if (!modal || !choices) return;

        choices.innerHTML = '';
        tiles.forEach(tile => {
            const btn = document.createElement('button');
            btn.className = 'modal-btn accent';
            btn.textContent = `${this.display(tile)} × 4`;
            btn.addEventListener('click', () => {
                modal.classList.add('hidden');
                this.doKan(tile);
            });
            choices.appendChild(btn);
        });

        modal.classList.remove('hidden');
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
        this.customOrder = null; // Reset custom order on discard

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
        // Kan button managed separately by updateKanButton
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
        if (ripaiToggle) {
            ripaiToggle.checked = this.autoRipai;
            ripaiToggle.addEventListener('change', () => {
                this.autoRipai = ripaiToggle.checked;
                localStorage.setItem('autoRipai', this.autoRipai);
                this.customOrder = null;
                if (this.gameState && this.gameState.hand) {
                    this.renderHand(this.gameState.hand);
                }
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

        // カンボタン
        document.getElementById('btn-kan')?.addEventListener('click', () => {
            const kanBtn = document.getElementById('btn-kan');
            if (kanBtn && kanBtn.dataset.kanTiles) {
                try {
                    const tiles = JSON.parse(kanBtn.dataset.kanTiles);
                    this.showKanModal(tiles);
                } catch (e) {
                    console.error('Kan parse error', e);
                }
            }
        });

        // カンモーダルキャンセル
        document.getElementById('kan-cancel')?.addEventListener('click', () => {
            document.getElementById('kan-modal')?.classList.add('hidden');
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
                document.getElementById('kan-modal')?.classList.add('hidden');
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
