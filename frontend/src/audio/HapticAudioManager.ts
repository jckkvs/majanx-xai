// src/audio/HapticAudioManager.ts

export class HapticAudioManager {
  private static instance: HapticAudioManager;
  private ctx: AudioContext | null = null;
  private buffers: Record<string, AudioBuffer> = {};
  private gainNode: GainNode | null = null;
  private isInitialized = false;

  private constructor() {}

  static getInstance(): HapticAudioManager {
    if (!HapticAudioManager.instance) {
      HapticAudioManager.instance = new HapticAudioManager();
    }
    return HapticAudioManager.instance;
  }

  async init() {
    if (this.isInitialized) return;
    try {
      this.ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      this.gainNode = this.ctx.createGain();
      this.gainNode.connect(this.ctx.destination);
      
      // 合成的に基本音声を生成（デモ用、実運用時はアセットをロード）
      this._generateSyntheticSnap();
      
      this.isInitialized = true;
      console.log("[HapticAudioManager] Initialized.");
    } catch (e) {
      console.warn("[HapticAudioManager] Init failed:", e);
    }
  }

  private _generateSyntheticSnap() {
    if (!this.ctx) return;
    const bufferSize = this.ctx.sampleRate * 0.1;
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (this.ctx.sampleRate * 0.012));
    }
    this.buffers['snap'] = buffer;
  }

  play(event: string, intensity: number = 0.8) {
    if (!this.ctx || this.ctx.state === 'suspended') this.ctx?.resume();
    
    if (event === 'grab') {
        this._playGrab();
        return;
    }
    
    const buffer = this.buffers['snap']; // 現状は共通音
    if (!buffer || !this.ctx || !this.gainNode) return;

    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    
    // 音量減衰エンベロープ
    this.gainNode.gain.setValueAtTime(intensity, this.ctx.currentTime);
    this.gainNode.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.15);
    
    source.connect(this.gainNode);
    source.start(0);
  }

  private _playGrab() {
    if (!this.ctx) return;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, this.ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(1200, this.ctx.currentTime + 0.05);
    g.gain.setValueAtTime(0.05, this.ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.05);
    osc.connect(g);
    g.connect(this.ctx.destination);
    osc.start();
    osc.stop(this.ctx.currentTime + 0.05);
  }

  vibrate(pattern: number[]) {
    if ('vibrate' in navigator) {
      navigator.vibrate(pattern);
    }
    // Gamepad API integration (Placeholder logic)
    const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
    for (const gp of gamepads) {
      if (gp && (gp as any).hapticActuators && (gp as any).hapticActuators[0]) {
        (gp as any).hapticActuators[0].pulse(0.6, 150);
      }
    }
  }

  triggerFeedback(action: 'drag_start' | 'snap' | 'confirm' | 'danger' | 'ron' | 'tsumo' | 'grab' | 'riichi') {
    const map: Record<string, { play: string, vib: number[] }> = {
      grab: { play: 'grab', vib: [5] },
      drag_start: { play: 'grab', vib: [5] },
      snap: { play: 'snap', vib: [20] },
      confirm: { play: 'snap', vib: [15, 30, 15] },
      danger: { play: 'snap', vib: [10, 40, 10] },
      riichi: { play: 'snap', vib: [60, 100, 60] },
      ron: { play: 'snap', vib: [50, 20, 50] },
      tsumo: { play: 'snap', vib: [25, 15] }
    };
    const cfg = map[action];
    if (cfg) {
      this.play(cfg.play);
      this.vibrate(cfg.vib);
    }
  }
}
