/**
 * 牌レンダラー: CSS描画による牌の生成
 * Implements: F-006 | 牌レンダリング
 */

const TileRenderer = {
    /**
     * 牌IDの文字表現マップ
     * 字牌: 1z=東, 2z=南, 3z=西, 4z=北, 5z=白, 6z=發, 7z=中
     */
    WIND_CHARS: {
        1: '東', 2: '南', 3: '西', 4: '北',
        5: '白', 6: '發', 7: '中'
    },

    WIND_CLASSES: {
        1: 'tile-wind-east',
        2: 'tile-wind-south',
        3: 'tile-wind-west',
        4: 'tile-wind-north',
        5: 'tile-dragon-white',
        6: 'tile-dragon-green',
        7: 'tile-dragon-red'
    },

    SUIT_NAMES: {
        m: 'man', p: 'pin', s: 'sou', z: 'wind'
    },

    /**
     * 牌IDをパース
     * @param {string} id - 牌ID (例: '1m', '5pr', '7z')
     * @returns {{number: number, suit: string, isRed: boolean}}
     */
    parseTileId(id) {
        if (!id || id === '?') return null;
        const isRed = id.endsWith('r') || id.includes('0');
        const cleanId = id.replace('r', '').replace('0', '5');
        const number = parseInt(cleanId[0]);
        const suit = cleanId[1];
        return { number, suit, isRed };
    },

    /**
     * 牌の DOM 要素を生成
     * @param {string} tileId - 牌ID
     * @param {object} options - オプション
     * @returns {HTMLElement}
     */
    createTileElement(tileId, options = {}) {
        const {
            small = false,
            clickable = false,
            back = false,
            tsumo = false,
            riichi = false,
            rotated = false,
            animate = false,
        } = options;

        const el = document.createElement('div');
        el.classList.add('tile');

        if (back || !tileId || tileId === '?') {
            el.classList.add('tile-back');
            if (small) el.classList.add('tile-sm');
            return el;
        }

        const parsed = this.parseTileId(tileId);
        if (!parsed) {
            el.classList.add('tile-back');
            return el;
        }

        const { number, suit, isRed } = parsed;
        el.dataset.suit = suit;
        el.dataset.tileId = tileId;

        if (suit === 'm') {
            el.classList.add('manzu');
            el.textContent = ['一','二','三','四','五','六','七','八','九'][number-1];
        } else if (suit === 'p') {
            el.classList.add('pinzu');
            el.appendChild(this._createPinzuPattern(number));
        } else if (suit === 's') {
            el.classList.add('souzu');
            el.appendChild(this._createSouzuPattern(number));
        } else if (suit === 'z') {
            el.classList.add('honor');
            el.textContent = this.WIND_CHARS[number] || '?';
            if (number <= 4) el.classList.add('wind');
            else if (number === 5) el.classList.add('white');
            else if (number === 6) el.classList.add('dragon-green');
            else if (number === 7) el.classList.add('dragon-red');
        }

        if (isRed) el.classList.add('red-dora');
        if (small) el.classList.add('tile-sm');
        if (clickable) el.classList.add('tile-clickable');
        if (tsumo) el.classList.add('tile-tsumo');
        if (riichi) el.classList.add('tile-riichi');
        if (rotated) el.classList.add('tile-rotated');
        if (animate) el.classList.add('animate-appear');

        return el;
    },

    /**
     * 筒子の丸パターン生成
     */
    _createPinzuPattern(num) {
        const container = document.createElement('div');
        container.className = 'pattern';
        
        const patterns = {
            1: [[1]],
            2: [[1,0],[0,1]],
            3: [[1,0,0],[0,1,0],[0,0,1]],
            4: [[1,0],[0,1],[1,0],[0,1]],
            5: [[1,0,1],[0,1,0],[1,0,1]],
            6: [[1,0,1],[0,1,0],[1,0,1],[0,1,0]],
            7: [[1,0,1],[0,1,0],[1,0,1],[0,1,0],[1,0,1]],
            8: [[1,0,1],[0,1,0],[1,0,1],[0,1,0],[1,0,1],[0,1,0]],
            9: [[1,1,1],[1,1,1],[1,1,1]]
        };

        const pattern = patterns[num] || [[1]];
        container.style.gridTemplateColumns = `repeat(${pattern[0].length}, 1fr)`;
        
        pattern.forEach(row => {
            row.forEach(val => {
                if (val) {
                    const dot = document.createElement('div');
                    dot.className = 'dot';
                    if ((num === 5 && row.length === 3 && row[1] === 1) || num === 1) {
                        dot.classList.add('red');
                    } else {
                        dot.classList.add('blue');
                    }
                    container.appendChild(dot);
                } else {
                    const empty = document.createElement('div');
                    container.appendChild(empty);
                }
            });
        });
        return container;
    },

    /**
     * 索子の竹パターン生成
     */
    _createSouzuPattern(num) {
        const container = document.createElement('div');
        container.className = 'bamboo';
        
        if (num === 1) {
            container.textContent = '🐦';
            container.style.fontSize = '32px';
        } else {
            for (let i = 0; i < num; i++) {
                const stick = document.createElement('div');
                stick.className = 'stick';
                container.appendChild(stick);
            }
        }
        return container;
    },

    /**
     * 牌リストを DOM に描画
     * @param {HTMLElement} container - コンテナ要素
     * @param {string[]} tileIds - 牌IDリスト
     * @param {object} options - オプション
     */
    renderTiles(container, tileIds, options = {}) {
        container.innerHTML = '';
        if (!tileIds) return;

        tileIds.forEach((id, index) => {
            const tileOptions = { ...options };
            // 最後の牌がツモ牌（手牌14枚目）
            if (options.markTsumo && index === tileIds.length - 1 && tileIds.length % 3 === 2) {
                tileOptions.tsumo = true;
            }
            const el = this.createTileElement(id, tileOptions);
            container.appendChild(el);
        });
    },

    /**
     * 副露を描画
     * @param {HTMLElement} container
     * @param {object[]} melds
     */
    renderMelds(container, melds) {
        container.innerHTML = '';
        if (!melds || melds.length === 0) return;

        melds.forEach(meld => {
            const group = document.createElement('div');
            group.classList.add('meld-group');

            meld.tiles.forEach((id, idx) => {
                const isCalledTile = idx === 0; // 鳴いた牌を横向きに
                const el = this.createTileElement(id, {
                    small: true,
                    rotated: isCalledTile && meld.type !== 'ankan',
                });
                group.appendChild(el);
            });

            container.appendChild(group);
        });
    }
};
