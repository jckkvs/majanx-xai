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
        const isRed = id.endsWith('r');
        const cleanId = isRed ? id.slice(0, -1) : id;
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
        const suitName = this.SUIT_NAMES[suit];

        el.classList.add(`tile-${suitName}`);
        el.dataset.tileId = tileId;

        if (isRed) el.classList.add('tile-red');
        if (small) el.classList.add('tile-sm');
        if (clickable) el.classList.add('tile-clickable');
        if (tsumo) el.classList.add('tile-tsumo');
        if (riichi) el.classList.add('tile-riichi');
        if (rotated) el.classList.add('tile-rotated');
        if (animate) el.classList.add('animate-appear');

        // コンテンツ
        const content = document.createElement('div');
        content.classList.add('tile-content');

        if (suit === 'z') {
            // 字牌
            const numEl = document.createElement('span');
            numEl.classList.add('tile-number');
            numEl.textContent = this.WIND_CHARS[number];
            content.appendChild(numEl);
            el.classList.add(this.WIND_CLASSES[number]);
        } else {
            // 数牌
            const numEl = document.createElement('span');
            numEl.classList.add('tile-number');
            numEl.textContent = number;
            content.appendChild(numEl);

            const suitEl = document.createElement('span');
            suitEl.classList.add('tile-suit');
            content.appendChild(suitEl);
        }

        el.appendChild(content);
        return el;
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
