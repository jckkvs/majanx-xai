"""
desktop/setup_templates.py
------------------------------
スプライトシート画像から個別の牌テンプレート画像を切り出して
desktop/templates/ に保存するユーティリティ。

使い方:
    python desktop/setup_templates.py --sprite path/to/sprite.png

スプライトのレイアウト（デフォルト設定）:
    Row 0: 1m 2m 3m 4m 5m 6m 7m 8m 9m  (萬子)
    Row 1: 1p 2p 3p 4p 5p 6p 7p 8p 9p  (筒子)
    Row 2: 1s 2s 3s 4s 5s 6s 7s 8s 9s  (索子)
    Row 3: 1z 2z 3z 4z 5z 6z 7z         (字牌: 東南西北白發中)

共有画像（ユーザー収集のもの）を --sprite に指定すれば自動で切り出せる。
"""
import cv2
import numpy as np
import os
import argparse


# ---- デフォルトスプライトレイアウト ----
# 各行に含まれる tile_id の順番
SPRITE_LAYOUT = [
    # row 0: 萬子
    ["1m","2m","3m","4m","5m","6m","7m","8m","9m"],
    # row 1: 筒子
    ["1p","2p","3p","4p","5p","6p","7p","8p","9p"],
    # row 2: 索子
    ["1s","2s","3s","4s","5s","6s","7s","8s","9s"],
    # row 3: 字牌
    ["1z","2z","3z","4z","5z","6z","7z"],
]


def auto_detect_grid(img: np.ndarray, rows: int, max_cols: int):
    """
    画像の高さ・幅からタイルサイズを自動推定する。
    """
    H, W = img.shape[:2]
    tile_h = H // rows
    tile_w = W // max_cols
    return tile_h, tile_w


def extract_templates(
    sprite_path: str,
    out_dir: str = "desktop/templates",
    layout: list = None,
    tile_w: int = None,
    tile_h: int = None,
    padding: int = 2,
):
    """
    スプライトシートを切り出して templates/<id>.png に保存。
    """
    if layout is None:
        layout = SPRITE_LAYOUT

    img = cv2.imread(sprite_path)
    if img is None:
        print(f"[ERROR] 画像を読み込めません: {sprite_path}")
        return

    rows = len(layout)
    max_cols = max(len(row) for row in layout)

    if tile_h is None or tile_w is None:
        tile_h, tile_w = auto_detect_grid(img, rows, max_cols)
        print(f"[Info] タイルサイズ自動推定: {tile_w}x{tile_h} px")

    os.makedirs(out_dir, exist_ok=True)
    saved = 0

    for row_idx, row_tiles in enumerate(layout):
        for col_idx, tile_id in enumerate(row_tiles):
            x = col_idx * tile_w + padding
            y = row_idx * tile_h + padding
            w = tile_w - padding * 2
            h = tile_h - padding * 2

            # 画像範囲チェック
            if y + h > img.shape[0] or x + w > img.shape[1]:
                print(f"[WARN] 範囲外: {tile_id} ({x},{y},{w},{h})")
                continue

            tile_img = img[y:y+h, x:x+w]
            out_path = os.path.join(out_dir, f"{tile_id}.png")
            cv2.imwrite(out_path, tile_img)
            print(f"  保存: {out_path}")
            saved += 1

    print(f"\n[完了] {saved}枚のテンプレートを {out_dir}/ に保存しました。")


def verify_templates(out_dir: str = "desktop/templates"):
    """保存したテンプレートを小さなウィンドウで確認する"""
    files = sorted([f for f in os.listdir(out_dir) if f.endswith(".png")])
    if not files:
        print("[ERROR] テンプレートが見つかりません")
        return

    # 横並びのプレビュー画像を作成
    imgs = []
    for f in files:
        img = cv2.imread(os.path.join(out_dir, f))
        if img is not None:
            img = cv2.resize(img, (50, 70))
            imgs.append(img)

    if imgs:
        preview = np.hstack(imgs)
        cv2.imshow("Template Preview", preview)
        print("Press any key to close preview...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="麻雀牌スプライト切り出しツール")
    parser.add_argument("--sprite", required=True, help="スプライトシート画像のパス")
    parser.add_argument("--out", default="desktop/templates", help="出力ディレクトリ")
    parser.add_argument("--tile-w", type=int, default=None, help="タイル幅(px)。省略時は自動推定")
    parser.add_argument("--tile-h", type=int, default=None, help="タイル高さ(px)。省略時は自動推定")
    parser.add_argument("--padding", type=int, default=2, help="タイル間のパディング(px)")
    parser.add_argument("--verify", action="store_true", help="切り出し後にプレビュー表示")
    args = parser.parse_args()

    extract_templates(
        sprite_path=args.sprite,
        out_dir=args.out,
        tile_w=args.tile_w,
        tile_h=args.tile_h,
        padding=args.padding,
    )

    if args.verify:
        verify_templates(args.out)
