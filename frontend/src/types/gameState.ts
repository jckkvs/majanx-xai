// src/types/gameState.ts

export interface Tile {
    id: string; // e.g., "1m", "5p"
    isAka?: boolean;
}

export interface PlayerState {
    seat: number;
    score: number;
    isRiichi: boolean;
    wind: string;
    melds: any[]; 
    discards: Tile[];
}

export interface RiverEntry {
    tile: Tile;
    danger: number; // 0.0 to 1.0
}

export interface GameState {
  turn: number;
  dealer: number;
  honba: number;
  kyoku: number;
  scores: Record<number, number>;
  players: PlayerState[];
  hand: Tile[];
  river: RiverEntry[][]; // 4 players' rivers
  doraIndicators: Tile[];
  riichiSticks: number;
  actionPhase: 'waiting' | 'draw' | 'discard' | 'call' | 'ron' | 'result';
  timerMs: number;
  serverHash: string;
  lastConfirmedTurn: number;
  discardOptions?: Record<string, {
    shanten: number;
    ukeire_count: number;
    waits: string[];
  }>;
  completeExplanation?: {
    recommended_move: string;
    technical_factors: any[];
    strategic_factors: any[];
    summary: { one_liner: string; full_paragraph: string; };
    confidence_score: number;
    alternative_moves: any[];
  };
}

export interface ServerAction {
    type: string;
    payload: any;
}

export interface StateDelta {
  turn: number;
  hash: string;
  changes: Partial<GameState>;
  actions: ServerAction[];
}
