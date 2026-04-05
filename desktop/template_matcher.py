"""
desktop/template_matcher.py
OpenCVテンプレートマッチングによる麻雀牌認識
templates/ ディレクトリの画像を使って手牌・捨て牌を特定する。
"""
import cv2
import numpy as np
import os
import glob
from typing import List, Dict, Optional, Tuple


# 牌IDの並び順（全34種）
ALL_TILE_IDS = (
    ["1m","2m","3m","4m","5m","6m","7m","8m","9m",
     "1p","2p","3p","4p","5p","6p","7p","8p","9p",
     "1s","2s","3s","4s","5s","6s","7s","8s","9s",
     "1z","2z","3z","4z","5z","6z","7z"]
)


class TemplateMatcher:
    """
    templates/<tile_id>.png をロードし、スクリーン画像から牌を検出する。
    YOLO重みなしで動作するフォールバック実装。
    """

    def __init__(
        self,
        template_dir: str = "desktop/templates",
        conf_threshold: float = 0.70,
        tile_w_range: Tuple[int,int] = (30, 90),
        tile_h_range: Tuple[int,int] = (45, 130),
    ):
        self.template_dir = template_dir
        self.conf = conf_threshold
        self.tile_w_range = tile_w_range
        self.tile_h_range = tile_h_range
        self.templates: Dict[str, np.ndarray] = {}
        self._load_templates()

    # ------------------------------------------------------------------
    # テンプレートのロード
    # ------------------------------------------------------------------
    def _load_templates(self):
        """templates/<id>.png または <id>.jpg を全ロード"""
        if not os.path.isdir(self.template_dir):
            print(f"[TemplateMatcher] テンプレートディレクトリなし: {self.template_dir}")
            return

        loaded = 0
        for tile_id in ALL_TILE_IDS:
            for ext in ("png", "jpg", "jpeg"):
                path = os.path.join(self.template_dir, f"{tile_id}.{ext}")
                if os.path.exists(path):
                    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        self.templates[tile_id] = img
                        loaded += 1
                        break

        print(f"[TemplateMatcher] {loaded}/{len(ALL_TILE_IDS)} テンプレートロード完了")

    def has_templates(self) -> bool:
        return len(self.templates) > 0

    # ------------------------------------------------------------------
    # メイン検出
    # ------------------------------------------------------------------
    def detect(self, frame_bgr: np.ndarray) -> List[Dict]:
        """
        フレーム画像から牌を検出し、検出リストを返す。
        Returns: [{"tile_id": "5m", "conf": 0.85, "box": (x,y,w,h)}, ...]
        """
        if not self.has_templates():
            return self._contour_fallback(frame_bgr)

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        # コントラスト向上
        gray = cv2.equalizeHist(gray)

        results = []

        for tile_id, tmpl in self.templates.items():
            # 複数スケールでマッチング
            for scale in (0.8, 1.0, 1.2):
                h_t = int(tmpl.shape[0] * scale)
                w_t = int(tmpl.shape[1] * scale)
                if h_t < 10 or w_t < 10:
                    continue

                resized_tmpl = cv2.resize(tmpl, (w_t, h_t))
                if gray.shape[0] < h_t or gray.shape[1] < w_t:
                    continue

                res = cv2.matchTemplate(gray, resized_tmpl, cv2.TM_CCOEFF_NORMED)
                locs = np.where(res >= self.conf)

                for pt in zip(*locs[::-1]):  # (x, y)
                    score = float(res[pt[1], pt[0]])
                    results.append({
                        "tile_id": tile_id,
                        "conf": round(score, 3),
                        "box": (int(pt[0]), int(pt[1]), w_t, h_t),
                    })

        # NMS（重複除去）
        results = self._nms(results)
        # x座標でソート（手牌の左から右の順）
        results.sort(key=lambda r: r["box"][0])
        return results

    # ------------------------------------------------------------------
    # NMS (Non-Maximum Suppression)
    # ------------------------------------------------------------------
    def _nms(self, detections: List[Dict], iou_thr: float = 0.3) -> List[Dict]:
        if not detections:
            return []

        detections.sort(key=lambda d: d["conf"], reverse=True)
        kept = []

        for det in detections:
            x, y, w, h = det["box"]
            overlap = False
            for k in kept:
                kx, ky, kw, kh = k["box"]
                # IoU計算
                ix = max(x, kx)
                iy = max(y, ky)
                ix2 = min(x+w, kx+kw)
                iy2 = min(y+h, ky+kh)
                inter = max(0, ix2-ix) * max(0, iy2-iy)
                union = w*h + kw*kh - inter
                if union > 0 and inter/union > iou_thr:
                    overlap = True
                    break
            if not overlap:
                kept.append(det)

        return kept

    # ------------------------------------------------------------------
    # テンプレートなしのフォールバック（輪郭抽出）
    # ------------------------------------------------------------------
    def _contour_fallback(self, frame_bgr: np.ndarray) -> List[Dict]:
        """テンプレート未準備時: 輪郭抽出で牌らしい矩形を返す（tile_idは不明）"""
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results = []
        w_min, w_max = self.tile_w_range
        h_min, h_max = self.tile_h_range

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w_min < w < w_max and h_min < h < h_max and 0.55 < w/h < 0.90:
                results.append({
                    "tile_id": None,   # 未識別
                    "conf": 0.5,
                    "box": (x, y, w, h),
                })

        results.sort(key=lambda r: r["box"][0])
        return results

    # ------------------------------------------------------------------
    # 手牌の抽出（画面下部の特定エリアに絞る）
    # ------------------------------------------------------------------
    def extract_hand(
        self, frame_bgr: np.ndarray,
        hand_roi: Optional[Dict] = None
    ) -> List[str]:
        """
        画面の手牌エリアから牌IDリストを返す。
        hand_roi: {"x": 100, "y": 800, "w": 900, "h": 120}
        """
        if hand_roi:
            x, y, w, h = hand_roi["x"], hand_roi["y"], hand_roi["w"], hand_roi["h"]
            roi_frame = frame_bgr[y:y+h, x:x+w]
        else:
            # デフォルト: 画面下部25%
            H, W = frame_bgr.shape[:2]
            roi_frame = frame_bgr[int(H*0.75):H, :]

        detections = self.detect(roi_frame)
        # tile_id が取得できたものだけ返す
        hand = [d["tile_id"] for d in detections if d["tile_id"] is not None]
        return hand[:14]  # 最大14枚
