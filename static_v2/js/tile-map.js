/**
 * MajanX-XAI v2 — Tile Map
 * Backend tile ID → individual image file mapping
 *
 * Image naming convention (design/majang-hai/):
 *   萬子: p_ms{1-9}_{orientation}.gif
 *   筒子: p_ps{1-9}_{orientation}.gif
 *   索子: p_ss{1-9}_{orientation}.gif
 *   字牌: p_ji_{letter}_{orientation}.gif
 *     e=東, s=南, w=西, n=北, h=發, c=中
 *   白:   p_no_{orientation}.gif
 *
 * Orientation: 0=正面, 1=上下反転, 3=右向き, 4=左向き
 */

const TileMap = {
    /** Suit code → image prefix */
    SUIT_PREFIX: { m: 'ms', p: 'ps', s: 'ss' },

    /** Honor tile ID → image file key */
    HONOR_FILE: {
        '1z': 'ji_e',  // 東
        '2z': 'ji_s',  // 南
        '3z': 'ji_w',  // 西
        '4z': 'ji_n',  // 北
        '5z': 'no',    // 白
        '6z': 'ji_h',  // 發
        '7z': 'ji_c',  // 中
        // Legacy format support
        'E':  'ji_e',
        'S':  'ji_s',
        'W':  'ji_w',
        'N':  'ji_n',
        'Wh': 'no',
        'P':  'no',
        'Gr': 'ji_h',
        'F':  'ji_h',
        'Rd': 'ji_c',
        'C':  'ji_c',
    },

    /**
     * Get image URL for a tile ID
     * @param {string} tileId - e.g. "1m", "7z", "5mr"
     * @param {number} orientation - 0=front, 1=flipped, 3=right, 4=left
     * @returns {string|null} image URL or null
     */
    getImageUrl(tileId, orientation = 0) {
        if (!tileId || tileId === '?') return null;

        // Check honor tiles first
        const honorKey = this.HONOR_FILE[tileId];
        if (honorKey) {
            return `/tiles/p_${honorKey}_${orientation}.gif`;
        }

        // Handle red dora suffix
        let id = tileId;
        let isRed = false;
        if (id.endsWith('r')) {
            isRed = true;
            id = id.slice(0, -1);
        }

        const num = parseInt(id[0]);
        const suit = id[1];

        if (isNaN(num) || !this.SUIT_PREFIX[suit]) return null;

        const prefix = this.SUIT_PREFIX[suit];

        // Red dora (0m/0p/0s) → use normal 5 image (no separate red image)
        const tileNum = (num === 0) ? 5 : num;

        return `/tiles/p_${prefix}${tileNum}_${orientation}.gif`;
    },

    /**
     * Check if a tile is red dora
     */
    isRedDora(tileId) {
        if (!tileId) return false;
        return tileId.endsWith('r') || tileId.startsWith('0');
    },

    /**
     * Display name (Japanese) for a tile
     */
    displayName(tileId) {
        if (!tileId) return '?';

        const HONOR_NAMES = {
            '1z': '東', '2z': '南', '3z': '西', '4z': '北',
            '5z': '白', '6z': '發', '7z': '中',
            'E': '東', 'S': '南', 'W': '西', 'N': '北',
            'Wh': '白', 'P': '白', 'Gr': '發', 'F': '發',
            'Rd': '中', 'C': '中',
        };
        if (HONOR_NAMES[tileId]) return HONOR_NAMES[tileId];

        const NUM_KANJI = { 0: '五', 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八', 9: '九' };
        const SUIT_KANJI = { m: '萬', p: '筒', s: '索' };

        let id = tileId;
        if (id.endsWith('r')) id = id.slice(0, -1);
        const n = id[0];
        const s = id[1];

        if (NUM_KANJI[n] && SUIT_KANJI[s]) {
            return NUM_KANJI[n] + SUIT_KANJI[s];
        }
        return tileId;
    },

    /**
     * Sort key for hand ordering
     */
    sortKey(tileId) {
        if (!tileId) return 999;

        // Honor tiles
        const honorOrder = {
            '1z': 400, '2z': 401, '3z': 402, '4z': 403,
            '5z': 404, '6z': 405, '7z': 406,
            'E': 400, 'S': 401, 'W': 402, 'N': 403,
            'Wh': 404, 'P': 404, 'Gr': 405, 'F': 405,
            'Rd': 406, 'C': 406,
        };
        if (honorOrder[tileId] !== undefined) return honorOrder[tileId];

        let id = tileId;
        if (id.endsWith('r')) id = id.slice(0, -1);
        const num = parseInt(id[0]);
        const suit = id[1];

        const suitOrder = { m: 0, p: 100, s: 200 };
        const base = suitOrder[suit] ?? 300;
        const n = (num === 0) ? 5 : num;

        return base + n * 10 + (this.isRedDora(tileId) ? 1 : 0);
    }
};
