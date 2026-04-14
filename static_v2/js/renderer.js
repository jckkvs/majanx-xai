/**
 * MajanX-XAI v2 — Renderer
 * DOM rendering using individual tile images
 */

const Renderer = {
    /**
     * Apply tile image as background to an element
     */
    applyTileImage(el, tileId, orientation = 0) {
        const url = TileMap.getImageUrl(tileId, orientation);
        if (url) {
            el.style.backgroundImage = `url('${url}')`;
            if (TileMap.isRedDora(tileId)) {
                el.classList.add('red-dora');
            }
        }
    },

    /**
     * Render player's hand into container.
     */
    renderHand(containerId, hand, options = {}) {
        const el = document.getElementById(containerId);
        if (!el) return [];
        el.innerHTML = '';

        const {
            isMyTurn = false,
            autoRipai = true,
            customOrder = null,
            recommendedTiles = new Set(),
            onTileClick = null,
        } = options;

        let tiles = [...hand];
        let tsumoTile = null;

        // Separate tsumo tile (14th tile)
        if (tiles.length % 3 === 2) {
            tsumoTile = tiles.pop();
        }

        // Sort normal tiles
        if (autoRipai) {
            tiles.sort((a, b) => TileMap.sortKey(a) - TileMap.sortKey(b));
        } else if (customOrder && customOrder.length === tiles.length) {
            tiles = [...customOrder];
        }

        // Render normal tiles
        tiles.forEach((tile, i) => {
            const d = this._createHandTile(tile, i, {
                isMyTurn, onTileClick,
                isRecommended: recommendedTiles.has(tile),
            });
            el.appendChild(d);
        });

        // Tsumo separator + tile
        if (tsumoTile) {
            const spacer = document.createElement('div');
            spacer.className = 'tsumo-separator';
            el.appendChild(spacer);

            const d = this._createHandTile(tsumoTile, tiles.length, {
                isMyTurn, onTileClick,
                isRecommended: recommendedTiles.has(tsumoTile),
                isTsumo: true,
            });
            el.appendChild(d);
        }

        return tiles;
    },

    _createHandTile(tile, idx, options = {}) {
        const { isMyTurn, isRecommended, onTileClick, isTsumo } = options;
        const d = document.createElement('div');
        d.className = 'hand-tile';
        this.applyTileImage(d, tile, 0); // Self hand is always face-on

        if (isRecommended) d.classList.add('ai-recommended');
        if (isTsumo) d.dataset.tsumo = 'true';
        d.dataset.idx = idx;
        d.dataset.tile = tile;

        if (isMyTurn && onTileClick) {
            d.addEventListener('click', () => onTileClick(idx, tile, d));
        }
        return d;
    },

    /**
     * Render opponent hands (back tiles)
     */
    renderOpponents(handCounts, openMelds) {
        for (let p = 1; p <= 3; p++) {
            const el = document.getElementById(`hand-${p}`);
            if (!el) continue;
            el.innerHTML = '';

            const tileCount = handCounts[p] || 13;

            for (let j = 0; j < tileCount; j++) {
                const b = document.createElement('div');
                b.className = 'tile-back-3d';
                if (j === tileCount - 1 && tileCount % 3 === 2) {
                    b.classList.add('tsumo-gap');
                }
                el.appendChild(b);
            }
        }
    },

    /**
     * Render discard rivers
     */
    renderRivers(discards, prevCounts) {
        const newCounts = [0, 0, 0, 0];
        // Orientation Map: 0:P0, 1:P1, 2:P2, 3:P3
        // P0 -> _2, P1 -> _3, P2 -> _1, P3 -> _4
        const orientationMap = [2, 3, 1, 4];

        for (let p = 0; p < 4; p++) {
            const el = document.getElementById(`river-${p}`);
            if (!el) continue;

            const arr = discards[p] || [];
            const prev = prevCounts[p] || 0;
            newCounts[p] = arr.length;

            el.innerHTML = '';
            arr.forEach((t, idx) => {
                const d = document.createElement('div');
                d.className = 'river-tile';
                this.applyTileImage(d, t, orientationMap[p]);
                if (idx === arr.length - 1) d.classList.add('last-discard');
                if (idx >= prev) d.style.animation = 'tilePlace 0.25s ease-out';
                el.appendChild(d);
            });
        }
        return newCounts;
    },

    /**
     * Render dora indicator
     */
    renderDora(indicator) {
        const el = document.getElementById('dora-tiles');
        if (!el) return;
        el.innerHTML = '';
        if (indicator) {
            const d = document.createElement('div');
            d.className = 'dora-tile';
            this.applyTileImage(d, indicator, 0);
            el.appendChild(d);
        }
    },

    /**
     * Render scores
     */
    renderScores(scores) {
        scores.forEach((s, i) => {
            const el = document.getElementById(`score-val-${i}`);
            if (el) el.textContent = s.toLocaleString();
        });
    },

    /**
     * Turn highlight
     */
    renderTurnHighlight(cp) {
        for (let i = 0; i < 4; i++) {
            const chip = document.getElementById(`score-${i}`);
            if (chip) chip.classList.toggle('active', i === cp);
        }
        const compassMap = { 0: 'compass-s', 1: 'compass-e', 2: 'compass-n', 3: 'compass-w' };
        ['compass-n', 'compass-s', 'compass-e', 'compass-w'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.remove('active');
        });
        const active = document.getElementById(compassMap[cp]);
        if (active) active.classList.add('active');
    },

    /**
     * Remaining tiles
     */
    renderRemaining(data) {
        const remaining = Math.max(0, 136 - 14 - 52 - (data.turn || 0));
        const el = document.getElementById('remain-count');
        if (el) el.textContent = remaining;
        const shieldEl = document.getElementById('shield-remain');
        if (shieldEl) shieldEl.textContent = remaining;
    },

    /**
     * Center shield
     */
    renderCenterShield(data) {
        const roundEl = document.getElementById('shield-round');
        if (!roundEl) return;
        const winds = ['東', '南', '西', '北'];
        const roundNum = data.round_number || 0;
        const wind = winds[Math.floor(roundNum / 4)] || '東';
        const num = (roundNum % 4) + 1;
        const text = `${wind}${num}局`;
        roundEl.textContent = text;

        const topRound = document.getElementById('round-display');
        if (topRound) topRound.textContent = text;
    },

    /**
     * Open melds
     */
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
                        t.className = 'meld-tile';
                        this.applyTileImage(t, tile, 0);
                    } else {
                        t.className = 'tile-back-3d';
                    }
                    group.appendChild(t);
                });
                group.style.opacity = '1';
                el.appendChild(group);
            });
        }
    },

    showGame() {
        const ls = document.getElementById('loading-screen');
        const gs = document.getElementById('game-screen');
        if (ls && !ls.classList.contains('fade-out')) {
            ls.classList.add('fade-out');
            setTimeout(() => ls.classList.add('hidden'), 600);
        }
        if (gs) gs.classList.remove('hidden');
    },

    setLoadingMsg(msg) {
        const el = document.getElementById('loading-msg');
        if (el) el.textContent = msg;
    },

    showMsg(msg) {
        const el = document.getElementById('game-message');
        if (el) el.textContent = msg;
    }
};
