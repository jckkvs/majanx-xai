import React, { useEffect, useRef, useState } from 'react';
import { RankCertificationOverlay } from './ui/RankCertificationOverlay';
import { LocalProgressEngine } from './core/LocalProgressEngine';
import { TableRenderer } from './render/TableRenderer';
import { ActionContextBar } from './input/ActionContextBar';
import { SoundManager } from './audio/SoundManager';
import { ProgressiveOverlayController } from './ui/ProgressiveOverlayController';
import { ExplanationPanel } from './ui/ExplanationPanel';
import { StatsDashboard } from './ui/StatsDashboard';
import { ReviewView } from './ui/ReviewView';
import { useGameStore } from './state/gameStore';
import { useGameAudio } from './hooks/useAudio';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';

function App() {
  const progressiveRef = useRef<ProgressiveOverlayController | null>(null);
  const [matchResult, setMatchResult] = useState<any>(null);
  const [showStats, setShowStats] = useState(false);
  const progressEngine = useRef(new LocalProgressEngine());
  const completeExplanation = useGameStore(state => state.completeExplanation);
  const { appMode, setAppMode } = useGameStore();
  const { playSFX } = useGameAudio();
  const orchestrator = useRef<GameOrchestrator | null>(null);

  useEffect(() => {
    progressEngine.current.load();
    progressiveRef.current = new ProgressiveOverlayController();
    
    // Get orchestrator instance if needed
    const tableEl = document.querySelector('.game-root') as HTMLElement;
    if (tableEl) {
        orchestrator.current = new GameOrchestrator(tableEl);
    }
    
    // Webhook simulation / message listener logic
    const handleMessage = (e: any) => {
      if (e.data?.type === 'round_end') {
        const result = e.data;
        // 自分の順位 (1-indexed)
        const myPlace = result.placement.indexOf(0) + 1;
        
        const oldData = progressEngine.current.getSnapshot();
        const oldRP = oldData.rank.points;
        const oldRank = oldData.rank.division;
        
        // 記録更新
        progressEngine.current.applyResult(myPlace, result.scores[0] - 25000, 0); 
        progressEngine.current.save();
        
        const newData = progressEngine.current.getSnapshot();
        
        setMatchResult({
          place: myPlace,
          score: result.scores[0],
          oldRP,
          newRP: newData.rank.points,
          oldRank,
          newRank: newData.rank.division
        });
        
        playSFX('ai_ready');
        SoundManager.getInstance().play('snap'); // Celebration sound
        orchestrator.current?.triggerWinEffect('tsumo');
      } else if (e.data?.type === 'discard_result') {
        playSFX('discard');
      } else if (e.data?.type === 'game_start') {
        playSFX('draw');
      } else if (e.data?.type === 'riichi') {
        orchestrator.current?.triggerRiichiEffect();
      }
    };

    // Instantiate message listener (Integration point)
    window.addEventListener('message', handleMessage);
    
    // 最初のユーザー操作でオーディオコンテキストを初期化
    const unlock = () => {
      SoundManager.getInstance().init();
      window.removeEventListener('pointerdown', unlock);
    };
    window.addEventListener('pointerdown', unlock);

    return () => {
      window.removeEventListener('message', handleMessage);
      progressiveRef.current?.cleanup();
    };
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={
          <div className="game-root" style={{ 
            position: 'relative', 
            width: '100vw', 
            height: '100vh', 
            backgroundColor: '#1b1b1b', 
            overflow: 'hidden',
            fontFamily: '"Outfit", sans-serif'
          }}>
            <TableRenderer />
            <ActionContextBar containerRef={progressiveRef} />
            
            <div id="wait-info-portal" style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none', zIndex: 2000 }} />
            <div id="progressive-ui-portal" />
            <div id="network-overlay" />

            {/* モード切替スイッチャー */}
            <div style={{
              position: 'absolute', top: '20px', left: '50%', transform: 'translateX(-50%)',
              background: 'rgba(17,24,39,0.8)', padding: '4px', borderRadius: '10px',
              display: 'flex', gap: '4px', zIndex: 1000, border: '1px solid #333'
            }}>
                <button 
                  onClick={() => setAppMode('PLAY')}
                  style={{
                    padding: '8px 16px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                    background: appMode === 'PLAY' ? '#4ecca3' : 'transparent',
                    color: appMode === 'PLAY' ? '#0d0d1a' : '#888',
                    fontWeight: 600, transition: 'all 0.2s'
                  }}
                >
                  🎮 PLAY
                </button>
                <button 
                  onClick={() => setAppMode('LEARN')}
                  style={{
                    padding: '8px 16px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                    background: appMode === 'LEARN' ? '#4ecca3' : 'transparent',
                    color: appMode === 'LEARN' ? '#0d0d1a' : '#888',
                    fontWeight: 600, transition: 'all 0.2s'
                  }}
                >
                  📚 LEARN
                </button>
            </div>

            {completeExplanation && (
              <div style={{ position: 'absolute', top: '20px', right: '20px', zIndex: 1000 }}>
                <ExplanationPanel explanation={completeExplanation as any} />
              </div>
            )}

            <div style={{ position: 'absolute', bottom: '20px', left: '20px', zIndex: 1000 }}>
              <button 
                onClick={() => setShowStats(!showStats)}
                style={{
                  background: '#4ecca3',
                  border: 'none',
                  borderRadius: '50%',
                  width: '48px',
                  height: '48px',
                  fontSize: '1.2rem',
                  cursor: 'pointer',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                {showStats ? '✖' : '📊'}
              </button>
              {showStats && (
                <div style={{ position: 'absolute', bottom: '60px', left: 0 }}>
                  <StatsDashboard />
                </div>
              )}
            </div>

            {matchResult && (
              <RankCertificationOverlay 
                {...matchResult} 
                onClose={() => setMatchResult(null)} 
              />
            )}
          </div>
        } />
        <Route path="/review/:id" element={<ReviewView />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
