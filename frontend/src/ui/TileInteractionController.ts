export class TileInteractionController {
  private isDragging = false;
  private activeEl: HTMLElement | null = null;
  private tileId: string | null = null;
  private startX = 0; 
  private startY = 0;
  private readonly THRESHOLD = 6;
  private readonly CANCEL_ZONE = 0.15;

  constructor(
    private host: HTMLElement,
    private onDiscard: (id: string) => void,
    private updateOverlay: (tileId: string | null, isDanger: boolean) => void
  ) {
    this.down = this.down.bind(this); 
    this.move = this.move.bind(this); 
    this.up = this.up.bind(this);
    host.addEventListener('pointerdown', this.down, { passive: false });
    window.addEventListener('pointermove', this.move, { passive: false });
    window.addEventListener('pointerup', this.up);
  }

  private down(e: PointerEvent) {
    const el = (e.target as HTMLElement).closest('[data-tile]') as HTMLElement;
    if (!el || !el.dataset.tile) return;
    e.preventDefault();
    el.setPointerCapture(e.pointerId);
    this.activeEl = el; 
    this.tileId = el.dataset.tile;
    this.startX = e.clientX; 
    this.startY = e.clientY;
    this.isDragging = false;
    this.updateOverlay(this.tileId, false);
  }

  private move(e: PointerEvent) {
    if (!this.activeEl) return;
    const dx = e.clientX - this.startX;
    const dy = e.clientY - this.startY;
    const dist = Math.hypot(dx, dy);

    if (!this.isDragging && dist >= this.THRESHOLD) {
      this.isDragging = true;
      this.activeEl.style.transition = 'none';
      this.activeEl.style.zIndex = '1000';
    }

    if (this.isDragging) {
      this.activeEl.style.transform = `translate(${dx}px, ${dy}px) scale(1.03)`;
      const isCancel = e.clientY > window.innerHeight * (1 - this.CANCEL_ZONE);
      this.activeEl.style.boxShadow = isCancel
        ? '0 0 0 3px rgba(239,68,68,0.85)'
        : (dy < -12 ? '0 0 0 3px rgba(34,197,94,0.85)' : '0 4px 12px rgba(0,0,0,0.25)');
    }
  }

  private up(e: PointerEvent) {
    if (!this.isDragging || !this.activeEl || !this.tileId) return this.reset();
    const isCancel = (ev: PointerEvent) => ev.clientY > window.innerHeight * (1 - this.CANCEL_ZONE);
    if (!isCancel(e)) this.onDiscard(this.tileId);
    this.revert();
  }

  private revert() {
    if (!this.activeEl) return;
    this.activeEl.style.transition = 'transform 0.14s cubic-bezier(0.34,1.56,0.64,1)';
    this.activeEl.style.transform = 'translate(0,0)';
    this.activeEl.style.boxShadow = ''; 
    this.activeEl.style.zIndex = '';
    
    // Explicitly cache element due to timeout async execution
    const elToClear = this.activeEl;
    setTimeout(() => { if (elToClear) elToClear.style.transition = ''; }, 140);
    
    this.updateOverlay(null, false);
    this.reset();
  }

  private reset() {
    this.isDragging = false; 
    this.activeEl = null; 
    this.tileId = null;
  }

  destroy() {
    this.host.removeEventListener('pointerdown', this.down);
    window.removeEventListener('pointermove', this.move);
    window.removeEventListener('pointerup', this.up);
    this.reset();
  }
}
