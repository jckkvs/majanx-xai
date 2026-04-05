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
        this.previousTenpai = false;

        this.WIND_CHARS = { 0: '東', 1: '南', 2: '西', 3: '北' };
        this.SEAT_NAMES = ['あなた', 'CPU 2', 'CPU 3', 'CPU 4'];
        this.isReplay = false;
        this.replaySessionId = null;

        // Settings & Voice
        this.settings = {};
        this.synth = window.speechSynthesis;
        this.lastSpoken = "";
        
        // Settings websocket
        this._initSettings();
    }

    async _initSettings() {
        try {
            const res = await fetch('/api/settings');
            this.settings = await res.json();
        } catch (e) {
            console.error('[Settings] Load error:', e);
        }

        // 簡易的な WebSocket による設定更新購読（settings.html 側で更新時に送信）
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.settingsWs = new WebSocket(`${protocol}//${location.host}/ws_ui`);
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
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        let url = `${protocol}//${location.host}/ws_ui`;
        
        if (replaySessionId) {
            this.isReplay = true;
            this.replaySessionId = replaySessionId;
            url = `${protocol}//${location.host}/ws/replay/${replaySessionId}`;
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

            case 'dahai':
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
     * 他家の手牌を描画（裏向き）
     */
    renderOtherHand(container, player) {
        container.innerHTML = '';
        // 手牌が公開されている場合（和了時）
        if (player.hand) {
            player.hand.forEach(id => {
                const el = TileRenderer.createTileElement(id, { small: true });
                container.appendChild(el);
            });
        } else {
            // 裏向き
            const count = player.hand_count || 13;
            for (let i = 0; i < count; i++) {
                const el = TileRenderer.createTileElement(null, {
                    small: true,
                    back: true,
                });
                container.appendChild(el);
            }
        }
    }

    /**
     * 捨て牌を描画（全牌同サイズで見やすく）
     */
    renderDiscards(container, player, isSelf) {
        // ラベルを保持
        const label = container.querySelector('.discard-label');
        container.innerHTML = '';
        if (label) container.appendChild(label);

        (player.discards || []).forEach((id, idx) => {
            const isLast = idx === (player.discards || []).length - 1;
            const el = TileRenderer.createTileElement(id, {
                small: true,
            });
            el.classList.add('animate-appear');
            // 最後の打牌をハイライト
            if (isLast) {
                el.classList.add('tile-last-discard');
            }
            container.appendChild(el);
        });
    }

    /**
     * 牌クリック時の処理
     */
    onTileClick(tileId, element) {
        // 既に選択中の牌をクリック → 打牌実行
        if (this.selectedTile === tileId &&
            element.classList.contains('selected')) {
            this.discardTile(tileId);
            return;
        }

        // 選択解除
        document.querySelectorAll('.tile-clickable.selected').forEach(el => {
            el.classList.remove('selected');
        });

        // 新しい牌を選択
        this.selectedTile = tileId;
        element.classList.add('selected');
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

        if (!analysis || !analysis.choices || analysis.choices.length === 0) return;

        const handContainer = document.getElementById(`hand-${this.humanSeat}`);
        if (!handContainer) return;

        const tiles = handContainer.querySelectorAll('.tile-clickable');

        analysis.choices.forEach((choice, idx) => {
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
        const mortalViewEl = document.getElementById('mortal_view');
        const ruleViewEl = document.getElementById('rule_view');
        const synthesisEl = document.getElementById('synthesis');
        const candidatesEl = document.getElementById('ai-candidates');

        if (!mortalViewEl || !ruleViewEl || !synthesisEl || !candidatesEl) return;

        // 双視点解説の反映
        mortalViewEl.textContent = analysis.mortal_view || "待機中...";
        ruleViewEl.textContent = analysis.rule_view || "待機中...";
        synthesisEl.textContent = analysis.synthesis || "解析中...";
        synthesisEl.className = "synthesis " + (analysis.agreement ? "agree" : "disagree");

        if (analysis.synthesis) {
            this.speak(analysis.synthesis);
        }

        // 候補リスト
        candidatesEl.innerHTML = '';
        if (analysis.mortal_top3) {
            analysis.mortal_top3.forEach((cand, index) => {
                const card = document.createElement('div');
                card.classList.add('ai-candidate-item');
                if (index === 0) card.classList.add('recommended');
                
                card.innerHTML = `
                    <div class="ai-candidate-tile">
                        <span class="choice-marker">${index === 0 ? '★ 推奨' : '候補' + (index + 1)}</span>
                        <strong>${cand.tile_name} 切り</strong>
                    </div>
                    <div class="ai-candidate-score">
                        確率: ${(cand.prob * 100).toFixed(1)}%
                    </div>
                `;
                candidatesEl.appendChild(card);
            });
        }
    }

    /**
     * 候補カードクリック → 手牌の対応牌をフォーカス
     */
    focusTileInHand(tileId) {
        const handContainer = document.getElementById(`hand-${this.humanSeat}`);
        if (!handContainer) return;

        // 既存の選択をクリア
        document.querySelectorAll('.tile-clickable.selected').forEach(el => {
            el.classList.remove('selected');
        });

        // 対応する牌を見つけて選択状態にする
        const tiles = handContainer.querySelectorAll('.tile-clickable');
        for (const tileEl of tiles) {
            if (tileEl.dataset.tileId === tileId) {
                tileEl.classList.add('selected');
                this.selectedTile = tileId;
                tileEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
                break;
            }
        }
    }
}
