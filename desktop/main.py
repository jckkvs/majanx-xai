import sys
import os
import time

# プロジェクトルートをパスに追加（serverモジュール参照のため）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal

from desktop.overlay_window import OverlayWindow
from desktop.screen_capturer import ScreenCapturer
from server.commentator import CommentatorAI
from server.models import GameState, PlayerState, Tile
from server.mortal.mortal_agent import MortalAgent

class CaptureThread(QThread):
    comment_ready = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.capturer = ScreenCapturer()
        
        # 簡易モックエンジン (FastAPIに依存せずにCommentatorを起動)
        class MockEngine:
            def __init__(self):
                self.state = GameState()
                self.state.players = [PlayerState(seat=i) for i in range(4)]
            def _hand_to_34(self, hand):
                arr = [0]*34
                for t in hand:
                    idx = t.suit.value * 9 + t.number - 1 if t.suit.value < 3 else 27 + t.number - 1
                    arr[idx] += 1
                return arr
                
        self.mock_engine = MockEngine()
        self.commentator = CommentatorAI(self.mock_engine)
        self.mortal = MortalAgent(0, self.mock_engine)

    def run(self):
        while True:
            # 外部画面キャプチャの実行
            state = self.capturer.capture_frame()
            
            # TODO: 本格的な動作時は YOLOの出力を `self.mock_engine.state.players[0].hand` 等に変換する
            
            if state and state.get("status") == "stable":
                # AIから解説取得のダミー呼び出し
                try:
                    mortal_probs = self.mortal._get_probabilities()
                except Exception:
                    mortal_probs = None
                
                # 双視点解説を取得
                analysis = self.commentator.analyze(0, mortal_probs)
                
                # Overlay更新イベントを発火
                # ※ここではダミーの状態を投げていますが、実動時は analysis の結果をパースします
                msg_body = f"【外部画面認識】\n推奨打牌: {analysis['rule_view']['recommendation']}\n"
                msg_body += f"Mortal確率: 処理中...\n"
                msg_body += f"ルール評価: 受皿{analysis['rule_view'].get('acceptance',0)}枚"
                self.comment_ready.emit(msg_body)
            else:
                # デバッグ用定期更新
                self.comment_ready.emit("🔍 外部画面認識中...\n（Mortal推論待機中）")
                
            time.sleep(2.0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 透過オーバーレイ起動
    overlay = OverlayWindow()
    overlay.show()
    
    # キャプチャ＋AI推論スレッドの開始
    thread = CaptureThread()
    thread.comment_ready.connect(overlay.update_commentary)
    thread.start()
    
    sys.exit(app.exec())
