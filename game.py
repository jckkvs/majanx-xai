#!/usr/bin/env python3
"""
Majan MVP - 最小実行可能麻雀ゲームエンジン
使用方法: python game.py
アクセス: http://localhost:8000
"""

import asyncio
import random
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List, Optional
import json

# --- 定数 ---
TILE_MAP = {
    **{i: f"{i+1}m" for i in range(9)},
    **{i+9: f"{i+1}p" for i in range(9)},
    **{i+18: f"{i+1}s" for i in range(9)},
    **{i+27: h for i, h in enumerate(['E','S','W','N','P','F','C'])}
}

def parse_tile(val: int) -> str:
    base = val & 0x3F
    return TILE_MAP.get(base, "?")

# --- ゲーム状態 ---
class GameState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        tiles = list(range(136))
        random.shuffle(tiles)
        self.hands = [sorted(tiles[i*13:(i+1)*13]) for i in range(4)]
        self.wall = tiles[52:]
        self.discards = [[] for _ in range(4)]
        self.current_player = 0
        self.last_tile = None
        self.active = True

    def draw(self) -> Optional[int]:
        if not self.wall:
            return None
        tile = self.wall.pop()
        self.hands[self.current_player].append(tile)
        self.hands[self.current_player].sort()
        return tile

    def discard(self, player: int, tile: int) -> bool:
        if player != self.current_player:
            return False
        try:
            self.hands[player].remove(tile)
            self.discards[player].append(tile)
            self.last_tile = tile
            self.current_player = (player + 1) % 4
            return True
        except:
            return False

    def to_dict(self) -> dict:
        return {
            "hands": [[parse_tile(t) for t in h] for h in self.hands],
            "discards": [[parse_tile(t) for t in d] for d in self.discards],
            "current": self.current_player,
            "wall": len(self.wall),
            "last": parse_tile(self.last_tile) if self.last_tile else None
        }

game = GameState()

# --- WebSocket管理 ---
class Manager:
    def __init__(self):
        self.conns: List[WebSocket] = []
    
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.conns.append(ws)
    
    def disconnect(self, ws: WebSocket):
        if ws in self.conns:
            self.conns.remove(ws)
    
    async def broadcast(self, msg: dict):
        for c in self.conns:
            try:
                await c.send_json(msg)
            except:
                pass

mgr = Manager()

# --- ゲームループ ---
async def loop():
    while True:
        if not game.active:
            await asyncio.sleep(1)
            continue
        
        tile = game.draw()
        if tile is None:
            await mgr.broadcast({"type": "end", "reason": "wall_empty"})
            game.active = False
            continue
        
        await mgr.broadcast({"type": "update", "state": game.to_dict()})
        await asyncio.sleep(1.0)  # 簡易思考時間
        
        # 簡易自動打牌（ツモ切り）
        hand = game.hands[game.current_player]
        if hand:
            game.discard(game.current_player, hand[-1])
            await mgr.broadcast({
                "type": "discarded",
                "player": game.current_player,
                "tile": parse_tile(hand[-1])
            })

# --- FastAPI ---
app = FastAPI()

@app.on_event("startup")
async def startup():
    asyncio.create_task(loop())

@app.get("/")
async def index():
    return HTMLResponse(HTML)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await mgr.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "discard":
                # 人間プレイヤーの打牌処理（簡易）
                pass
    except WebSocketDisconnect:
        mgr.disconnect(ws)

HTML = """
<!DOCTYPE html>
<html><head><title>Majan MVP</title>
<style>
body{background:#1a472a;color:#fff;font-family:sans-serif;text-align:center}
#board{width:90vw;max-width:800px;height:70vh;margin:20px auto;background:#2d6b42;border-radius:10px;position:relative}
.player{position:absolute;padding:8px;background:rgba(0,0,0,0.3);border-radius:5px}
#p0{bottom:10px;left:50%;transform:translateX(-50%)}
#p1{left:10px;top:50%;transform:translateY(-50%)}
#p2{top:10px;left:50%;transform:translateX(-50%)}
#p3{right:10px;top:50%;transform:translateY(-50%)}
.tile{display:inline-block;width:28px;height:38px;background:#fff;color:#000;margin:2px;border-radius:3px;line-height:38px;cursor:pointer}
.tile:hover{transform:translateY(-3px)}
.tile.selected{border:2px solid gold;background:#ffe}
#info{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(0,0,0,0.6);padding:15px;border-radius:8px}
</style></head><body>
<h1>🀄 Majan MVP</h1>
<div id="board">
  <div id="info">Connecting...</div>
  <div id="p0" class="player">You</div>
  <div id="p1" class="player">P1</div>
  <div id="p2" class="player">P2</div>
  <div id="p3" class="player">P3</div>
</div>
<script>
const ws=new WebSocket(`ws://${location.host}/ws`);
ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.type==='update')render(d.state);};
function render(s){
  document.getElementById('info').innerHTML=`Wall:${s.wall}<br>Last:${s.last||'-'}`;
  for(let i=0;i<4;i++){
    const el=document.getElementById(`p${i}`);
    el.querySelectorAll('.tile').forEach(t=>t.remove());
    s.hands[i].forEach(tile=>{
      const t=document.createElement('div');
      t.className='tile'+(i===0?' interactive':'');
      t.textContent=tile;
      if(i===0)t.onclick=()=>ws.send(JSON.stringify({type:'discard',tile}));
      el.appendChild(t);
    });
  }
}
</script></body></html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
