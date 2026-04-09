// static/js/main.js

let ws;
const playerId = "p_human";
let gameStateRenderer;

class GameRenderer {
  constructor() {
    this.selectedTile = null;
    this.state = null;
  }

  // Unicode変換
  getTileUnicode(tileStr) {
    if (!tileStr) return '🀫';
    const map = {
      '1m':'🀇','2m':'🀈','3m':'🀉','4m':'🀊','5m':'🀋','6m':'🀌','7m':'🀍','8m':'🀎','9m':'🀏',
      '1p':'🀙','2p':'🀚','3p':'🀛','4p':'🀜','5p':'🀝','6p':'🀞','7p':'🀟','8p':'🀠','9p':'🀡',
      '1s':'🀐','2s':'🀑','3s':'🀒','4s':'🀓','5s':'🀔','6s':'🀕','7s':'🀖','8s':'🀗','9s':'🀘',
      'E':'🀀','S':'🀁','W':'🀂','N':'🀃','C':'🀄','F':'🀅','P':'🀆'
    };
    return map[tileStr] || tileStr;
  }

  update(newState) {
    this.state = newState;
    this.render();
  }

  renderOpponentHand(seatIdx, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    // 他家は手牌データがないため、13枚として描画 (親なら14枚等の制御が必要だが簡易化)
    const handSize = 13;
    container.innerHTML = '';
    for (let i = 0; i < handSize; i++) {
        const tileBack = document.createElement('div');
        tileBack.className = 'tile-back';
        container.appendChild(tileBack);
    }
  }

  renderDiscards(seatIdx, containerId) {
    const container = document.getElementById(containerId);
    if (!container || !this.state.discards) return;
    
    // current_player を基準に相対位置を計算するのが本来ですが、
    // ここでは idx=0 が bottom, idx=1 が right, idx=2 が top, idx=3 が left と固定します。
    const discards = this.state.discards[seatIdx] || [];
    
    container.innerHTML = '';
    discards.forEach(tileStr => {
      const tileEl = document.createElement('div');
      tileEl.className = 'tile discard-tile';
      // 簡易ツモ切り判定（データにあれば `.tsumogiri` を付ける）
      tileEl.textContent = this.getTileUnicode(tileStr);
      container.appendChild(tileEl);
    });
  }

  renderSelfHand() {
    const container = document.getElementById('player-hand');
    if (!container || !this.state.hand) return;

    container.innerHTML = '';
    this.state.hand.forEach(tile => {
      const tileEl = document.createElement('div');
      tileEl.className = 'tile interactive';
      tileEl.dataset.tile = tile;
      tileEl.textContent = this.getTileUnicode(tile);
      
      tileEl.onclick = () => this.selectTile(tileEl);
      container.appendChild(tileEl);
    });
  }

  selectTile(element) {
    document.querySelectorAll('.tile.selected').forEach(el => {
      el.classList.remove('selected');
    });
    
    element.classList.add('selected');
    this.selectedTile = element.dataset.tile;
    
    const btnDiscard = document.getElementById('btn-discard');
    if (btnDiscard && this.state.current_player === 0 && this.state.game_state === "DISCARDING") {
      btnDiscard.disabled = false;
    }
  }

