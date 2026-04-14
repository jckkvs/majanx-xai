// src/ui/GameVisualLayer.ts

export class GameVisualLayer {
  private overlay: HTMLElement;
  private activeDrag: {el: HTMLElement; startX: number; startY: number} | null = null;

  constructor(private host: HTMLElement) {
    this.overlay = this.createOverlay();
    this.host.appendChild(this.overlay);
    this.bindGlobalEvents();
  }

  private createOverlay(): HTMLElement {
    const el = document.createElement('div');
    Object.assign(el.style, {
      position: 'fixed', bottom: '26%', left: '50%', transform: 'translateX(-50%)',
      display: 'flex', gap: '6px', padding: '6px 10px', borderRadius: '8px',
      background: 'rgba(17,24,39,0.88)', backdropFilter: 'blur(4px)',
      opacity: '0', transition: 'opacity 0.18s ease, transform 0.18s ease', 
      pointerEvents: 'none', zIndex: '950'
    });
    return el;
  }

  private bindGlobalEvents() {
    window.addEventListener('pointermove', e => {
      if (!this.activeDrag) return;
      const dx = e.clientX - this.activeDrag.startX;
      const dy = e.clientY - this.activeDrag.startY;
      
      // GPU加速を使用したトランスフォーム
      this.activeDrag.el.style.transform = `translate(${dx}px, ${dy}px) scale(1.05)`;
      
      const isDiscardZone = dy < -20;
      this.overlay.style.opacity = isDiscardZone ? '1' : '0.2';
      this.overlay.style.transform = `translateX(-50%) translateY(${isDiscardZone ? 0 : 5}px)`;
    });

    window.addEventListener('pointerup', () => {
      if (this.activeDrag) {
        this.activeDrag.el.style.transition = 'transform 0.15s cubic-bezier(0.34,1.56,0.64,1)';
        this.activeDrag.el.style.transform = 'translate(0,0)';
        this.activeDrag.el.style.zIndex = '';
        
        const elToClear = this.activeDrag.el;
        setTimeout(() => { if (elToClear) elToClear.style.transition = ''; }, 150);
        
        this.activeDrag = null;
        this.overlay.style.opacity = '0';
      }
    });
  }

  startDrag(el: HTMLElement, startX: number, startY: number) {
    this.activeDrag = {el, startX, startY};
    el.setPointerCapture(1); // Pointer ID stub
    el.style.transition = 'none';
    el.style.zIndex = '1000';
  }

  updateInfo(waits: {tile: string; remaining: number}[], dangerSet: Set<string>) {
    this.overlay.innerHTML = '';
    if (waits.length === 0) {
        this.overlay.style.opacity = '0';
        return;
    }
    
    waits.forEach(w => {
      const s = document.createElement('span');
      s.textContent = `${w.tile}(${w.remaining})`;
      s.style.cssText = `
        font-size: 13px; 
        color: ${dangerSet.has(w.tile) ? '#fca5a5' : '#f3f4f6'}; 
        font-weight: 500;
        text-shadow: 0 1px 2px rgba(0,0,0,0.5);
      `;
      this.overlay.appendChild(s);
    });
  }

  triggerEffect(type: 'tsumo' | 'ron' | 'discard' | 'riichi') {
    if (type === 'riichi') {
      this._triggerRiichiZoom();
      return;
    }
    
    const fx = document.createElement('div');
    const color = (type === 'ron' || type === 'tsumo') ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.1)';
    fx.style.cssText = `
        position: fixed; inset: 0; 
        background: ${color}; 
        opacity: 0; pointer-events: none; 
        transition: opacity 0.5s cubic-bezier(0.16, 1, 0.3, 1); z-index: 999;
    `;
    document.body.appendChild(fx);
    
    if (type === 'tsumo') {
        this._createParticles();
    }

    requestAnimationFrame(() => {
        fx.style.opacity = '1';
        setTimeout(() => {
            fx.style.opacity = '0';
            setTimeout(() => fx.remove(), 500);
        }, 100);
    });
  }

  private _triggerRiichiZoom() {
    this.host.style.transition = 'transform 0.8s cubic-bezier(0.33, 1, 0.68, 1)';
    this.host.style.transform = 'scale(1.15) translateY(20px)';
    
    // 画面の縁を暗くするビネット
    const vignette = document.createElement('div');
    vignette.style.cssText = `
        position: fixed; inset: 0; 
        background: radial-gradient(circle, transparent 40%, rgba(0,0,0,0.6) 100%);
        opacity: 0; pointer-events: none; transition: opacity 0.8s; z-index: 900;
    `;
    document.body.appendChild(vignette);

    requestAnimationFrame(() => {
        vignette.style.opacity = '1';
        setTimeout(() => {
           this.host.style.transform = '';
           vignette.style.opacity = '0';
           setTimeout(() => vignette.remove(), 800);
        }, 3000);
    });
  }

  private _createParticles() {
    for (let i = 0; i < 20; i++) {
        const p = document.createElement('div');
        const size = Math.random() * 8 + 4;
        p.style.cssText = `
            position: fixed; top: 50%; left: 50%;
            width: ${size}px; height: ${size}px; background: #4ecca3;
            border-radius: 50%; pointer-events: none; z-index: 1001;
            box-shadow: 0 0 10px #4ecca3;
        `;
        document.body.appendChild(p);
        
        const angle = Math.random() * Math.PI * 2;
        const dist = Math.random() * 200 + 100;
        const tx = Math.cos(angle) * dist;
        const ty = Math.sin(angle) * dist;
        
        p.animate([
            { transform: 'translate(-50%, -50%) scale(1)', opacity: 1 },
            { transform: `translate(calc(-50% + ${tx}px), calc(-50% + ${ty}px)) scale(0)`, opacity: 0 }
        ], {
            duration: 800 + Math.random() * 400,
            easing: 'cubic-bezier(0.16, 1, 0.3, 1)',
            fill: 'forwards'
        }).onfinish = () => p.remove();
    }
  }
}
