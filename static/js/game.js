/**
 * MAJANX-XAI Game Client
 * 麻雀ソウル風UIの実装
 */

class MahjongGame {
    constructor() {
        this.ws = null;
        this.gameState = null;
        this.selectedTile = null;
        this.playerId = 0; // 自分は常に0（下部）
        this.tiles = [];
        this.river = [];
        this.doraIndicators = [];
        
        this.init();
    }

    init() {
        this.connectWebSocket();
        this.bindEvents();
        this.hideLoadingScreen();
    }

    // WebSocket接続
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/game`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket接続確立');
            this.showGameScreen();
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleServerMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket接続切断');
            setTimeout(() => this.connectWebSocket(), 3000); // 3秒後に再接続
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocketエラー:', error);
        };
    }

    // サーバーからのメッセージ処理
    handleServerMessage(data) {
        console.log('受信:', data);
        
        switch(data.type) {
            case 'game_start':
                this.handleGameStart(data);
                break;
            case 'game_state':
                this.handleGameState(data);
                break;
            case 'tile_draw':
                this.handleTileDraw(data);
                break;
            case 'tile_discard':
                this.handleTileDiscard(data);
                break;
            case 'meld':
                this.handleMeld(data);
                break;
            case 'riichi':
                this.handleRiichi(data);
                break;
            case 'win':
                this.handleWin(data);
                break;
            case 'ryukyoku':
                this.handleRyukyoku(data);
                break;
            case 'action_request':
                this.handleActionRequest(data);
                break;
            case 'message':
                this.showMessage(data.text);
                break;
        }
    }

    // ゲーム開始
    handleGameStart(data) {
        this.gameState = data.state;
        this.updateScoreDisplay(data.scores);
        this.updateRoundDisplay(data.round);
        this.showMessage('ゲーム開始！');
    }

    // ゲーム状態更新
    handleGameState(data) {
        this.gameState = data.state;
        this.updateAllPlayers(data);
        this.updateRiver(data.river);
        this.updateDora(data.dora_indicators);
        this.updateActivePlayer(data.current_player);
        
        if (data.current_player === this.playerId) {
            this.enablePlayerActions();
        } else {
            this.disablePlayerActions();
        }
    }

    // 牌をツモ
    handleTileDraw(data) {
        const playerId = data.player_id;
        const tile = data.tile;
        
        if (playerId === this.playerId) {
            this.tiles.push(tile);
            this.renderHand();
            
            if (playerId === this.gameState.current_player) {
                this.showMessage('あなたの番です');
            }
        }
    }

    // 牌を打牌
    handleTileDiscard(data) {
        const playerId = data.player_id;
        const tile = data.tile;
        
        this.river.push({
            tile: tile,
            player_id: playerId
        });
        
        if (playerId === this.playerId) {
            const index = this.tiles.findIndex(t => t.id === tile.id);
            if (index !== -1) {
                this.tiles.splice(index, 1);
                this.renderHand();
            }
        }
        
        this.updateRiver(this.river);
    }

    // 鳴き
    handleMeld(data) {
        const playerId = data.player_id;
        const meld = data.meld;
        
        this.showMessage(`${this.getPlayerName(playerId)}が${this.getMeldName(meld.type)}!`);
        
        // 鳴いた牌の処理
        if (playerId === this.playerId) {
            // 自分の手牌から鳴きに使用した牌を削除
            meld.tiles.forEach(tileId => {
                const index = this.tiles.findIndex(t => t.id === tileId);
                if (index !== -1) {
                    this.tiles.splice(index, 1);
                }
            });
            this.renderHand();
        }
        
        // 鳴き表示エリアに追加
        this.renderMeld(playerId, meld);
    }

    // リーチ
    handleRiichi(data) {
        const playerId = data.player_id;
        this.showMessage(`${this.getPlayerName(playerId)}がリーチ!`);
        
        // リーチ棒の表示
        this.showRiichiStick(playerId);
    }

    // 和了
    handleWin(data) {
        const playerId = data.player_id;
        const winInfo = data.win_info;
        
        this.showWinModal(playerId, winInfo);
        this.showMessage(`${this.getPlayerName(playerId)}の和了！`);
    }

    // 流局
    handleRyukyoku(data) {
        const reason = data.reason;
        this.showMessage(`流局 (${reason})`);
        
        // 流局詳細表示
        setTimeout(() => {
            this.showRyukyokuDetails(data);
        }, 1000);
    }

    // アクション要求（ポン・チー・カン・ロンなど）
    handleActionRequest(data) {
        const actions = data.actions;
        this.showActionButtons(actions);
    }

    // 全プレイヤーの更新
    updateAllPlayers(data) {
        // 他のプレイヤーの手牌は伏せたまま
        for (let i = 0; i < 4; i++) {
            if (i !== this.playerId) {
                this.updateOpponentHand(i, data.hands[i].length);
            }
        }
        
        // 自分の手牌
        if (data.hands[this.playerId]) {
            this.tiles = data.hands[this.playerId];
            this.renderHand();
        }
    }

    // 対戦相手の手牌更新（枚数のみ）
    updateOpponentHand(playerId, tileCount) {
        const handElement = document.getElementById(`hand-${playerId}`);
        handElement.innerHTML = '';
        
        // 伏せ牌を表示
        for (let i = 0; i < tileCount; i++) {
            const tile = document.createElement('div');
            tile.className = 'tile back';
            tile.textContent = '🀄';
            handElement.appendChild(tile);
        }
    }

    // 自分の手牌レンダリング
    renderHand() {
        const handElement = document.getElementById(`hand-${this.playerId}`);
        handElement.innerHTML = '';
        
        // 手牌をソート
        this.sortTiles();
        
        this.tiles.forEach((tile, index) => {
            const tileElement = this.createTileElement(tile, index);
            handElement.appendChild(tileElement);
        });
    }

    // 牌のソート
    sortTiles() {
        const tileOrder = {
            'm': 1, 'p': 2, 's': 3, 'z': 4
        };
        
        this.tiles.sort((a, b) => {
            const suitA = tileOrder[a.suit] || 5;
            const suitB = tileOrder[b.suit] || 5;
            
            if (suitA !== suitB) {
                return suitA - suitB;
            }
            
            return a.number - b.number;
        });
    }

    // 牌要素の作成
    createTileElement(tile, index) {
        const tileElement = document.createElement('div');
        tileElement.className = `tile ${this.getTileClass(tile)}`;
        tileElement.textContent = this.getTileDisplay(tile);
        tileElement.dataset.index = index;
        
        // クリックイベント
        tileElement.addEventListener('click', () => this.handleTileClick(index, tile));
        
        return tileElement;
    }

    // 牌のクラス取得
    getTileClass(tile) {
        switch(tile.suit) {
            case 'm': return 'manzu';
            case 'p': return 'pinzu';
            case 's': return 'souzu';
            case 'z': return 'jihai';
            default: return '';
        }
    }

    // 牌の表示文字取得
    getTileDisplay(tile) {
        if (tile.suit === 'z') {
            const jihaiMap = {
                1: '東', 2: '南', 3: '西', 4: '北',
                5: '白', 6: '發', 7: '中'
            };
            return jihaiMap[tile.number] || '';
        }
        
        const suitMap = {
            'm': '萬',
            'p': '筒',
            's': '索'
        };
        
        const numMap = {
            1: '一', 2: '二', 3: '三', 4: '四',
            5: '五', 6: '六', 7: '七', 8: '八', 9: '九'
        };
        
        return numMap[tile.number] + suitMap[tile.suit];
    }

    // 牌クリック処理
    handleTileClick(index, tile) {
        if (this.gameState.current_player !== this.playerId) {
            return; // 自分の番でない場合は何もしない
        }
        
        // 選択状態の切り替え
        if (this.selectedTile === index) {
            this.deselectTile();
        } else {
            this.selectTile(index);
        }
    }

    // 牌選択
    selectTile(index) {
        this.deselectTile();
        this.selectedTile = index;
        
        const handElement = document.getElementById(`hand-${this.playerId}`);
        const tiles = handElement.querySelectorAll('.tile');
        tiles[index].classList.add('selected');
    }

    // 牌選択解除
    deselectTile() {
        if (this.selectedTile === null) return;
        
        const handElement = document.getElementById(`hand-${this.playerId}`);
        const tiles = handElement.querySelectorAll('.tile');
        tiles.forEach(tile => tile.classList.remove('selected'));
        
        this.selectedTile = null;
    }

    // 河の更新
    updateRiver(river) {
        const riverElement = document.getElementById('river');
        riverElement.innerHTML = '';
        
        river.forEach((discard, index) => {
            const tileElement = document.createElement('div');
            tileElement.className = `tile ${this.getTileClass(discard.tile)} discard-animation`;
            tileElement.textContent = this.getTileDisplay(discard.tile);
            tileElement.style.animationDelay = `${index * 0.05}s`;
            riverElement.appendChild(tileElement);
        });
    }

    // ドラ表示更新
    updateDora(doraIndicators) {
        const doraElement = document.getElementById('dora-tiles');
        doraElement.innerHTML = '';
        
        doraIndicators.forEach(tile => {
            const tileElement = document.createElement('div');
            tileElement.className = `tile dora ${this.getTileClass(tile)}`;
            tileElement.textContent = this.getTileDisplay(tile);
            doraElement.appendChild(tileElement);
        });
    }

    // アクティブプレイヤー更新
    updateActivePlayer(playerId) {
        document.querySelectorAll('.player-area').forEach((el, index) => {
            if (index === playerId) {
                el.classList.add('active');
            } else {
                el.classList.remove('active');
            }
        });
        
        document.querySelectorAll('.player-score').forEach((el, index) => {
            if (index === playerId) {
                el.classList.add('active');
            } else {
                el.classList.remove('active');
            }
        });
    }

    // スコア表示更新
    updateScoreDisplay(scores) {
        scores.forEach((score, index) => {
            const element = document.getElementById(`score-val-${index}`);
            if (element) {
                element.textContent = score;
            }
        });
    }

    // 局表示更新
    updateRoundDisplay(round) {
        const roundElement = document.getElementById('round-display');
        const honbaElement = document.getElementById('honba-display');
        
        const roundMap = {
            'east': '東',
            'south': '南',
            'west': '西',
            'north': '北'
        };
        
        roundElement.textContent = `${roundMap[round.wind]}${round.number}局`;
        honbaElement.textContent = `${round.honba}本場`;
    }

    // プレイヤー名取得
    getPlayerName(playerId) {
        const names = ['自分', '下家', '対面', '上家'];
        return names[playerId] || `Player ${playerId}`;
    }

    // 鳴き名取得
    getMeldName(meldType) {
        const names = {
            'chi': 'チー',
            'pon': 'ポン',
            'kan': 'カン'
        };
        return names[meldType] || meldType;
    }

    // 鳴きレンダリング
    renderMeld(playerId, meld) {
        const poolElement = document.getElementById(`pool-${playerId}`);
        
        meld.tiles.forEach(tile => {
            const tileElement = document.createElement('div');
            tileElement.className = `tile ${this.getTileClass(tile)}`;
            tileElement.textContent = this.getTileDisplay(tile);
            poolElement.appendChild(tileElement);
        });
    }

    // リーチ棒表示
    showRiichiStick(playerId) {
        const playerArea = document.getElementById(`player-${playerId}`);
        const stick = document.createElement('div');
        stick.className = 'riichi-stick';
        playerArea.appendChild(stick);
    }

    // アクションボタン表示
    showActionButtons(actions) {
        const container = document.getElementById('action-buttons');
        container.innerHTML = '';
        
        actions.forEach(action => {
            const button = document.createElement('button');
            button.className = `action-btn ${action.type}`;
            button.textContent = this.getActionLabel(action.type);
            button.onclick = () => this.sendAction(action);
            container.appendChild(button);
        });
    }

    // アクションラベル取得
    getActionLabel(actionType) {
        const labels = {
            'riichi': 'リーチ',
            'tsumo': 'ツモ',
            'ron': 'ロン',
            'chi': 'チー',
            'pon': 'ポン',
            'kan': 'カン',
            'none': 'スキップ',
            'flow': '流局'
        };
        return labels[actionType] || actionType;
    }

    // アクション送信
    sendAction(action) {
        this.ws.send(JSON.stringify({
            type: 'action',
            action: action.type,
            tile_index: this.selectedTile
        }));
        
        // ボタンを非表示
        document.getElementById('action-buttons').innerHTML = '';
        this.deselectTile();
    }

    // プレイヤーアクション有効化
    enablePlayerActions() {
        const controlBtns = document.querySelectorAll('.control-btn');
        controlBtns.forEach(btn => {
            if (btn.id === 'btn-riichi' || btn.id === 'btn-ron') {
                btn.disabled = false;
            } else {
                btn.disabled = false;
            }
        });
    }

    // プレイヤーアクション無効化
    disablePlayerActions() {
        const controlBtns = document.querySelectorAll('.control-btn');
        controlBtns.forEach(btn => {
            btn.disabled = true;
        });
    }

    // メッセージ表示
    showMessage(text) {
        const messageElement = document.getElementById('game-message');
        messageElement.textContent = text;
        
        // 3秒後に消去
        setTimeout(() => {
            if (messageElement.textContent === text) {
                messageElement.textContent = '';
            }
        }, 3000);
    }

    // 和了モーダル表示
    showWinModal(playerId, winInfo) {
        const modal = document.getElementById('win-modal');
        const title = document.getElementById('win-title');
        const details = document.getElementById('win-details');
        
        title.textContent = playerId === this.playerId ? '和了!' : '放銃!';
        
        let detailHTML = `
            <div><strong>プレイヤー:</strong> ${this.getPlayerName(playerId)}</div>
            <div><strong>手役:</strong> ${winInfo.yaku.join(', ')}</div>
            <div><strong>翻数:</strong> ${winInfo.han}翻</div>
            <div><strong>符:</strong> ${winInfo.fu}符</div>
            <div><strong>得点:</strong> ${winInfo.score}点</div>
        `;
        
        details.innerHTML = detailHTML;
        modal.classList.remove('hidden');
    }

    // 流局詳細表示
    showRyukyokuDetails(data) {
        // 実装は必要に応じて追加
        console.log('流局詳細:', data);
    }

    // イベントバインド
    bindEvents() {
        // コントロールパネルのボタン
        document.getElementById('btn-riichi').addEventListener('click', () => {
            this.sendAction({ type: 'riichi' });
        });
        
        document.getElementById('btn-tsumo').addEventListener('click', () => {
            if (this.selectedTile !== null) {
                this.sendAction({ type: 'discard', tile_index: this.selectedTile });
            }
        });
        
        document.getElementById('btn-ron').addEventListener('click', () => {
            this.sendAction({ type: 'ron' });
        });
        
        document.getElementById('btn-flow').addEventListener('click', () => {
            this.sendAction({ type: 'ryukyoku' });
        });
        
        document.getElementById('btn-menu').addEventListener('click', () => {
            this.showMenu();
        });
        
        // キーボードショートカット
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.deselectTile();
            } else if (e.key === 'Enter' && this.selectedTile !== null) {
                document.getElementById('btn-tsumo').click();
            }
        });
    }

    // メニュー表示
    showMenu() {
        const menuItems = [
            { label: 'ゲームを終了', action: () => this.endGame() },
            { label: '設定', action: () => this.showSettings() },
            { label: 'キャンセル', action: () => {} }
        ];
        
        // シンプルな確認ダイアログ
        if (confirm('ゲームを終了しますか？')) {
            this.endGame();
        }
    }

    // ゲーム終了
    endGame() {
        this.ws.send(JSON.stringify({ type: 'end_game' }));
        location.reload();
    }

    // 設定表示
    showSettings() {
        alert('設定機能は準備中です');
    }

    // ローディング画面非表示
    hideLoadingScreen() {
        setTimeout(() => {
            document.getElementById('loading-screen').classList.add('hidden');
        }, 1500);
    }

    // ゲーム画面表示
    showGameScreen() {
        document.getElementById('game-screen').classList.remove('hidden');
    }
}

// グローバル関数
function closeWinModal() {
    document.getElementById('win-modal').classList.add('hidden');
}

// ゲーム開始
let game;
document.addEventListener('DOMContentLoaded', () => {
    game = new MahjongGame();
});
