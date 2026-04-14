// src/render/ReviewBoard.tsx
import React, { useRef, useEffect } from 'react';

interface ReviewBoardProps {
  state: {
    hand: string[];
    river: string[];
    players?: any;
    dora?: string[];
  } | null;
  aiSuggestion?: string;
}

export const ReviewBoard: React.FC<ReviewBoardProps> = ({ state, aiSuggestion }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !state) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Redraw table
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#1a3a19'; 
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Markings
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 2;
    ctx.strokeRect(320, 160, 640, 400);

    // Simplistic River Render (User only for MVP review)
    const river = state.river || [];
    river.forEach((tileId, idx) => {
        const row = Math.floor(idx / 6);
        const col = idx % 6;
        const x = 460 + col * 32;
        const y = 380 + row * 44;
        
        ctx.fillStyle = '#f8f8f8';
        ctx.fillRect(x, y, 30, 40);
        ctx.fillStyle = '#333';
        ctx.font = 'bold 12px sans-serif';
        ctx.fillText(tileId, x + 5, y + 25);
    });

    // Dora Indicators
    if (state.dora) {
        state.dora.forEach((d, i) => {
            const x = 340 + i * 32;
            ctx.fillStyle = '#2d3436';
            ctx.fillRect(x, 180, 30, 40);
            ctx.fillStyle = '#ffeaa7';
            ctx.fillText(d, x + 5, 205);
        });
    }

  }, [state]);

  if (!state) return <div style={{ color: '#666' }}>No snapshot available</div>;

  return (
    <div style={{ position: 'relative', width: '100%', height: '400px', borderRadius: '12px', overflow: 'hidden' }}>
      <canvas 
        ref={canvasRef} 
        width={1280} 
        height={720} 
        style={{ width: '100%', height: '100%', display: 'block' }} 
      />
      {/* Hand display (Static) */}
      <div style={{
        position: 'absolute', bottom: '20px', left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: '4px'
      }}>
        {state.hand.map((tile, idx) => (
          <div key={idx} style={{
            width: '36px', height: '50px', backgroundColor: tile === aiSuggestion ? '#e3f2fd' : '#f8f8f8',
            borderRadius: '4px', border: tile === aiSuggestion ? '2px solid #4ecca3' : '1px solid #ccc',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '16px',
            boxShadow: tile === aiSuggestion ? '0 0 10px rgba(78,204,163,0.5)' : 'none'
          }}>
            {tile}
          </div>
        ))}
      </div>
    </div>
  );
};
