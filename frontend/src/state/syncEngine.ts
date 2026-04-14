// src/state/syncEngine.ts
import { GameState, StateDelta, ServerAction } from '../types/gameState';

export function reconcileGameState(snapshot: GameState): GameState {
    // サーバーの完全なスナップショットをそのままローカル状態として適用
    return JSON.parse(JSON.stringify(snapshot)); // 深いコピーで不変性確保
}

export function applyDelta(state: GameState, delta: StateDelta): GameState {
    // サーバーからの一部の差分だけをマージ
    return {
        ...state,
        ...delta.changes,
        turn: delta.turn,
        serverHash: delta.hash,
        lastConfirmedTurn: delta.turn
    };
}

export function applyLocalPrediction(state: GameState, action: any): GameState {
    // オプティミスティック更新。たとえば手牌から打牌を一時的に消す。
    if (action.type === 'DISCARD') {
        const newHand = state.hand.filter(t => t.id !== action.payload.tileId);
        return {
            ...state,
            hand: newHand,
            actionPhase: 'waiting'
        };
    }
    return state;
}
