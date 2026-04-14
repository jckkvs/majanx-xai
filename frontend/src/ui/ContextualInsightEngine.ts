// frontend/src/ui/ContextualInsightEngine.ts
export class ContextualInsightEngine {
  private overlay: HTMLElement | null = null;
  private timeoutId: ReturnType<typeof setTimeout> | null = null;
  private isEnabled = false;
  private readonly DURATION = 3000;

  constructor(private host: HTMLElement) {
    try { this.isEnabled = localStorage.getItem('majanx:insight_enabled') === 'true'; } catch { this.isEnabled = false; }
    
    this.overlay = document.createElement('div');
    Object.assign(this.overlay.style, {
      position: 'absolute', bottom: '20%', left: '50%', transform: 'translateX(-50%)',
      background: 'rgba(20,24,32,0.92)', color: '#e5e7eb', padding: '8px 16px',
      borderRadius: '8px', fontSize: '14px', pointerEvents: 'none', opacity: '0',
      transition: 'opacity 0.3s ease', whiteSpace: 'nowrap', zIndex: '900'
    });
    this.host.appendChild(this.overlay);
  }

  toggle() {
    this.isEnabled = !this.isEnabled;
    try { localStorage.setItem('majanx:insight_enabled', String(this.isEnabled)); } catch {}
    if (!this.isEnabled && this.overlay) this.overlay.style.opacity = '0';
  }

  show(message: string) {
    if (!this.isEnabled || !this.overlay) return;
    if (this.timeoutId) clearTimeout(this.timeoutId);
    this.overlay.textContent = message;
    this.overlay.style.opacity = '1';
    this.timeoutId = setTimeout(() => { if (this.overlay) this.overlay.style.opacity = '0'; }, this.DURATION);
  }

  destroy() {
    if (this.timeoutId) clearTimeout(this.timeoutId);
    this.overlay?.remove();
    this.overlay = null;
  }
}
