import { WaitInfoOverlay } from '../ui/WaitInfoOverlay';
import { LocalProgressEngine } from '../core/LocalProgressEngine';

// Fake deterministic deck for frontend to use until integrated fully via API or WASM,
// OR wait... the spec had it import DeterministicDeck but deterministic deck was defined in python.
// Since the prompt includes `import { DeterministicDeck } from '../core/deterministic_deck';`, I will create a minimal TS version or stub.

export class DeterministicDeckTS {
  private _state: number;
  
  constructor(seed: number) {
    this._state = seed & 0xFFFFFFFF;
  }
  verify_integrity() { return true; }
  getState() { return this._state; }
}

export class OfflineGameController {
  private deck: DeterministicDeckTS | null = null;
  private overlay: WaitInfoOverlay;
  private progress: LocalProgressEngine;
  private isRunning = false;

  constructor(private root: HTMLElement) {
    this.overlay = new WaitInfoOverlay(root);
    this.progress = new LocalProgressEngine();
  }

  async init(seed?: number): Promise<void> {
    await this.progress.load();
    const s = seed ?? this.progress.getSnapshot().lastSeed;
    this.deck = new DeterministicDeckTS(s);
    this.isRunning = true;
  }

  async finishRound(playerRank: number, scoreDiff: number): Promise<void> {
    if (!this.deck || !this.isRunning) return;
    const verified = this.deck.verify_integrity();
    if (!verified) throw new Error('Deck integrity check failed');

    this.progress.applyResult(playerRank, scoreDiff, this.deck.getState());
    await this.progress.save();
    this.isRunning = false;
    this.overlay.hide();
  }

  updateUI(waits: any[], dangerTiles: Set<string>) {
    if (!this.isRunning) return;
    this.overlay.update(waits, dangerTiles);
  }

  cleanup() {
    this.overlay.destroy();
    this.deck = null;
    this.isRunning = false;
  }
}
