// src/state/gameStore.ts
import { create } from 'zustand';
import { reconcileGameState, applyDelta, applyLocalPrediction } from './syncEngine';
import { GameState, StateDelta } from '../types/gameState';

export interface ServerUpdate {
    fullSnapshot?: boolean;
    snapshot?: GameState;
    delta?: StateDelta;
}

export interface ClientAction {
    type: string;
    payload: any;
}

interface GameStoreState extends GameState {
  pendingReconciliation: boolean;
  syncFromServer: (payload: ServerUpdate) => void;
  predictLocal: (action: ClientAction) => void;
  rollback: (serverState: GameState) => void;
  _interpolateFrom?: GameState;
  _interpolateTo?: GameState;
  appMode: 'PLAY' | 'LEARN';
  setAppMode: (mode: 'PLAY' | 'LEARN') => void;
  completeExplanation: any | null; // 前回のターンで追加したもの
}

const initialState: GameState = {
  turn: 0,
  dealer: 0,
  honba: 0,
  kyoku: 1,
  scores: {},
  players: [],
  hand: [],
  river: [],
  doraIndicators: [],
  riichiSticks: 0,
  actionPhase: 'waiting',
  timerMs: 0,
  serverHash: '',
  lastConfirmedTurn: 0
};

export const useGameStore = create<GameStoreState>((set, get) => ({
  ...initialState,
  pendingReconciliation: false,
  syncFromServer: (payload) => set((state) => {
    if (payload.fullSnapshot && payload.snapshot) {
        return { ...reconcileGameState(payload.snapshot), pendingReconciliation: false };
    }
    if (payload.delta) {
        return applyDelta(state, payload.delta);
    }
    return state;
  }),
  predictLocal: (action) => set((state) => applyLocalPrediction(state, action)),
  rollback: (serverState) => set((state) => ({
    ...reconcileGameState(serverState),
    pendingReconciliation: true,
    _interpolateFrom: { ...state },
    _interpolateTo: serverState
  })),
  appMode: 'LEARN',
  setAppMode: (mode) => set({ appMode: mode }),
  completeExplanation: null
}));
