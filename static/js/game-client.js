/**
 * ゲームクライアント: WebSocket通信 + UI更新
 * Implements: F-007 | フロントエンド通信・UI制御
 * Phase 2: AI推奨ハイライト + アニメーション強化
 */

class GameClient {
    constructor() {
        this.ws = null;
        this.state = null;
        this.humanSeat = 0;
        this.selectedTile = null;
        this.isMyTurn = false;
        this.pendingActions = [];
        this.lastAiAnalysis = null;
        this.WIND_CHARS = { 0: '東', 1: '南', 2: '西', 3: '北' };
        this.SEAT_NAMES = ['あなた', 'CPU 2', 'CPU 3', 'CPU 4'];
        this.isReplay = false;
        this.replaySessionId = null;

        // 情報隠蔽(手出しのランダム化)用クライアントステート
        this.riverTiles = { 0: [], 1: [], 2: [], 3: [] };
        this.currentRoundStr = null;

        // Settings & Voice
        this.settings = {};
        this.synth = window.speechSynthesis;
        this.lastSpoken = "";
        
        // Settings websocket
        this._initSettings();
    }

    async _initSettings() {
        try {
            const res = await fetch('http://localhost:8001/api/settings');
            this.settings = await res.json();
        } catch (e) {
            console.error('[Settings] Load error:', e);
        }

        // 簡易的な WebSocket による設定更新購読（settings.html 側で更新時に送信）
        this.settingsWs = new WebSocket(`ws://localhost:8001/ws_ui`);
        window.settingsWs = this.settingsWs; // settings.html から送信するため
        this.settingsWs.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'settings_update') {
                this.settings = { ...this.settings, ...data.settings };
            }
        };
    }

    speak(text) {
        if (!this.settings.voice_enabled || !this.synth) return;
        if (this.lastSpoken === text) return;
        
        this.lastSpoken = text;
        const msg = new SpeechSynthesisUtterance(text);
        
        // 180 chars/min is roughly rate 1.2
        const rate = this.settings.voice_rate ? this.settings.voice_rate / 150 : 1.2;
        msg.rate = rate;
        msg.volume = this.settings.voice_volume !== undefined ? this.settings.voice_volume : 0.8;
        msg.lang = 'ja-JP';

        this.synth.cancel();
        this.synth.speak(msg);
    }

    /**
     * WebSocket接続
     */
    connect(replaySessionId = null) {
        let url = `ws://localhost:8001/ws_ui`;
        
        if (replaySessionId) {
            this.isReplay = true;
            this.replaySessionId = replaySessionId;
            url = `ws://localhost:8001/ws/replay/${replaySessionId}`;
        }

        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            console.log('[WS] Connected');
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.ws.onclose = () => {
            console.log('[WS] Disconnected');
        };

        this.ws.onerror = (err) => {
            console.error('[WS] Error:', err);
        };
    }

    /**
     * サーバーにメッセージ送信
     */
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    /**
     * サーバーメッセージのハンドリング
     */
    handleMessage(data) {
        console.log('[MSG]', data.type, data);

        switch (data.type) {
            case 'game_state':
            case 'state_sync':
                this.updateGameState(data.state || data.data);
                break;

            case 'tsumo':
                this.updateGameState(data.state);
                if (data.actor === this.humanSeat) {
                    this.showActionIndicator('ツモ');
                    // ツモ牌のアニメーション
                    this.animateTsumo();
                }
                break;

            case 'your_turn':
                this.updateGameState(data.state);
                this.isMyTurn = true;
                this.pendingActions = data.actions || [];
                this.showTurnActions(data.actions);
                // AI解説パネル更新 + 推奨牌ハイライト
                if (data.ai_analysis) {
                    this.lastAiAnalysis = data.ai_analysis;
                    this.showAiAnalysis(data.ai_analysis);
                    this.highlightRecommendedTiles(data.ai_analysis);
                }
                break;

            case 'call_option':
                this.updateGameState(data.state);
                this.showCallOptions(data.actions);
                break;

            case 'ai_analysis':
                if (data.ai_analysis) {
                    this.lastAiAnalysis = data.ai_analysis;
                    this.showAiAnalysis(data.ai_analysis);
                    this.highlightRecommendedTiles(data.ai_analysis);
                }
                break;

            case 'triple_recommendation':
                this._renderTripleRecommendations(data.data);
                break;

            case 'dahai':
                this.recordDiscard(data);
                this.updateGameState(data.state);
                if (data.actor !== this.humanSeat) {
                    this.showDiscardAnimation(data.actor, data.pai);
                }
                break;

            case 'hora':
                this.showHoraResult(data);
                break;

            case 'round_end':
                this.updateGameState(data.state);
                break;

            case 'ryukyoku':
                this.showRyukyokuResult(data);
                break;

            case 'waiting_next_round':
                this.showNextRoundButton();
                break;

            case 'game_end':
                this.showGameEnd(data.state);
                break;

            default:
                console.log('[MSG] Unknown type:', data.type);
        }
    }

    /**
     * ゲーム状態を反映
     */
    updateGameState(state) {
        if (!state) return;
        this.state = state;

        // 局が変わったら履歴をリセット
        const roundStr = `${state.round}-${state.honba}`;
        if (this.currentRoundStr !== roundStr) {
            this.currentRoundStr = roundStr;
            this.riverTiles = { 0: [], 1: [], 2: [], 3: [] };
        }

        // 情報バー
        this.updateInfoBar(state);

        // 各プレイヤー
        state.players.forEach(player => {
            this.updatePlayerArea(player, state);
        });

        // 向聴数表示
        this.updateShantenDisplay(state);
    }

    /**
     * 情報バー更新
     */
    updateInfoBar(state) {
        const roundName = document.getElementById('round-name');
        const honba = document.getElementById('honba');
        const remaining = document.getElementById('tiles-remaining');
        const doraContainer = document.getElementById('dora-indicators');

        if (roundName) roundName.textContent = state.round_name || '';
        if (honba) honba.textContent = state.honba > 0 ? `${state.honba}本場` : '';
        if (remaining) remaining.textContent = state.tiles_remaining;

        // ドラ表示牌
        if (doraContainer) {
            doraContainer.innerHTML = '';
            (state.dora_indicators || []).forEach(id => {
                const el = TileRenderer.createTileElement(id, { small: true });
                doraContainer.appendChild(el);
            });
        }

        // リーチ棒
        const riichiSticks = document.getElementById('riichi-sticks');
        if (riichiSticks) {
            riichiSticks.innerHTML = '';
            for (let i = 0; i < (state.riichi_sticks || 0); i++) {
                const stick = document.createElement('div');
                stick.classList.add('riichi-stick');
                riichiSticks.appendChild(stick);
            }
        }

        // 巡目表示
        const turnCount = document.getElementById('turn-count');
        if (turnCount && state.turn_count !== undefined) {
            const junme = Math.floor(state.turn_count / 4) + 1;
            const oldText = turnCount.textContent;
            turnCount.textContent = junme;
            if (oldText !== String(junme)) {
                turnCount.classList.remove('animate-turn-update');
                void turnCount.offsetWidth; // reflow
                turnCount.classList.add('animate-turn-update');
            }
        }
    }

    /**
     * プレイヤーエリア更新
     */
    updatePlayerArea(player, state) {
        const seat = player.seat;

        // 点数
        const scoreEl = document.getElementById(`score-${seat}`);
        if (scoreEl) scoreEl.textContent = player.score.toLocaleString();

        // 風
        const windEl = document.getElementById(`wind-${seat}`);
        if (windEl) {
            const relativeSeat = (seat - state.dealer + 4) % 4;
            windEl.textContent = this.WIND_CHARS[relativeSeat];
            windEl.classList.toggle('dealer', seat === state.dealer);
        }

        // 手牌
        const handContainer = document.getElementById(`hand-${seat}`);
        if (handContainer) {
            if (seat === this.humanSeat) {
                this.renderMyHand(handContainer, player);
            } else {
                this.renderOtherHand(handContainer, player);
            }
        }

        // 捨て牌
        const discardContainer = document.getElementById(`discards-${seat}`);
        if (discardContainer) {
            this.renderDiscards(discardContainer, player, seat === this.humanSeat);
        }

        // 副露
        const meldContainer = document.getElementById(`melds-${seat}`);
        if (meldContainer) {
            TileRenderer.renderMelds(meldContainer, player.melds);
        }
    }

    /**
     * 自分の手牌を描画（クリッカブル）
     */
    renderMyHand(container, player) {
        container.innerHTML = '';
        if (!player.hand) return;

        player.hand.forEach((id, index) => {
            const isTsumo = index === player.hand.length - 1 &&
                            player.hand.length % 3 === 2;
            const el = TileRenderer.createTileElement(id, {
                clickable: true,
                tsumo: isTsumo,
            });

            el.addEventListener('click', () => {
                if (this.isMyTurn) {
                    this.onTileClick(id, el);
                }
            });

            container.appendChild(el);
        });
    }

    /**
     * 他家の手牌を描画（裏向き表示）
     */
    renderOtherHand(container, player) {
        container.innerHTML = '';
        // 手牌が公開されている場合（和了時・流局時など）
        if (player.hand) {
            player.hand.forEach(id => {
                const el = TileRenderer.createTileElement(id, { small: true });
                container.appendChild(el);
            });
        } else if (player.hand_count > 0) {
            // 手牌が隠蔽されている場合（プレイ中）
            for (let i = 0; i < player.hand_count; i++) {
                const el = TileRenderer.createTileElement('?', { small: true, back: true });
                container.appendChild(el);
            }
        }
    }

    /**
     * 捨て牌を描画（全牌同サイズで見やすく）
     * 隠蔽ロジック（手出しのランダム化）を適用した河を使用する
     */
    renderDiscards(container, player, isSelf) {
        // ラベルを保持
        const label = container.querySelector('.discard-label');
        container.innerHTML = '';
        if (label) container.appendChild(label);

        // クライアントで管理しているランダム化済みの河配列を使用する
        const riverArray = this.riverTiles[player.seat] || [];

        riverArray.forEach((tileData, idx) => {
            const isLast = idx === riverArray.length - 1;
            const el = TileRenderer.createTileElement(tileData.id, {
                small: true,
            });
            el.classList.add('animate-appear', 'river-tile');
            
            // ツモ切り・手出しのクラス付与
            if (tileData.isTsumogiri) {
                el.classList.add('is-tsumogiri');
                el.title = "ツモ切り";
            } else {
                el.classList.add('is-tedashi');
                el.title = "手出し";
            }

            // 最後の打牌をハイライト
            if (isLast) {
                el.classList.add('tile-last-discard');
            }
            container.appendChild(el);
        });
    }

    /**
     * 相手の手出し牌を隠蔽するための河ランダム化処理
     * dahai コール時に記録される
     */
    recordDiscard(data) {
        const actor = data.actor;
        const tileId = data.pai;
        const isTsumogiri = data.tsumogiri;

        if (!this.riverTiles[actor]) {
            this.riverTiles[actor] = [];
        }

        const tileData = {
            id: tileId,
            isTsumogiri: isTsumogiri,
            timestamp: Date.now()
        };

        if (isTsumogiri) {
            // ツモ切りの場合：時系列通り末尾に追加
            this.riverTiles[actor].push(tileData);
        } else {
            // 手出しの場合：情報隠蔽のためランダムな位置に挿入
            const randomIndex = Math.floor(Math.random() * (this.riverTiles[actor].length + 1));
            this.riverTiles[actor].splice(randomIndex, 0, tileData);
        }
    }

    /**
     * 牌クリック時の処理（ワンクリック打牌）
     */
    onTileClick(tileId, element) {
        this.discardTile(tileId);
    }

    /**
     * 打牌を実行
     */
    discardTile(tileId) {
        this.isMyTurn = false;
        this.selectedTile = null;
        this.hideActionBar();
        this.clearTileHighlights();

        this.send({
            action: 'dahai',
            tile: tileId,
            tsumogiri: false,
        });
    }

    // ============================================================
    // Phase 2: AI推奨牌ハイライト
    // ============================================================

    /**
     * AI推奨牌を手牌上でハイライト
     */
    highlightRecommendedTiles(analysis) {
        this.clearTileHighlights();

        if (!analysis) return;

        // choices がない場合 mortal_top3 からフォールバック生成
        let choices = analysis.choices;
        if (!choices && analysis.mortal_top3) {
            choices = analysis.mortal_top3.map(c => ({
                tile: c.tile_name,
                prob: c.prob,
                acceptance: c.acceptance
            }));
        }
        if (!choices || choices.length === 0) return;

        const handContainer = document.getElementById(`hand-${this.humanSeat}`);
        if (!handContainer) return;

        const tiles = handContainer.querySelectorAll('.tile-clickable');

        choices.forEach((choice, idx) => {
            // 牌IDで手牌要素を検索
            const tileId = choice.tile;
            for (const tileEl of tiles) {
                if (tileEl.dataset.tileId === tileId &&
                    !tileEl.classList.contains('tile-recommended') &&
                    !tileEl.classList.contains('tile-candidate-2') &&
                    !tileEl.classList.contains('tile-candidate-3')) {
                    if (idx === 0) {
                        tileEl.classList.add('tile-recommended');
                    } else if (idx === 1) {
                        tileEl.classList.add('tile-candidate-2');
                    } else if (idx === 2) {
                        tileEl.classList.add('tile-candidate-3');
                    }
                    break;
                }
            }
        });
    }

    /**
     * 牌ハイライトをクリア
     */
    clearTileHighlights() {
        document.querySelectorAll('.tile-recommended, .tile-candidate-2, .tile-candidate-3').forEach(el => {
            el.classList.remove('tile-recommended', 'tile-candidate-2', 'tile-candidate-3');
        });
    }

    // ============================================================
    // Phase 2: アニメーション強化
    // ============================================================

    /**
     * ツモ牌のアニメーション
     */
    animateTsumo() {
        requestAnimationFrame(() => {
            const handContainer = document.getElementById(`hand-${this.humanSeat}`);
            if (!handContainer) return;

            const tsumoTile = handContainer.querySelector('.tile-tsumo');
            if (tsumoTile) {
                tsumoTile.classList.add('animate-tsumo');
            }
        });
    }

    /**
     * テンパイバナー表示
     */
    showTenpaiBanner() {
        const existing = document.querySelector('.tenpai-banner');
        if (existing) existing.remove();

        const banner = document.createElement('div');
        banner.classList.add('tenpai-banner');
        banner.textContent = 'テンパイ！';
        document.body.appendChild(banner);

        setTimeout(() => {
            if (banner.parentNode) banner.remove();
        }, 1500);
    }

    /**
     * ターン時のアクション表示
     */
    showTurnActions(actions) {
        const actionBar = document.getElementById('action-bar');
        const actionButtons = document.getElementById('action-buttons');

        if (!actionBar || !actionButtons) return;

        actionButtons.innerHTML = '';

        // 特殊アクションボタン
        if (actions && actions.length > 0) {
            actions.forEach(action => {
                if (action.type === 'hora') {
                    const btn = this.createActionButton('ツモ和了', 'hora', () => {
                        this.isMyTurn = false;
                        this.hideActionBar();
                        this.clearTileHighlights();
                        this.send({ action: 'hora', is_tsumo: true });
                    });
                    actionButtons.appendChild(btn);
                } else if (action.type === 'riichi') {
                    const btn = this.createActionButton(
                        `リーチ (${action.tile})`, 'riichi', () => {
                            this.isMyTurn = false;
                            this.hideActionBar();
                            this.clearTileHighlights();
                            this.send({ action: 'riichi', tile: action.tile });
                        }
                    );
                    actionButtons.appendChild(btn);
                } else if (action.type === 'ankan') {
                    const btn = this.createActionButton('暗槓', 'btn-action', () => {
                        this.isMyTurn = false;
                        this.hideActionBar();
                        this.clearTileHighlights();
                        this.send({ action: 'ankan', tile: action.tile });
                    });
                    actionButtons.appendChild(btn);
                }
            });
        }

        actionBar.classList.remove('hidden');
    }

    /**
     * 鳴き選択肢の表示
     */
    showCallOptions(actions) {
        const actionBar = document.getElementById('action-bar');
        const actionButtons = document.getElementById('action-buttons');

        if (!actionBar || !actionButtons) return;

        actionButtons.innerHTML = '';

        actions.forEach(action => {
            let labelHTML = '';
            let cssClass = 'btn-action';

            switch (action.type) {
                case 'hora':
                    labelHTML = 'ロン';
                    cssClass = 'hora';
                    break;
                case 'pon':
                    labelHTML = 'ポン';
                    break;
                case 'chi': {
                    const tilesHtml = (action.consumed || []).map(id => TileRenderer.createTileElement(id, {small: true}).outerHTML).join('');
                    labelHTML = `<div style="display:flex; align-items:center; gap:4px"><span>チー</span><div style="display:flex;">${tilesHtml}</div></div>`;
                    break;
                }
                case 'daiminkan':
                    labelHTML = 'カン';
                    break;
                case 'skip':
                    labelHTML = 'スキップ';
                    cssClass = 'skip';
                    break;
                default:
                    labelHTML = action.type;
            }

            const btn = document.createElement('button');
            btn.classList.add('btn', 'btn-action');
            if (cssClass) btn.classList.add(cssClass);
            btn.innerHTML = labelHTML;
            btn.addEventListener('click', () => {
                this.hideActionBar();

                if (action.type === 'skip') {
                    this.send({ action: 'skip' });
                } else if (action.type === 'hora') {
                    this.send({ action: 'hora', is_tsumo: false });
                } else if (action.type === 'pon') {
                    this.send({
                        action: 'pon',
                        consumed: action.consumed || [],
                    });
                } else if (action.type === 'chi') {
                    this.send({
                        action: 'chi',
                        consumed: action.consumed || [],
                    });
                } else if (action.type === 'daiminkan') {
                    this.send({
                        action: 'daiminkan',
                        consumed: action.consumed || [],
                    });
                }
            });

            actionButtons.appendChild(btn);
        });

        actionBar.classList.remove('hidden');
    }

    /**
     * アクションボタン生成
     */
    createActionButton(labelHTML, cssClass, onClick) {
        const btn = document.createElement('button');
        btn.classList.add('btn', 'btn-action');
        if (cssClass) btn.classList.add(cssClass);
        btn.innerHTML = labelHTML;
        btn.addEventListener('click', onClick);
        return btn;
    }

    /**
     * アクションバーを隠す
     */
    hideActionBar() {
        const actionBar = document.getElementById('action-bar');
        if (actionBar) actionBar.classList.add('hidden');
    }

    /**
     * アクションインジケーター表示
     */
    showActionIndicator(text) {
        const indicator = document.getElementById('action-indicator');
        if (indicator) {
            indicator.textContent = text;
            indicator.classList.add('turn-indicator');
            setTimeout(() => {
                indicator.classList.remove('turn-indicator');
                indicator.textContent = '';
            }, 1500);
        }
    }

    /**
     * 打牌アニメーション（他家）
     */
    showDiscardAnimation(seat, tileId) {
        // 簡易的な通知
        this.showActionIndicator(`${this.SEAT_NAMES[seat]} → ${tileId}`);
    }

    /**
     * 向聴数表示（Phase 2強化：テンパイ時グロウ + 待ち牌表示）
     */
    updateShantenDisplay(state) {
        const display = document.getElementById('shanten-display');
        const valueEl = document.getElementById('shanten-value');
        if (!display || !valueEl) return;

        const myPlayer = state.players.find(p => p.seat === this.humanSeat);
        if (!myPlayer || !myPlayer.hand) {
            display.classList.add('hidden');
            return;
        }

        // 向聴数がサーバーから来ている場合
        if (state.shanten !== undefined && state.shanten !== null) {
            const shanten = state.shanten;
            const shantenNames = {
                '-1': '和了形',
                '0': 'テンパイ',
                '1': 'イーシャンテン',
                '2': 'リャンシャンテン',
                '3': 'サンシャンテン',
            };
            const name = shantenNames[String(shanten)] || `${shanten}向聴`;

            let html = `<span class="shanten-label">${name}</span>`;

            // テンパイ時: 待ち牌表示
            if (shanten === 0 && state.waiting_tiles && state.waiting_tiles.length > 0) {
                html += `<span class="waiting-list">待ち: ${state.waiting_tiles.join(', ')}</span>`;
                display.classList.add('tenpai');

                // 初めてテンパイになった時にバナーを表示
                if (!this.previousTenpai) {
                    this.showTenpaiBanner();
                    this.previousTenpai = true;
                }
            } else {
                display.classList.remove('tenpai');
                if (shanten > 0) {
                    this.previousTenpai = false;
                }
            }

            valueEl.innerHTML = html;
        } else {
            // フォールバック: 手牌枚数表示
            const handCount = myPlayer.hand.length;

            if (myPlayer.is_riichi) {
                valueEl.textContent = '🀄 リーチ中';
                display.classList.add('tenpai');
            } else if (handCount >= 13) {
                valueEl.textContent = `手牌: ${handCount}枚`;
                display.classList.remove('tenpai');
            }
        }
        display.classList.remove('hidden');
    }

    /**
     * 和了結果表示
     */
    showHoraResult(data) {
        const overlay = document.getElementById('result-overlay');
        const content = document.getElementById('result-content');
        const btnNext = document.getElementById('btn-next-round');
        const btnBack = document.getElementById('btn-back-to-start');

        if (!overlay || !content) return;

        this.clearTileHighlights();

        if (data.state) {
            this.updateGameState(data.state);
        }

        const horaData = data.data || {};
        const isMyWin = horaData.actor === this.humanSeat;
        const isTsumo = horaData.is_tsumo;
        const winnerName = this.SEAT_NAMES[horaData.actor] || '不明';

        // バナー表示
        this.showBanner(isMyWin ? 'ツモ！' : `${winnerName} ${isTsumo ? 'ツモ' : 'ロン'}`,
                        isMyWin ? 'hora-banner' : 'riichi-banner');

        let html = `
            <div class="result-title ${isMyWin ? 'win' : 'lose'}">
                ${isMyWin ? '🎉 和了！' : `${winnerName} の和了`}
            </div>
        `;

        // 役一覧
        if (horaData.yakus && horaData.yakus.length > 0) {
            html += '<div class="result-yakus">';
            horaData.yakus.forEach(yaku => {
                html += `
                    <div class="yaku-item">
                        <span class="yaku-name">${yaku.name}</span>
                        <span class="yaku-han">${yaku.han}翻</span>
                    </div>
                `;
            });
            html += '</div>';
        }

        // 点数
        html += `
            <div class="result-score">
                ${horaData.han || 0}翻 ${horaData.fu || 0}符
                → ${(horaData.points || 0).toLocaleString()}点
            </div>
        `;

        // スコア一覧
        if (horaData.scores) {
            html += '<table class="result-scores-table">';
            horaData.scores.forEach((score, idx) => {
                const diff = score - 25000;
                const diffClass = diff >= 0 ? 'score-positive' : 'score-negative';
                const diffStr = diff >= 0 ? `+${diff}` : `${diff}`;
                html += `
                    <tr>
                        <td>${this.SEAT_NAMES[idx]}</td>
                        <td>${score.toLocaleString()}</td>
                        <td class="${diffClass}">${diffStr}</td>
                    </tr>
                `;
            });
            html += '</table>';
        }

        content.innerHTML = html;

        if (btnNext) {
            btnNext.classList.remove('hidden');
            btnNext.onclick = () => {
                overlay.classList.add('hidden');
                this.previousTenpai = false;
                this.send({ action: 'next_round' });
            };
        }
        if (btnBack) btnBack.classList.add('hidden');

        setTimeout(() => {
            overlay.classList.remove('hidden');
        }, 2000);
    }

    /**
     * 次局ボタン表示
     */
    showNextRoundButton() {
        const overlay = document.getElementById('result-overlay');
        const content = document.getElementById('result-content');
        const btnNext = document.getElementById('btn-next-round');

        if (!overlay || !content) return;

        // 和了でない場合（流局等）
        if (overlay.classList.contains('hidden')) {
            content.innerHTML = `
                <div class="result-title draw">流局</div>
                <p style="color: var(--color-text-secondary); margin: var(--space-md) 0;">
                    荒牌流局
                </p>
            `;

            if (btnNext) {
                btnNext.classList.remove('hidden');
                btnNext.onclick = () => {
                    overlay.classList.add('hidden');
                    this.previousTenpai = false;
                    this.send({ action: 'next_round' });
                };
            }

            overlay.classList.remove('hidden');
        }
    }

    /**
     * 対局終了表示
     */
    showGameEnd(state) {
        const overlay = document.getElementById('result-overlay');
        const content = document.getElementById('result-content');
        const btnNext = document.getElementById('btn-next-round');
        const btnBack = document.getElementById('btn-back-to-start');

        if (!overlay || !content) return;

        this.clearTileHighlights();

        const players = state.players || [];
        const sorted = [...players].sort((a, b) => b.score - a.score);
        const myRank = sorted.findIndex(p => p.seat === this.humanSeat) + 1;

        let html = `
            <div class="result-title ${myRank === 1 ? 'win' : 'lose'}">
                ${myRank === 1 ? '🏆 1位！' : `${myRank}位`}
            </div>
            <table class="result-scores-table" style="margin: var(--space-lg) 0;">
        `;

        sorted.forEach((p, idx) => {
            const isMe = p.seat === this.humanSeat;
            html += `
                <tr style="${isMe ? 'font-weight: 700; color: var(--color-accent-gold);' : ''}">
                    <td>${idx + 1}位</td>
                    <td>${this.SEAT_NAMES[p.seat]}</td>
                    <td>${p.score.toLocaleString()}点</td>
                </tr>
            `;
        });
        html += '</table>';

        content.innerHTML = html;

        if (btnNext) btnNext.classList.add('hidden');
        if (btnBack) {
            btnBack.classList.remove('hidden');
            btnBack.onclick = () => {
                overlay.classList.add('hidden');
                location.reload();
            };
        }

        overlay.classList.remove('hidden');
    }

    /**
     * バナー表示
     */
    showBanner(text, cssClass) {
        const banner = document.createElement('div');
        banner.classList.add(cssClass);
        banner.textContent = text;
        document.body.appendChild(banner);

        setTimeout(() => {
            banner.remove();
        }, 2000);
    }

    // ============================================================
    // AI解説パネル (Phase 2 強化)
    // ============================================================

    /**
     * AI解説を表示 (強化版)
     */
    showAiAnalysis(analysis) {
        if (!analysis) return;
        
        const ov = document.getElementById('ai-overlay');
        if (ov) {
            ov.style.display = 'block';
            
            const recTile = document.getElementById('ai-tile') || document.getElementById('ai-rec-tile');
            if (recTile) recTile.textContent = (analysis.recommendation || '').replace(/[0r]/g, '') || '-';
            
            const reason = document.getElementById('ai-reason') || document.getElementById('ai-reasoning');
            if (reason) reason.textContent = analysis.reasoning || "解析待機中...";

            const max = Math.max(analysis.attack_score || 0, analysis.defense_score || 0, 1);
            const atkBar = document.getElementById('atk-bar');
            if (atkBar) atkBar.style.width = `${((analysis.attack_score || 0) / max) * 100}%`;
            
            const atkVal = document.getElementById('atk-val');
            if (atkVal) atkVal.textContent = (analysis.attack_score || 0).toFixed(1);
            
            const defBar = document.getElementById('def-bar');
            if (defBar) defBar.style.width = `${((analysis.defense_score || 0) / max) * 100}%`;
            
            const defVal = document.getElementById('def-val');
            if (defVal) defVal.textContent = (analysis.defense_score || 0).toFixed(2);
        }

        if (analysis.reasoning) {
            this.speak(analysis.reasoning);
        }
    }

    /**
     * 流局結果表示
     */
    showRyukyokuResult(data) {
        const modal = document.getElementById('ryukyoku-modal');
        if (!modal) return;
        
        modal.classList.remove('hidden');
        modal.style.display = 'flex';
        
        // 局情報
        const rRound = document.getElementById('ryukyoku-round');
        if (rRound) rRound.textContent = data.round || '東1局';
        
        // 各プレイヤーの手牌公開
        if (data.hands) {
            data.hands.forEach((hand, idx) => {
                const container = document.getElementById(`hand-reveal-${idx}`);
                if (container && hand) {
                    const tilesHtml = hand.map(id => TileRenderer.createTileElement(id, { small: true }).outerHTML).join('');
                    container.innerHTML = `
                        <div class="player-label">${data.players && data.players[idx] ? data.players[idx].name : this.SEAT_NAMES[idx]}</div>
                        <div class="tiles" style="display:flex; flex-wrap:wrap; gap:4px;">
                            ${tilesHtml}
                        </div>
                    `;
                }
            });
        }
        
        // 聴牌状況
        if (data.tenpai_info) {
            data.tenpai_info.forEach((info, idx) => {
                const el = document.getElementById(`tenpai-${idx}`);
                if (el) {
                    const isTenpai = info.tenpai;
                    el.className = `status-item ${isTenpai ? 'tenpai' : 'noten'}`;
                    el.innerHTML = `
                        <span class="player-name">${info.name || this.SEAT_NAMES[idx]}</span>
                        <span class="tenpai-badge ${isTenpai ? '' : 'noten'}">
                            ${isTenpai ? '聴牌' : 'ノーテン'}
                        </span>
                        <span class="penalty ${info.delta >= 0 ? '' : 'negative'}">
                            ${info.delta >= 0 ? '+' : ''}${info.delta}
                        </span>
                    `;
                }
            });
        }
        
        // 点数移動アニメーション
        if (data.score_changes) {
            const container = document.getElementById('score-anim');
            if (container) {
                container.innerHTML = '';
                data.score_changes.forEach((change, idx) => {
                    setTimeout(() => {
                        const arrow = document.createElement('div');
                        arrow.className = 'score-arrow';
                        arrow.textContent = change.delta >= 0 ? `↑ +${change.delta}` : `↓ ${change.delta}`;
                        arrow.style.color = change.delta >= 0 ? '#48bb78' : '#f56565';
                        arrow.style.left = `${50 + (idx - 1.5) * 30}%`;
                        container.appendChild(arrow);
                        
                        setTimeout(() => arrow.remove(), 1500);
                    }, idx * 500);
                });
            }
        }
        
        // 最終点数表示
        if (data.scores) {
            const fs = document.getElementById('final-score');
            if (fs) fs.textContent = data.scores[this.humanSeat] || 0;
        }

        const btnNext = document.getElementById('btn-ryukyoku-next') || document.getElementById('btn-next-round');
        if (btnNext) {
            btnNext.onclick = () => {
                modal.classList.add('hidden');
                modal.style.display = 'none';
                this.previousTenpai = false;
                this.send({ action: 'next_round' });
            };
        }
    }

    _renderTripleRecommendations(tripleData) {
        let panel = document.getElementById("ai-panel");
        if (!panel) {
            panel = document.createElement("div");
            panel.id = "ai-panel";
            document.body.appendChild(panel);
        }
        
        const ai = tripleData.ai;
        const strat = tripleData.strategy;
        const xai = tripleData.xai;
        const interp = tripleData.interpretation;
        const meta = tripleData.meta;
        
        let html = `<div class="ai-title">3系統推論統合 (${meta.latency_ms.toFixed(0)}ms)</div>`;
        
        // ── Mortal AI 確率分布 ──
        if (ai && ai.primary) {
            html += `<div style="margin-bottom:8px;"><strong>Mortal AI 分布</strong></div>`;
            const recs = [ai.primary, ...(ai.alternatives || [])];
            recs.forEach((r, i) => {
                const width = (r.prob * 100).toFixed(1);
                const color = i === 0 ? "#ff4757" : i === 1 ? "#ffa502" : "#2ed573";
                html += `
                    <div class="ai-row">
                        <span class="ai-rank">#${i+1}</span>
                        <span class="ai-tile">${r.tile}</span>
                        <div class="ai-bar-bg">
                            <div class="ai-bar-fill" style="width:${width}%; background:${color}"></div>
                        </div>
                        <span class="ai-prob">${(r.prob*100).toFixed(1)}%</span>
                    </div>
                `;
            });
        }
        
        // ── 方向性1: XAI解析 ──
        html += `<div style="margin-top:12px; margin-bottom:4px;"><strong>方向性1: XAI解析</strong></div>`;
        html += `<div style="color:#a5b4fc; font-size:11px; margin-bottom:4px;">[${xai.keywords.join(", ")}]</div>`;
        html += `<div style="color:#cbd5e1; font-size:12px; line-height:1.3;">${xai.reasoning}</div>`;

        // ── 方向性2: 戦略判断 ──
        const stratColor = strat.type === "ATTACK" ? "#ef4444" : strat.type === "DEFENSE" ? "#3b82f6" : "#a3a3a3";
        html += `<div style="margin-top:12px; margin-bottom:4px;"><strong>方向性2: 戦略判断</strong>
            <span style="color:${stratColor}; font-size:11px; margin-left:6px; padding:1px 6px; border:1px solid ${stratColor}; border-radius:3px;">${strat.type}</span>
        </div>`;
        
        // 信頼度バー
        const confWidth = ((strat.confidence || 0) * 100).toFixed(0);
        const confColor = strat.confidence > 0.7 ? "#10b981" : strat.confidence > 0.4 ? "#f59e0b" : "#ef4444";
        html += `<div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
            <span style="color:#9ca3af; font-size:10px; min-width:45px;">信頼度</span>
            <div style="flex:1; height:4px; background:#374151; border-radius:2px;">
                <div style="width:${confWidth}%; height:100%; background:${confColor}; border-radius:2px;"></div>
            </div>
            <span style="color:${confColor}; font-size:10px; font-weight:bold;">${confWidth}%</span>
        </div>`;
        
        // 翻数評価
        if (strat.han_evaluation && strat.han_evaluation.current > 0) {
            const he = strat.han_evaluation;
            html += `<div style="color:#fbbf24; font-size:11px; margin-bottom:2px;">翻数: ${he.current}翻→${he.potential}翻 ${he.mangan_reachable ? "🀄満貫到達可能" : ""} (${he.points_if_agari}点)</div>`;
        }
        
        html += `<div style="color:#e2e8f0; font-size:12px;">推奨: <span style="font-weight:bold; color:white;">${strat.tile}</span></div>`;
        html += `<div style="color:#cbd5e1; font-size:12px; line-height:1.3;">${strat.reasoning || strat.judgment}</div>`;
        
        if (strat.rules && strat.rules.length > 0) {
            html += `<div style="color:#6b7280; font-size:10px; margin-top:2px;">適用ルール: ${strat.rules.join(", ")}</div>`;
        }
        
        // ── 方向性3: 逆推論 ──
        const catLabel = interp.category === "DEFENSE" ? "🛡防御" : interp.category === "VALUE" ? "💰打点" : "📐効率";
        html += `<div style="margin-top:12px; margin-bottom:4px;"><strong>方向性3: 逆推論</strong>
            <span style="font-size:11px; margin-left:6px;">${catLabel}</span>
        </div>`;
        html += `<div style="color:#a5b4fc; font-size:11px; margin-bottom:4px;">意図: ${interp.intents.join(", ")}</div>`;
        html += `<div style="color:#cbd5e1; font-size:12px; line-height:1.3;">${interp.text}</div>`;
        
        // 逆推論の信頼度
        if (interp.confidence_score) {
            const iConf = (interp.confidence_score * 100).toFixed(0);
            html += `<div style="color:#6b7280; font-size:10px; margin-top:2px;">確信度: ${interp.confidence}(${iConf}%) | パターン: ${(interp.rules || []).join(", ")}</div>`;
        }
        
        // ── メタ注記 ──
        const consColor = meta.consistency === "完全一致" ? "#10b981" : meta.consistency === "部分一致" ? "#f59e0b" : "#ef4444";
        html += `<div style="margin-top:12px; padding:6px; background:#374151; border-radius:4px; font-size:11px; color:#9ca3af; border-left: 3px solid ${consColor}">
            <strong style="color:${consColor}">${meta.consistency}</strong>
            <span style="margin-left:8px;">統合信頼度: ${((meta.integrated_confidence || 0) * 100).toFixed(0)}%</span><br/>
            ${meta.note}
        </div>`;
        
        panel.innerHTML = html;
        panel.style.display = "block";
    }
}
