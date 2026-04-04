import cv2
import numpy as np
import mss
from collections import deque
from typing import Optional, Dict

class ScreenCapturer:
    """YOLOv8とmssを使った画面認識パイプライン（Phase 2最小実装）"""
    def __init__(self, roi: dict = None, conf: float = 0.82, fps: int = 12):
        self.roi = roi or {"top": 0, "left": 0, "width": 1920, "height": 1080}
        self.conf = conf
        self.fps = fps
        self.buffer = deque(maxlen=4)
        
        try:
            import easyocr
            self.ocr = easyocr.Reader(["en"], gpu=False, verbose=False) # デモ用にGPU強制解除
        except ImportError:
            self.ocr = None
            
        self.yolo = self._load_yolo()

    def _load_yolo(self):
        try:
            from ultralytics import YOLO
            # 実際にはここに学習済み重みを配置して読み込む
            # return YOLO("weights/mahjong_tiles.pt")
            print("[ScreenCapturer] YOLO model weights not found, using dummy detection.")
            return None
        except ImportError:
            print("[ScreenCapturer] ultralytics not installed. Dummy run.")
            return None

    def capture_frame(self) -> Optional[Dict]:
        with mss.mss() as sct:
            # 画面キャプチャ
            frame = np.array(sct.grab(self.roi))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)

        tiles = self._detect(frame)
        state = {"tiles": tiles, "timestamp": cv2.getTickCount()}
        self.buffer.append(state)

        if len(self.buffer) < 3: 
            return None
            
        stable = self._smooth()
        if not stable: 
            return None

        return {"hand_guess": stable, "status": "stable"}

    def _detect(self, frame) -> list:
        if not self.yolo: 
            # YOLOが無い場合のダミー処理：モックとして常に5p等を検出したことにするのもありだがここでは空を返す
            return []
            
        res = self.yolo(frame, verbose=False, conf=self.conf, iou=0.45)
        return [{"cls": int(b.cls), "conf": float(b.conf), "box": b.xyxy[0].cpu().numpy()} 
                for r in res for b in r.boxes]

    def _smooth(self) -> list:
        counts = {}
        for s in self.buffer:
            for d in s["tiles"]:
                counts[d["cls"]] = counts.get(d["cls"], 0) + d["conf"]
        # 高確信度 tile のみ採用
        return [tid for tid, c in counts.items() if c >= self.conf * 2]
