export class WaitInfoOverlay {
  private el: HTMLElement;
  private isVisible = false;

  constructor(private host: HTMLElement) {
    this.el = document.createElement('div');
    Object.assign(this.el.style, {
      position: 'fixed', bottom: '28%', left: '50%', transform: 'translateX(-50%)',
      display: 'flex', gap: '6px', padding: '6px 10px', borderRadius: '8px',
      background: 'rgba(17,24,39,0.88)', backdropFilter: 'blur(4px)',
      opacity: '0', transition: 'opacity 0.2s ease, transform 0.2s ease',
      pointerEvents: 'none', zIndex: '950', willChange: 'opacity, transform'
    });
    this.host.appendChild(this.el);
  }

  update(waits: Array<{tile: string, remaining: number}>, dangerTiles: Set<string>) {
    if (waits.length === 0) return this.hide();
    
    this.el.innerHTML = '';
    waits.forEach(w => {
      const chip = document.createElement('span');
      chip.textContent = w.tile;
      chip.style.cssText = `
        font-size: 14px; color: #f3f4f6; font-weight: 500;
        ${dangerTiles.has(w.tile) ? 'color: #fca5a5; text-shadow: 0 0 4px rgba(239,68,68,0.6);' : ''}
      `;
      const rem = document.createElement('sub');
      rem.textContent = `(${w.remaining})`;
      rem.style.cssText = 'font-size: 10px; color: #9ca3af; margin-left: 2px;';
      chip.appendChild(rem);
      this.el.appendChild(chip);
    });

    this.el.style.opacity = '1';
    this.el.style.transform = 'translateX(-50%) translateY(0)';
    this.isVisible = true;
  }

  hide() {
    if (!this.isVisible) return;
    this.el.style.opacity = '0';
    this.el.style.transform = 'translateX(-50%) translateY(4px)';
    this.isVisible = false;
  }

  destroy() {
    this.el.remove();
    this.isVisible = false;
  }
}
