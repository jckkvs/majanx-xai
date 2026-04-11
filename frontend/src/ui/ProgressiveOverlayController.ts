export class ProgressiveOverlayController {
  private overlayElements: HTMLElement[] = [];
  private thresholdDistance = 150; // pixels
  private pointerPos = { x: -1000, y: -1000 };

  constructor() {
    this.handlePointerMove = this.handlePointerMove.bind(this);
    window.addEventListener('pointermove', this.handlePointerMove, { passive: true });
    this._startLoop();
  }

  registerElement(el: HTMLElement, layerType: 'Core' | 'Contextual' | 'OnDemand') {
    // Only Contextual and OnDemand fade
    if (layerType === 'Core') return;
    el.style.transition = 'opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1)';
    el.dataset.layerType = layerType;
    this.overlayElements.push(el);
  }

  unregisterElement(el: HTMLElement) {
    this.overlayElements = this.overlayElements.filter(e => e !== el);
  }

  private handlePointerMove(e: PointerEvent) {
    this.pointerPos.x = e.clientX;
    this.pointerPos.y = e.clientY;
  }

  private _startLoop() {
    const checkProximity = () => {
      this.overlayElements.forEach(el => {
        const rect = el.getBoundingClientRect();
        const center = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
        const dist = Math.hypot(center.x - this.pointerPos.x, center.y - this.pointerPos.y);

        if (dist > this.thresholdDistance) {
          // pointer is far, dim down the element aggressively
          el.style.opacity = el.dataset.layerType === 'OnDemand' ? '0.0' : '0.3';
          el.style.pointerEvents = el.dataset.layerType === 'OnDemand' ? 'none' : 'auto';
        } else {
          // pointer is near, bring focus
          el.style.opacity = '1';
          el.style.pointerEvents = 'auto';
        }
      });
      requestAnimationFrame(checkProximity);
    };
    requestAnimationFrame(checkProximity);
  }

  cleanup() {
    window.removeEventListener('pointermove', this.handlePointerMove);
  }
}
