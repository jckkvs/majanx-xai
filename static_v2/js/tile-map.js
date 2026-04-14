/**
 * MajanX-XAI v2 — Tile Map
 * Orientation: 0=front, 1=flipped (toimen), 3=right (shimocha), 4=left (kamicha)
 */

const TileMap = {
    SUIT_PREFIX: { m: 'ms', p: 'ps', s: 'ss' },

    HONOR_FILE: {
        '1z': 'ji_e', '2z': 'ji_s', '3z': 'ji_w', '4z': 'ji_n',
        '5z': 'no', '6z': 'ji_h', '7z': 'ji_c'
    },

    getImageUrl(tileId, orientation = 0) {
        if (!tileId || tileId === '?') return null;

        let key = this.HONOR_FILE[tileId];
        if (!key) {
            const num = parseInt(tileId[0]);
            const suit = tileId[1];
            key = this.SUIT_PREFIX[suit] + (num === 0 ? 5 : num);
        }

        // Return path with orientation suffix
        return `/tiles/p_${key}_${orientation}.gif`;
    },

    isRedDora(tileId) {
        return tileId && (tileId[0] === '0' || tileId.endsWith('r'));
    },

    sortKey(tileId) {
        if (!tileId) return 999;
        const honorBase = { '1z': 401, '2z': 402, '3z': 403, '4z': 404, '5z': 405, '6z': 406, '7z': 407 };
        if (honorBase[tileId]) return honorBase[tileId];

        const suitBase = { m: 100, p: 200, s: 300 };
        const num = parseInt(tileId[0]);
        const s = tileId[1];
        return (suitBase[s] || 400) + (num === 0 ? 5 : num);
    }
};
