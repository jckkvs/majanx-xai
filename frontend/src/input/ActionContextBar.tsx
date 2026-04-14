// src/input/ActionContextBar.tsx
import React from 'react';
import { useGameStore } from '../state/gameStore';

import { ProgressiveOverlayController } from '../ui/ProgressiveOverlayController';

export const ActionContextBar: React.FC<{ containerRef: React.RefObject<ProgressiveOverlayController | null> }> = ({ containerRef }) => {
    const actionPhase = useGameStore(state => state.actionPhase);
    const timerMs = useGameStore(state => state.timerMs);
    const elRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        if (elRef.current && containerRef.current) {
            containerRef.current.registerElement(elRef.current, 'Contextual');
        }
    }, [containerRef]);

    if (actionPhase !== 'call' && actionPhase !== 'discard') {
        return null; // Only show when call or discard phase
    }

    const timerColor = timerMs > 5000 ? 'green' : timerMs > 3000 ? 'yellow' : 'red';

    return (
        <div ref={elRef} style={{
            position: 'absolute',
            bottom: '100px',
            left: '50%',
            transform: 'translateX(-50%)',
            display: 'flex',
            gap: '12px',
            background: 'rgba(0,0,0,0.6)',
            padding: '10px 20px',
            borderRadius: '8px'
        }}>
            {/* Timer visual */}
            <div style={{ width: '20px', height: '20px', borderRadius: '50%', backgroundColor: timerColor }} />
            
            <button style={{ padding: '8px 16px', fontWeight: 'bold' }}>Chi</button>
            <button style={{ padding: '8px 16px', fontWeight: 'bold' }}>Pon</button>
            <button style={{ padding: '8px 16px', fontWeight: 'bold' }}>Kan</button>
            <button style={{ padding: '8px 16px', fontWeight: 'bold' }}>Riichi</button>
            <button style={{ padding: '8px 16px', fontWeight: 'bold' }}>Pass</button>
        </div>
    );
};
