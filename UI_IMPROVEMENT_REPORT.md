
# MajanX-XAI アプリの問題点と改善提案

## 📋 現状分析

### 1. 画像素材の問題
- **スプライトシートの不整合**: 
  - 画像サイズ：757x484px
  - CSS 設定：10 カラム×4 行（40 スロット）
  - 各セル：約 75.7x121px（端数切り捨てにより位置ずれ発生）
  
- **座標計算の精度問題**:
  - CSS: `background-position-x: 11.111%` など百分率使用
  - 757px を 10 等分すると 75.7px で整数にならない
  - 牌の表示位置が微妙にずれる可能性

### 2. UI/UX の問題点

#### デザイン面:
- 雀魂との比較で劣る点:
  1. 牌の質感・立体感不足
  2. アニメーションの滑らかさ
  3. 光のエフェクト（グロー、シャドウ）
  4. 背景の卓デザイン
  5. スコア表示の視認性

#### 操作性:
  1. 牌選択時のフィードバックが弱い
  2. 鳴き UI の完成度
  3. リーチ表示の派手さ不足
  4. 和了時エフェクト

### 3. コード構造の問題

#### CSS (style.css):
- 924 行の大規模ファイルで管理困難
- 重複スタイルが多い
- 変数定義が散在
- レスポンシブ対応が不十分

#### JavaScript (game.js):
- 578 行で複雑化
- エラーハンドリング不足
- WebSocket 再接続ロジックが単純
- AI 推奨表示のロジックが複雑

### 4. パフォーマンス問題
- 牌描画時の DOM 操作過多
- アニメーションの最適化不足
- WebSocket メッセージの最適化余地

## 🎯 雀魂なみの UI への改善案

### 短期改善（1-2 週間）:

1. **スプライトシートの修正**:
   - 画像を 760x484 にリサイズ（76px/cell で整数化）
   - または CSS をピクセル指定に変更
   
2. **牌のエフェクト強化**:
   ```css
   .tile {
     filter: drop-shadow(0 2px 4px rgba(0,0,0,0.4));
     transition: transform 0.15s cubic-bezier(0.4, 0, 0.2, 1);
   }
   .tile:hover {
     transform: translateY(-8px) scale(1.05);
     filter: drop-shadow(0 8px 16px rgba(212,168,83,0.6));
   }
   ```

3. **アニメーション改善**:
   - 打牌時の軌跡アニメーション
   - 摸球時の跳ねアニメーション
   - リーチ宣言時のエフェクト

### 中期改善（1 ヶ月）:

1. **高品質な牌画像の作成**:
   - Illustrator/Photoshop で新規作成
   - 3D レンダリングの検討
   - 各牌 100x140px 程度で統一

2. **UI コンポーネントの再設計**:
   - React/Vue などのフレームワーク導入
   - コンポーネント指向の設計
   - ステート管理の最適化

3. **サウンド実装**:
   - 打牌音
   - 摸球音
   - リーチ宣言
   - 和了効果音

### 長期改善（3 ヶ月〜）:

1. **WebGL/Canvas レンダリング**:
   - Three.js による 3D 牌卓
   - GPU アクセラレーション
   - 60fps アニメーション

2. **モバイル最適化**:
   - タッチ操作対応
   - レスポンシブデザインの強化
   - PWA 対応

## 🔧 具体的な修正コード例

### 1. スプライトシート座標の修正 (CSS):
```css
:root {
  /* 760x484 を想定（10x4 グリッド） */
  --tile-sprite-width: 760px;
  --tile-sprite-height: 484px;
  --tile-cell-width: 76px;
  --tile-cell-height: 121px;
}

.tile-sprite {
  width: var(--tile-width);
  height: var(--tile-height);
  background-image: url('../img/majang-hai.png');
  background-size: var(--tile-sprite-width) var(--tile-sprite-height);
  /* 百分率ではなくピクセル計算 */
  background-position: calc(var(--col) * -1 * var(--tile-cell-width)) 
                       calc(var(--row) * -1 * var(--tile-cell-height));
}
```

### 2. 牌のホバーエフェクト強化:
```css
.tile {
  position: relative;
  transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 
    0 4px 8px rgba(0,0,0,0.3),
    inset 0 1px 0 rgba(255,255,255,0.3);
}

.tile::before {
  /* 高光沢エフェクト */
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 40%;
  background: linear-gradient(
    to bottom,
    rgba(255,255,255,0.4) 0%,
    rgba(255,255,255,0.1) 100%
  );
  border-radius: 4px 4px 50% 50%;
  pointer-events: none;
}

.tile:hover {
  transform: translateY(-10px) scale(1.08);
  box-shadow: 
    0 12px 24px rgba(0,0,0,0.4),
    0 0 20px rgba(212,168,83,0.5),
    inset 0 1px 0 rgba(255,255,255,0.5);
  z-index: 100;
}
```

### 3. 打牌アニメーション:
```css
@keyframes discardFly {
  0% {
    opacity: 1;
    transform: translateY(0) rotate(0deg);
  }
  100% {
    opacity: 0;
    transform: translateY(-60px) translateX(20px) rotate(15deg);
  }
}

.tile.discard-animate {
  animation: discardFly 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}
```

## 📊 優先順位

| 優先度 | 項目 | 工数 | 影響度 |
|--------|------|------|--------|
| 🔴 高 | スプライト座標修正 | 2h | 大 |
| 🔴 高 | 牌ホバーエフェクト | 4h | 中 |
| 🟡 中 | 打牌アニメーション | 8h | 中 |
| 🟡 中 | AI 推奨表示 UI | 16h | 大 |
| 🟢 低 | 新スプライト作成 | 40h | 大 |
| 🟢 低 | フレームワーク移行 | 80h | 大 |