  render() {
    if (!this.state) return;
    
    // 対局情報
    document.getElementById('turn-count').textContent = this.state.turn || 0;
    document.getElementById('dora-tile').textContent = this.getTileUnicode(this.state.dora_indicator);
    
    // 点数表示
    if (this.state.scores) {
       document.querySelector('.bottom-score .score').textContent = this.state.scores[0];
       document.querySelector('.right-score .score').textContent = this.state.scores[1];
       document.querySelector('.top-score .score').textContent = this.state.scores[2];
       document.querySelector('.left-score .score').textContent = this.state.scores[3];
    }
    
    // 手牌

    // AI双視点パネルの更新
    if (this.state.perspective_parallel && this.state.perspective_parallel.length >= 1) {
      document.getElementById('ai-panel').style.display = 'block';
      
      const p1 = this.state.perspective_parallel[0];
      document.querySelector('#perspective-a .ai-name').textContent = p1.source_ai;
      document.querySelector('#perspective-a .pai-badge').textContent = this.getTileUnicode(p1.recommended_action.pai);
      document.querySelector('#perspective-a .principle').textContent = p1.reasoning;
      
      const ulA = document.querySelector('#perspective-a .checklist');
      ulA.innerHTML = '';
      if (p1.checklist) {
          p1.checklist.forEach(item => {
              const li = document.createElement('li');
              li.textContent = item;
              ulA.appendChild(li);
          });
      }

      const p2 = this.state.perspective_parallel.length > 1 ? this.state.perspective_parallel[1] : null;
      if (p2) {
          document.getElementById('perspective-b').style.display = 'block';
          document.querySelector('#perspective-b .ai-name').textContent = p2.source_ai;
          document.querySelector('#perspective-b .pai-badge').textContent = this.getTileUnicode(p2.recommended_action.pai);
          document.querySelector('#perspective-b .principle').textContent = p2.reasoning;
          
          const ulB = document.querySelector('#perspective-b .checklist');
          ulB.innerHTML = '';
          if (p2.checklist) {
              p2.checklist.forEach(item => {
                  const li = document.createElement('li');
                  li.textContent = item;
                  ulB.appendChild(li);
              });
          }
      } else {
          document.getElementById('perspective-b').style.display = 'none';
      }
    } else {
      document.getElementById('ai-panel').style.display = 'none';
    }
    this.renderSelfHand();
    this.renderOpponentHand(1, 'opponent-right-hand');
    this.renderOpponentHand(2, 'opponent-top-hand');
    this.renderOpponentHand(3, 'opponent-left-hand');
    
    // 河
    this.renderDiscards(0, 'river-bottom');
    this.renderDiscards(1, 'river-right');
    this.renderDiscards(2, 'river-top');
    this.renderDiscards(3, 'river-left');
    
    // オペレーション・ボタンのクリア
    const buttons = ['btn-reach', 'btn-pon', 'btn-chi', 'btn-kan', 'btn-ron', 'btn-pass', 'btn-discard'];
    buttons.forEach(b => {
      const el = document.getElementById(b);
      if (el && b !== 'btn-discard') el.style.display = 'none';
      if (el && b === 'btn-discard') el.disabled = true;
    });

    if (this.state.available_actions) {
      this.state.available_actions.forEach(act => {
        if (act.type === 'discard') {
          // 打牌待ちであることを示すのみ
        } else {
          const btn = document.getElementById(`btn-${act.type}`);
          if (btn) {
             btn.style.display = 'inline-block';
             btn.disabled = false;
          }
        }
      });
    }
  }
}

// Global UI Callbacks
window.doDiscard = function() {
  if (!gameStateRenderer || !gameStateRenderer.selectedTile) return;
  ws.send(JSON.stringify({
    type: "action_request",
    player_id: playerId,
    action: "discard",
    tile: gameStateRenderer.selectedTile
  }));
};

window.callPass = function() {
  ws.send(JSON.stringify({
    type: "action_request",
    player_id: playerId,
    action: "pass"
  }));
};

// WebSocket Initialization
function connect() {
  ws = new WebSocket("ws://127.0.0.1:8000/ws_ui");
  
  ws.onopen = () => {
    console.log("WebSocket connected.");
    ws.send(JSON.stringify({ type: "join", player_id: playerId, seat: 0 }));
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "state_update") {
      if (!gameStateRenderer) {
          gameStateRenderer = new GameRenderer();
      }
      gameStateRenderer.update(data);
    }
  };
  
  ws.onclose = () => {
    console.log("WebSocket disconnected. Reconnecting in 3s...");
    setTimeout(connect, 3000);
  };
}

window.onload = connect;
