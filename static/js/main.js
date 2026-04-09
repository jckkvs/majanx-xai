// static/js/main.js

let ws;
const playerId = "p1";
let mySeat = 0;

function log(msg) {
  const logDiv = document.getElementById('debug-log');
  const d = new Date();
  logDiv.innerHTML += `[${d.toLocaleTimeString()}] ${msg}<br>`;
  logDiv.scrollTop = logDiv.scrollHeight;
}

function connect() {
  ws = new WebSocket("ws://127.0.0.1:8000/ws_ui");
  
  ws.onopen = () => {
    log("WebSocket connected.");
    ws.send(JSON.stringify({ type: "join", player_id: playerId, seat: 0 }));
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "state_update") {
      updateUI(data);
    } else if (data.type === "error") {
      log(`Error: ${data.message}`);
    }
  };
  
  ws.onclose = () => {
    log("WebSocket disconnected. Reconnecting in 3s...");
    setTimeout(connect, 3000);
  };
}

function getSuitClass(tileStr) {
  if (tileStr.includes('m')) return 'tile-m';
  if (tileStr.includes('p')) return 'tile-p';
  if (tileStr.includes('s')) return 'tile-s';
  return 'tile-z';
}

function renderTiles(containerId, tilesArray, isHand = false) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  
  tilesArray.forEach(t => {
    const div = document.createElement('div');
    div.className = `tile ${getSuitClass(t)}`;
    div.innerText = t;
    
    if (isHand) {
      div.onclick = () => {
        // Send discard action
        ws.send(JSON.stringify({
          type: "action_request",
          player_id: playerId,
          action: "discard",
          tile: t,
          timestamp: Date.now()
        }));
      };
    }
    
    container.appendChild(div);
  });
}

function updateUI(state) {
  document.getElementById('turn-info').innerText = `State: ${state.game_state} | Turn: ${state.turn}`;
  document.getElementById('score-display').innerText = state.scores.join(" / ");
  
  // Render Hands
  if (state.hand) renderTiles('hand-area', state.hand, true);
  
  // Render Discards
  if (state.discards) {
    state.discards.forEach((dlist, idx) => {
      renderTiles(`discards-p${idx}`, dlist);
    });
  }
  
  // Update Buttons
  const buttons = ['reach', 'pon', 'chi', 'kan', 'ron', 'pass'];
  buttons.forEach(b => {
    const btn = document.getElementById(`btn-${b}`);
    if (btn) btn.style.display = 'none';
  });
  
  if (state.available_actions) {
    state.available_actions.forEach(act => {
      if (act.type === 'reach') {
        const btn = document.getElementById('btn-reach');
        btn.style.display = 'inline-block';
        btn.disabled = false;
        btn.onclick = () => {
          ws.send(JSON.stringify({type: "action_request", action: "reach", player_id: playerId}));
        };
      } else if (act.type !== 'discard') {
        const btn = document.getElementById(`btn-${act.type}`);
        if (btn) {
           btn.style.display = 'inline-block';
           btn.onclick = () => {
             ws.send(JSON.stringify({type: "action_request", action: act.type, player_id: playerId}));
           };
        }
      }
    });

    // If there are actions other than discard, show pass
    if (state.available_actions.some(a => a.type !== 'discard')) {
      const btn = document.getElementById('btn-pass');
      if (btn) {
         btn.style.display = 'inline-block';
         btn.onclick = () => {
           ws.send(JSON.stringify({type: "action_request", action: "pass", player_id: playerId}));
         };
      }
    }
  }
}

// Init
window.onload = () => {
  connect();
};
