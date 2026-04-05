import cv2
import numpy as np
import mss
from collections import deque
from typing import Optional, Dict, List

from .template_matcher import TemplateMatcher


class ScreenCapturer:
    """mssスクリーンキャプチャ + OpenCVテンプレートマッチングによる牌認識パイプライン"""

    def __init__(
        self,
        roi: dict = None,
        conf: float = 0.72,
        fps: int = 12,
        template_dir: str = "desktop/templates",
        hand_roi: dict = None,
    ):
        self.roi = roi or {"top": 0, "left": 0, "width": 1920, "height": 1080}
        self.conf = conf
        self.fps = fps
        self.hand_roi = hand_roi  # 手牌エリアの限定 ROI {x,y,w,h}
        self.buffer: deque = deque(maxlen=4)

        # YOLO障定 (weightsが存在する場合のみ使用)
        self.yolo = self._load_yolo()

        # OpenCVテンプレートマッチャー
        self.matcher = TemplateMatcher(
            template_dir=template_dir,
            conf_threshold=conf,
        )

    def _load_yolo(self):
        try:
            from ultralytics import YOLO
            # return YOLO("weights/mahjong_tiles.pt")
            print("[ScreenCapturer] YOLO model weights not found. Falling back to OpenCV Template Matching.")
            return None
        except ImportError:
            print("[ScreenCapturer] ultralytics not installed. Falling back to OpenCV Template Matching.")
            return None

    def capture_frame(self) -> Optional[Dict]:
        with mss.mss() as sct:
            frame_raw = np.array(sct.grab(self.roi))
            frame_bgr = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)

        detections = self._detect(frame_bgr)
        self.buffer.append({"tiles": detections, "timestamp": cv2.getTickCount()})

        if len(self.buffer) < 2:
            return None

        stable = self._smooth()
        if not stable:
            return None

        return {"hand_guess": stable, "raw_detections": detections, "status": "stable"}

    def _detect(self, frame_bgr: np.ndarray) -> List[Dict]:
        if self.yolo:
            res = self.yolo(frame_bgr, verbose=False, conf=self.conf, iou=0.45)
            return [
                {"tile_id": str(int(b.cls)), "conf": float(b.conf[0]), "box": b.xyxy[0].cpu().numpy()}
                for r in res for b in r.boxes
            ]
        # テンプレートマッチング / 輪郭抽出フォールバック
        return self._detect_cv_template(frame_bgr)

    def _detect_cv_template(self, frame_bgr: np.ndarray) -> List[Dict]:
        """TemplateMatcherに委譲。テンプレート未準備時は輪郭抽出フォールバック。"""
        if self.matcher.has_templates():
            return self.matcher.detect(frame_bgr)
        else:
            print("[ScreenCapturer] ⚠️ テンプレート未準備。輪郭抽出フォールバックで動作中。")
            print("手順: python desktop/setup_templates.py --sprite <スプライト画像>")
            return self.matcher._contour_fallback(frame_bgr)

    def _smooth(self) -> List[str]:
        """複数フレームで安定して検出された牌のみ返す"""
        counts: Dict[str, float] = {}
        for s in self.buffer:
            for d in s["tiles"]:
                tid = d.get("tile_id")
                if tid:
                    counts[tid] = counts.get(tid, 0.0) + d["conf"]
        return [tid for tid, score in counts.items() if score >= self.conf * 1.5]

    def extract_hand_tiles(self, hand_roi: dict = None) -> List[str]:
        """手牌エリアROIを指定して直接手牌牌IDリストを取得"""
        with mss.mss() as sct:
            frame_raw = np.array(sct.grab(self.roi))
            frame_bgr = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
        return self.matcher.extract_hand(frame_bgr, hand_roi or self.hand_roi)
