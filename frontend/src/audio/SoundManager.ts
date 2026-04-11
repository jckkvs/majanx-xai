export class SoundManager {
  private static instance: SoundManager;
  private audioCtx: AudioContext | null = null;
  private buffers: Map<string, AudioBuffer> = new Map();
  private isInitialized = false;

  private constructor() {}

  static getInstance(): SoundManager {
    if (!SoundManager.instance) {
      SoundManager.instance = new SoundManager();
    }
    return SoundManager.instance;
  }

  async init() {
    if (this.isInitialized) return;
    try {
      this.audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      
      // Warm up audio context with a silent oscillator
      const osc = this.audioCtx.createOscillator();
      osc.connect(this.audioCtx.destination);
      osc.start(0);
      osc.stop(0.01);
      
      this.isInitialized = true;
      console.log("[SoundManager] Synthesizer context unlocked and ready.");
      
      // Pre-synth sounds if no external robust loaded assets are available
      this._generateSyntheticSnap();
    } catch (e) {
      console.warn("[SoundManager] Context initialization failed:", e);
    }
  }

  private _generateSyntheticSnap() {
    // Generate a quick percussive snap for a tile hit
    if (!this.audioCtx) return;
    const bufferSize = this.audioCtx.sampleRate * 0.05; // 50ms impulse
    const buffer = this.audioCtx.createBuffer(1, bufferSize, this.audioCtx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (this.audioCtx.sampleRate * 0.01)); // exponential decay
    }
    this.buffers.set('snap', buffer);
  }

  play(soundId: string, volume: number = 1.0) {
    if (!this.audioCtx || this.audioCtx.state !== 'running') return;
    const buffer = this.buffers.get(soundId);
    if (!buffer) return;

    const source = this.audioCtx.createBufferSource();
    source.buffer = buffer;
    
    const gainNode = this.audioCtx.createGain();
    gainNode.gain.value = volume;
    
    source.connect(gainNode);
    gainNode.connect(this.audioCtx.destination);
    
    source.start(0);
  }

  vibrate(pattern: number | number[]) {
    if (navigator.vibrate) {
      navigator.vibrate(pattern);
    }
  }

  // Sensory Macros
  onTilePickup() {
    this.vibrate([10]);
  }

  onTileSnapHover() {
    this.vibrate([15]);
  }

  onTileDiscard() {
    this.play('snap', 0.8);
    this.vibrate([40, 10, 10]);
  }

  onDangerWarning() {
    this.vibrate([15, 50, 15]);
  }
}
