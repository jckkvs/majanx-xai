import { GameState } from '../types/gameState';

export class TileIntelligence {
  /**
   * 見えている枚数（手牌、河、副露、ドラ表示牌）から、壁に残っている枚数を計算
   */
  static getRemainingCount(tileId: string, state: GameState): int {
    let visible = 0;
    
    // 赤ドラの区別を除去してカウント
    const baseId = tileId.replace('r', '');

    // 自分の手牌
    state.hand.forEach(t => {
      if (t.id.replace('r', '') === baseId) visible++;
    });

    // 河 (全プレイヤー)
    state.river.forEach(entry => {
      if (entry.tile.id.replace('r', '') === baseId) visible++;
    });

    // 副露 (全プレイヤー)
    state.players.forEach(p => {
      p.melds.forEach(m => {
        m.tiles.forEach(t => {
          if (t.id.replace('r', '') === baseId) visible++;
        });
      });
    });

    // ドラ表示牌
    state.doraIndicators.forEach(t => {
      if (t.id.replace('r', '') === baseId) visible++;
    });

    return Math.max(0, 4 - visible);
  }
}
