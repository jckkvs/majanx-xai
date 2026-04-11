interface ProgressData {
  rank: { points: number; division: string; games: number; avgRank: number };
  stats: { wins: number; draws: number; losses: number; totalScore: number };
  lastSeed: number;
}

export class LocalProgressEngine {
  private data: ProgressData = this._initData();
  private readonly STORAGE_KEY = 'majanx_offline_v1';

  private _initData(): ProgressData {
    return {
      rank: { points: 1000, division: '四段', games: 0, avgRank: 2.5 },
      stats: { wins: 0, draws: 0, losses: 0, totalScore: 0 },
      lastSeed: Date.now()
    };
  }

  async load(): Promise<void> {
    try {
      const raw = localStorage.getItem(this.STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        this.data = { ...this._initData(), ...parsed };
        this.data.rank = { ...this._initData().rank, ...parsed.rank };
        this.data.stats = { ...this._initData().stats, ...parsed.stats };
      }
    } catch {
      console.warn('[Progress] Load failed, using defaults');
    }
  }

  async save(): Promise<void> {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.data));
    } catch {
      console.error('[Progress] Storage full or blocked');
    }
  }

  applyResult(rank: number, scoreDiff: number, usedSeed: number): void {
    this.data.rank.games++;
    const delta = rank === 1 ? 20 : rank === 2 ? 5 : rank === 3 ? -10 : -25;
    this.data.rank.points = Math.max(0, this.data.rank.points + delta);
    this.data.rank.avgRank = ((this.data.rank.avgRank * (this.data.rank.games - 1)) + rank) / this.data.rank.games;
    
    if (rank === 1) this.data.stats.wins++;
    else if (rank === 4) this.data.stats.losses++;
    else this.data.stats.draws++;
    this.data.stats.totalScore += scoreDiff;

    this.data.lastSeed = usedSeed;
    this._updateDivision();
  }

  private _updateDivision(): void {
    const thresholds: [number, string][] = [
      [2000, '魂天'], [1700, '七段'], [1400, '六段'],
      [1100, '五段'], [800, '四段'], [500, '三段'], [0, '二段']
    ];
    this.data.rank.division = thresholds.find(([p]) => this.data.rank.points >= p)![1] as string;
  }

  getSnapshot() {
    return JSON.parse(JSON.stringify(this.data));
  }
}
