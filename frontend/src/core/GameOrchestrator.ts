// src/core/GameOrchestrator.ts
import { GameVisualLayer } from '../ui/GameVisualLayer';
import { HapticAudioManager } from '../audio/HapticAudioManager';
import { GameState, Tile } from '../types/gameState';

export class GameOrchestrator {
  private visuals: GameVisualLayer;
  private audio: HapticAudioManager;
  private isRunning = false;

  constructor(host: HTMLElement) {
    this.visuals = new GameVisualLayer(host);
    this.audio = HapticAudioManager.getInstance();
    this.audio.init();
    this.isRunning = true;
  }

  /**
   * 打牌イベントの統合処理
   */
  async handleDiscard(tile: Tile, el: HTMLElement, onConfirm: (t: Tile) => void) {
    if (!this.isRunning) return;
    
    // 1. 視覚演出の開始
    this.visuals.triggerEffect('discard');
    
    // 2. 確定音と振動
    this.audio.triggerFeedback('confirm');
    
    // 3. ロジック実行 (サーバーへのリクエスト等)
    onConfirm(tile);
  }

  /**
   * ドラッグ開始イベント
   */
  handleDragStart(el: HTMLElement, e: PointerEvent, ukeire: any[]) {
    if (!this.isRunning) return;
    this.visuals.startDrag(el, e.clientX, e.clientY);
    this.audio.triggerFeedback('grab'); // Changed from drag_start to grab for crisp feel
    
    // 受入情報の更新
    if (ukeire) {
      this.visuals.updateInfo(ukeire, new Set());
    }
  }

  /**
   * リーチ演出
   */
  triggerRiichiEffect() {
    this.audio.triggerFeedback('riichi');
    this.visuals.triggerEffect('riichi');
  }

  /**
   * 和了（ツモ・ロン）演出
   */
  triggerWinEffect(type: 'tsumo' | 'ron') {
    this.audio.triggerFeedback(type);
    this.visuals.triggerEffect(type);
  }

  /**
   * 思考時間の演出（間を作る）
   */
  async simulateThinking(baseTime: number = 800) {
    const jitter = Math.random() * 400;
    await new Promise(r => setTimeout(r, baseTime + jitter));
  }

  /**
   * 各種イベントへのフィードバック
   */
  triggerFeedback(event: 'tsumo' | 'ron' | 'snaps' | 'riichi') {
    if (event === 'snaps') {
        this.audio.triggerFeedback('snap');
        return;
    }
    this.visuals.triggerEffect(event as any);
    this.audio.triggerFeedback(event as any);
  }
}
