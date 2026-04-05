/**
 * 牌レンダラー: Unicode絵文字ベースのリアル牌描画
 * Implements: F-006 | 牌レンダリング (Unicode方式)
 */

const TileRenderer = {

    /**
     * 牌ID -> Unicode麻雀牌文字マップ
     * 萬子(m), 筒子(p), 索子(s), 字牌(z)
     */
    TILE_UNICODE: {
        // 萬子
        '1m': '🀇', '2m': '🀈', '3m': '🀉', '4m': '🀊', '5m': '🀋',
        '6m': '🀌', '7m': '🀍', '8m': '🀎', '9m': '🀏',
        // 赤ドラ萬子
        '5mr': '🀋', '0m': '🀋',
        // 筒子
        '1p': '🀙', '2p': '🀚', '3p': '🀛', '4p': '🀜', '5p': '🀝',
        '6p': '🀞', '7p': '🀟', '8p': '🀠', '9p': '🀡',
        // 赤ドラ筒子
        '5pr': '🀝', '0p': '🀝',
        // 索子
        '1s': '🀐', '2s': '🀑', '3s': '🀒', '4s': '🀓', '5s': '🀔',
        '6s': '🀕', '7s': '🀖', '8s': '🀗', '9s': '🀘',
        // 赤ドラ索子
        '5sr': '🀔', '0s': '🀔',
        // 字牌: 1z=東 2z=南 3z=西 4z=北 5z=白 6z=發 7z=中
        '1z': '🀀', '2z': '🀁', '3z': '🀂', '4z': '🀃',
        '5z': '🀆', '6z': '🀅', '7z': '🀄',
    },

    /** 赤ドラ判定 */
    isRedDora(id) {
        return id && (id.endsWith('r') || id.startsWith('0'));
    },

    /** 牌IDをパース */
    parseTileId(id) {
        if (!id || id === '?') return null;
        const isRed = this.isRedDora(id);
        // normalize: 0m -> 5m
        const cleanId = id.replace('r', '').replace(/^0([mps])$/, '5$1');
        const number = parseInt(cleanId[0]);
        const suit = cleanId[1];
        return { number, suit, isRed, cleanId };
    },

    /**
     * 牌の DOM 要素を生成（Unicode文字ベース）
     */
    createTileElement(tileId, options = {}) {
        const {
            small = false,
            clickable = false,
            back = false,
            tsumo = false,
            riichi = false,
            rotated = false,
        } = options;

        const el = document.createElement('div');
        el.classList.add('tile');

        // 裏向き
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

        const { suit, isRed, cleanId } = parsed;
        el.dataset.tileId = tileId;
        el.dataset.suit = suit;

        // Unicode文字を設定
        const unicode = this.TILE_UNICODE[tileId] || this.TILE_UNICODE[cleanId];
        if (unicode) {
            el.textContent = unicode;
            el.classList.add('tile-unicode');
        } else {
            // フォールバック: テキスト描画
            el.classList.add('tile-text-fallback');
            el.textContent = tileId;
        }

        // 赤ドラスタイル
        if (isRed) el.classList.add('red-dora');

        // サイズ・状態クラス
        if (small) el.classList.add('tile-sm');
        if (clickable) el.classList.add('tile-clickable');
        if (tsumo) el.classList.add('tile-tsumo');
        if (riichi) el.classList.add('tile-riichi');
        if (rotated) el.classList.add('tile-rotated');

        return el;
    },

    /**
     * 牌リストを DOM に描画
     */
    renderTiles(container, tileIds, options = {}) {
        container.innerHTML = '';
        if (!tileIds) return;

        tileIds.forEach((id, index) => {
            const tileOptions = { ...options };
            if (options.markTsumo && index === tileIds.length - 1 && tileIds.length % 3 === 2) {
                tileOptions.tsumo = true;
            }
            const el = this.createTileElement(id, tileOptions);
            container.appendChild(el);
        });
    },

    /**
     * 副露を描画
     */
    renderMelds(container, melds) {
        container.innerHTML = '';
        if (!melds || melds.length === 0) return;

        melds.forEach(meld => {
            const group = document.createElement('div');
            group.classList.add('meld-group');

            meld.tiles.forEach((id, idx) => {
                const isCalledTile = idx === 0;
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
