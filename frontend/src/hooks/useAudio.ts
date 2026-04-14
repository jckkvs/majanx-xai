import { useState, useRef, useEffect } from 'react';

export interface AudioSFXPresets {
  draw: { freq: number; type: OscillatorType; dur: number };
  discard: { freq: number; type: OscillatorType; dur: number };
  ai_ready: { freq: number; type: OscillatorType; dur: number };
  error: { freq: number; type: OscillatorType; dur: number };
}

export const useGameAudio = () => {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);

  const initAudioCtx = () => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }
  };

  // 操作サウンド（Web Audio API によるゼロレイテンシー生成）
  const playSFX = (type: keyof AudioSFXPresets) => {
    initAudioCtx();
    const ctx = audioCtxRef.current!;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    
    osc.connect(gain);
    gain.connect(ctx.destination);

    const presets: AudioSFXPresets = {
      draw: { freq: 880, type: 'sine', dur: 0.08 },
      discard: { freq: 660, type: 'triangle', dur: 0.1 },
      ai_ready: { freq: 1200, type: 'sine', dur: 0.15 },
      error: { freq: 220, type: 'sawtooth', dur: 0.2 }
    };

    const p = presets[type] || presets.error;
    osc.frequency.setValueAtTime(p.freq, ctx.currentTime);
    osc.type = p.type;
    gain.gain.setValueAtTime(0.1, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + p.dur);
    
    osc.start();
    osc.stop(ctx.currentTime + p.dur);
  };

  // 解説音声読み上げ
  const speakExplanation = (text: string) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = 'ja-JP';
    utter.rate = 0.95;
    utter.pitch = 1.0;
    
    utter.onstart = () => setIsSpeaking(true);
    utter.onend = () => setIsSpeaking(false);
    utter.onerror = () => setIsSpeaking(false);
    
    window.speechSynthesis.speak(utter);
  };

  const stopSpeaking = () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  };

  return { isSpeaking, playSFX, speakExplanation, stopSpeaking };
};
