/**
 * MajanX-XAI v2 — Renderer
 */

const Renderer = {
    applyTileImage(el, tileId, orientation = 0) {
        const url = TileMap.getImageUrl(tileId, orientation);
        if (url) {
            el.style.backgroundImage = `url('${url}')`;
            el.classList.add('tile-base');
            if (TileMap.isRedDora(tileId)) el.classList.add('red-dora');
        }
    },

    renderHand(containerId, hand, options = {}) {
        const el = document.getElementById(containerId);
        if (!el) return;
        el.innerHTML = '';

        const tiles = [...hand];
        let tsumo = null;
        if (tiles.length % 3 === 2) tsumo = tiles.pop();

        tiles.sort((a, b) => TileMap.sortKey(a) - TileMap.sortKey(b));

        tiles.forEach((t, i) => {
            const d = this._createTile(t, i, options);
            el.appendChild(d);
        });

        if (tsumo) {
            const spacer = document.createElement('div');
            spacer.style.width = '16px';
            el.appendChild(spacer);
            const d = this._createTile(tsumo, tiles.length, options);
            el.appendChild(d);
        }
    },

    _createTile(tile, idx, options) {
        const d = document.createElement('div');
        d.className = 'hand-tile';
        this.applyTileImage(d, tile, 0);
        d.onclick = () => options.onTileClick?.(idx, tile, d);
        return d;
    },

    renderRivers(discards) {
        // Player orientations: 0:self(0), 1:right(3), 2:top(1), 3:left(4)
        const orientations = [0, 3, 1, 4];
        
        for (let p = 0; p < 4; p++) {
            const el = document.getElementById(`river-${p}`);
            if (!el) continue;
            el.innerHTML = '';
            
            const arr = discards[p] || [];
            arr.forEach((t, i) => {
                const d = document.createElement('div');
                d.className = 'river-tile';
                this.applyTileImage(d, t, orientations[p]);
                if (p === 0 && i === arr.length - 1) d.classList.add('last-discard');
                el.appendChild(d);
            });
        }
    },

    renderOpponents(handCounts) {
        for (let p = 1; p <= 3; p++) {
            const el = document.getElementById(`hand-${p}`);
            if (!el) continue;
            el.innerHTML = '';
            const count = handCounts[p] || 13;
            for (let i = 0; i < count; i++) {
                const b = document.createElement('div');
                b.className = 'tile-back-3d';
                el.appendChild(b);
            }
        }
    },

    setTurn(cp) {
        for (let i = 0; i < 4; i++) {
            const el = document.getElementById(`score-${i}`);
            el?.classList.toggle('active', i === cp);
            const comp = document.getElementById(['compass-s','compass-e','compass-n','compass-w'][i]);
            comp?.classList.toggle('active', i === cp);
        }
    },

    showGame() {
        document.getElementById('loading-screen')?.classList.add('fade-out');
        document.getElementById('game-stage').classList.add('visible');
    }
};
