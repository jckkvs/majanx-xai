// frontend/src/core/StateTransitionManager.ts
export class StateTransitionManager {
  private isBusy = false;
  private readonly FADE_MS = 240;
  private pendingQueue: Array<() => Promise<void>> = [];
  private currentEl: HTMLElement | null = null;

  constructor(private host: HTMLElement) {}

  async transition(renderNext: (container: HTMLElement) => Promise<void>): Promise<void> {
    return new Promise(resolve => {
      this.pendingQueue.push(async () => {
        if (this.isBusy) return;
        this.isBusy = true;
        try {
          const next = this.host.cloneNode(true) as HTMLElement;
          Object.assign(next.style, {
            position: 'absolute', top: '0', left: '0', width: '100%', height: '100%',
            opacity: '0', pointerEvents: 'none', willChange: 'opacity'
          });
          this.host.style.position = 'relative';
          this.host.appendChild(next);
          this.currentEl = next;

          await new Promise(r => requestAnimationFrame(() => setTimeout(r, 24)));
          await renderNext(next);

          const old = this.host.firstElementChild as HTMLElement;
          if (old) {
            await Promise.all([this.animateFade(old, 1, 0), this.animateFade(next, 0, 1)]);
            if (old.parentNode) old.parentNode.removeChild(old);
          } else {
            await this.animateFade(next, 0, 1);
          }

          next.style.position = ''; next.style.opacity = '';
          next.style.pointerEvents = ''; next.style.willChange = '';
          this.currentEl = null;
        } catch (err) {
          console.error('[Transition] Render failed, forcing cleanup', err);
          if (this.currentEl?.parentNode) this.currentEl.parentNode.removeChild(this.currentEl);
          this.currentEl = null;
        } finally {
          this.isBusy = false;
          resolve();
        }
      });
      if (this.pendingQueue.length === 1) this.processQueue();
    });
  }

  private async processQueue() {
    while (this.pendingQueue.length > 0) {
        const task = this.pendingQueue.shift();
        if (task) await task();
    }
  }

  private animateFade(el: HTMLElement, from: number, to: number): Promise<void> {
    return new Promise(r => {
      el.style.transition = `opacity ${this.FADE_MS}ms cubic-bezier(0.4, 0.0, 0.2, 1)`;
      el.style.opacity = String(from);
      requestAnimationFrame(() => {
        el.style.opacity = String(to);
        setTimeout(r, this.FADE_MS);
      });
    });
  }

  destroy() {
    this.pendingQueue.length = 0;
    if (this.currentEl?.parentNode) this.currentEl.parentNode.removeChild(this.currentEl);
    this.isBusy = false;
  }
}
