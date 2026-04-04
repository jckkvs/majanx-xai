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
