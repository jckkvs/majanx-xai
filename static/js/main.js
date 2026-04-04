/**
 * メインエントリーポイント
 * Implements: F-008 | アプリケーション起動・画面制御
 */

document.addEventListener('DOMContentLoaded', () => {
    const startScreen = document.getElementById('start-screen');
    const gameScreen = document.getElementById('game-screen');
    const btnStart = document.getElementById('btn-start-game');

    let client = null;

    /**
     * 画面切り替え
     */
    function showScreen(screen) {
        document.querySelectorAll('.screen').forEach(s => {
            s.classList.remove('active');
        });
        screen.classList.add('active');
    }

    /**
     * 対局開始
     */
    btnStart.addEventListener('click', () => {
        showScreen(gameScreen);

        // WebSocket接続
        client = new GameClient();
        client.connect();
    });

    /**
     * リプレイ開始
     */
    const btnReplay = document.getElementById('btn-start-replay');
    const fileInput = document.getElementById('replay-file');
    const replayBar = document.getElementById('replay-bar');

    if (btnReplay && fileInput) {
        btnReplay.addEventListener('click', async () => {
            const file = fileInput.files[0];
            if (!file) {
                alert('ファイルを選択してください (.log または .json)');
                return;
            }

            btnReplay.disabled = true;
            btnReplay.textContent = "アップロード中...";

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/api/replay/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                
                if (data.session_id) {
                    showScreen(gameScreen);
                    if (replayBar) replayBar.classList.remove('hidden');

                    client = new GameClient();
                    client.connect(data.session_id);

                    // Replay control buttons
                    document.getElementById('btn-replay-prev').onclick = () => {
                        client.send({ action: 'prev' });
                    };
                    document.getElementById('btn-replay-next').onclick = () => {
                        client.send({ action: 'next' });
                    };
                } else {
                    alert('エラー: セッションが作成できませんでした');
                }
            } catch (err) {
                console.error(err);
                alert('通信エラー');
            } finally {
                btnReplay.disabled = false;
                btnReplay.innerHTML = '<span class="btn-icon">📁</span> 牌譜を開く';
            }
        });
    }

    /**
     * AIパネル開閉トグル
     */
    const aiPanel = document.getElementById('ai-panel');
    const btnToggle = document.getElementById('btn-toggle-ai');
    if (aiPanel && btnToggle) {
        aiPanel.querySelector('.ai-panel-header').addEventListener('click', () => {
            aiPanel.classList.toggle('collapsed');
        });
    }

    /**
     * キーボードショートカット
     */
    document.addEventListener('keydown', (e) => {
        if (!client) return;

        // Escでアクションバーを隠す
        if (e.key === 'Escape') {
            if (client.isMyTurn) {
                client.hideActionBar();
                client.selectedTile = null;
                document.querySelectorAll('.tile-clickable.selected').forEach(el => {
                    el.classList.remove('selected');
                });
            }
        }

        // 'a' でAIパネルのトグル
        if (e.key === 'a' && !e.ctrlKey && !e.metaKey) {
            if (aiPanel) {
                aiPanel.classList.toggle('collapsed');
            }
        }
    });
});
