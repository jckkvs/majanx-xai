import React, { useEffect, useState } from 'react';
import { SoundManager } from '../audio/SoundManager';

interface RankProps {
  score: number;
  place: number;
  oldRP: number;
  newRP: number;
  oldRank: string;
  newRank: string;
  onClose: () => void;
}

export const RankCertificationOverlay: React.FC<RankProps> = ({ 
  score, place, oldRP, newRP, oldRank, newRank, onClose 
}) => {
  const [displayRP, setDisplayRP] = useState(oldRP);
  const [isRankUp, setIsRankUp] = useState(false);

  useEffect(() => {
    // RP Bar animation
    const duration = 2000;
    const start = Date.now();
    const animate = () => {
      const elapsed = Date.now() - start;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      
      const current = Math.floor(oldRP + (newRP - oldRP) * ease);
      setDisplayRP(current);
      
      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        if (newRank !== oldRank) {
          setIsRankUp(true);
          SoundManager.getInstance().vibrate([100, 50, 100]);
        }
      }
    };
    requestAnimationFrame(animate);
  }, [oldRP, newRP, oldRank, newRank]);

  const placeColors = ['#ffd700', '#c0c0c0', '#cd7f32', '#71717a'];
  const placeNames = ['1st', '2nd', '3rd', '4th'];

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 3000,
      backgroundColor: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      color: 'white', fontFamily: '"Outfit", sans-serif'
    }}>
      <div style={{ fontSize: '14px', color: '#94a3b8', letterSpacing: '0.2em' }}>局終了</div>
      <div style={{ 
        fontSize: '72px', fontWeight: 900, 
        color: placeColors[place - 1], 
        textShadow: `0 0 20px ${placeColors[place-1]}44`
      }}>
        {placeNames[place - 1]} PLACE
      </div>

      <div style={{ marginTop: '40px', textAlign: 'center' }}>
        <div style={{ fontSize: '24px', fontWeight: 600 }}>{newRank}</div>
        <div style={{ 
          width: '300px', height: '8px', 
          backgroundColor: '#334155', borderRadius: '4px', 
          marginTop: '12px', overflow: 'hidden' 
        }}>
          <div style={{ 
            width: `${(displayRP % 600) / 6}%`, 
            height: '100%', backgroundColor: '#60a5fa',
            boxShadow: '0 0 12px #3b82f6'
          }} />
        </div>
        <div style={{ marginTop: '8px', fontSize: '12px', color: '#94a3b8' }}>
          RP {displayRP} / {Math.floor(displayRP / 600 + 1) * 600}
        </div>
      </div>

      {isRankUp && (
        <div style={{ 
          marginTop: '20px', padding: '8px 24px', 
          backgroundColor: '#fbbf24', color: '#000', 
          fontWeight: 'bold', borderRadius: '20px',
          animation: 'bounce 0.5s infinite alternate'
        }}>
          RANK UP!!
        </div>
      )}

      <button 
        onClick={onClose}
        style={{
          marginTop: '60px', padding: '12px 48px',
          backgroundColor: 'transparent', border: '1px solid rgba(255,255,255,0.2)',
          color: 'white', borderRadius: 'default', cursor: 'pointer',
          transition: 'all 0.2s'
        }}
      >
        NEXT
      </button>

      <style>{`
        @keyframes bounce { from { transform: scale(1); } to { transform: scale(1.1); } }
      `}</style>
    </div>
  );
};
