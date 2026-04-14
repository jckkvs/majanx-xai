/**
 * MajanX-XAI v2 — Game Client
 */

class MahjongGame {
    constructor() {
        this.ws = null;
        this.playerId = 0;
        this.init();
    }

    init() {
        this.connect();
        this.bindEvents();
        this.handleResize();
        window.addEventListener('resize', () => this.handleResize());
    }

    handleResize() {
        const stage = document.getElementById('game-stage');
        if (!stage) return;
        
        const scale = Math.min(
            window.innerWidth / 1280,
            window.innerHeight / 720
        );
        
        stage.style.transform = `scale(${scale})`;
    }

    connect() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${proto}//${location.host}/ws_ui?new_game=true`);
        this.ws.onopen = () => this.ws.send(JSON.stringify({ type: 'join' }));
        this.ws.onmessage = (e) => this.onMessage(JSON.parse(e.data));
    }

    onMessage(d) {
        if (d.type === 'state_update') {
            this.updateUI(d);
        }
    }

    updateUI(d) {
        Renderer.showGame();
        Renderer.renderHand('hand-0', d.hand || [], {
            onTileClick: (idx, tile) => this.discard(tile)
        });
        Renderer.renderOpponents(d.hand_counts || []);
        Renderer.renderRivers(d.discards || []);
        Renderer.setTurn(d.current_player);
        
        document.getElementById('remain-count').textContent = 136 - 14 - 52 - (d.turn || 0);
        document.getElementById('shield-remain').textContent = 136 - 14 - 52 - (d.turn || 0);
        
        const btn = document.getElementById('btn-tsumo');
        if (btn) btn.disabled = (d.current_player !== this.playerId || d.game_state !== 'DISCARDING');
    }

    discard(tile) {
        this.ws.send(JSON.stringify({ type: 'action_request', action: 'discard', tile }));
    }

    bindEvents() {
        // Additional UI bindings here
    }
}

document.addEventListener('DOMContentLoaded', () => new MahjongGame());
