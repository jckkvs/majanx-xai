import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ExplanationPanel } from './ExplanationPanel';
import { ReviewBoard } from '../render/ReviewBoard';

interface TimelineItem {
  turn: number;
  user_move: string;
  ai_move: string;
  is_match: boolean;
  explanation: any;
  confidence: number;
  user_move_analysis: string;
  state_snapshot: any;
}

interface ReviewData {
  summary: {
    game_id: string;
    match_rate: number;
    total_turns: number;
    match_count: number;
    critical_turns: number[];
  };
  timeline: TimelineItem[];
}

export const ReviewView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [review, setReview] = useState<ReviewData | null>(null);
  const [currentTurn, setCurrentTurn] = useState(0);
  const [loading, setLoading] = useState(false);
  const timelineListRef = useRef<HTMLDivElement>(null);

  const currentTurnData = useMemo(() => review?.timeline[currentTurn] || null, [review, currentTurn]);

  // 不一致インデックスの計算
  const criticalIndices = useMemo(() => 
    review ? review.summary.critical_turns.map(turn => turn - 1) : []
  , [review]);

  const nextCritical = criticalIndices.find(i => i > currentTurn);
  const prevCritical = [...criticalIndices].reverse().find(i => i < currentTurn);

  const prevTurn = useCallback(() => {
    if (currentTurn > 0) setCurrentTurn(prev => prev - 1);
  }, [currentTurn]);

  const nextTurn = useCallback(() => {
    if (review && currentTurn < review.timeline.length - 1) setCurrentTurn(prev => prev + 1);
  }, [currentTurn, review]);

  useEffect(() => {
    const handleKeydown = (e: KeyboardEvent) => {
      if (loading) return;
      switch (e.key) {
        case 'ArrowLeft': prevTurn(); break;
        case 'ArrowRight': nextTurn(); break;
        case 'm': case 'M': if (nextCritical !== undefined) setCurrentTurn(nextCritical); break;
        case 'k': case 'K': if (prevCritical !== undefined) setCurrentTurn(prevCritical); break;
      }
    };
    window.addEventListener('keydown', handleKeydown);
    return () => window.removeEventListener('keydown', handleKeydown);
  }, [loading, prevTurn, nextTurn, nextCritical, prevCritical]);

  useEffect(() => {
    const loadReview = async () => {
      setLoading(true);
      try {
        await fetch(`/api/v1/review/analyze/${id}`, { method: 'POST' });
        const res = await fetch(`/api/v1/review/${id}`);
        if (res.ok) {
          const data = await res.json();
          setReview(data);
        }
      } catch (e) {
        console.error('Review load failed:', e);
      } finally {
        setLoading(false);
      }
    };
    if (id) loadReview();
  }, [id]);

  useEffect(() => {
    if (timelineListRef.current) {
      const activeEl = timelineListRef.current.querySelector('.timeline-item.active');
      activeEl?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [currentTurn]);

  if (loading) {
    return (
      <div style={{ position: 'fixed', inset: 0, background: '#0a0a12', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4ecca3', zIndex: 100 }}>
        AI分析中...
      </div>
    );
  }

  if (!review) return <div style={{ padding: '20px', color: '#fff' }}>Review result not found. Make sure the game was logged recently.</div>;

  return (
    <div className="review-container" style={{ maxWidth: '1400px', margin: '0 auto', padding: '20px', color: '#e0e0e0' }}>
      <header className="review-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', background: '#161625', padding: '16px', borderRadius: '12px' }}>
        <button onClick={() => navigate('/')} style={{ background: '#2a2a40', border: 'none', color: '#4ecca3', padding: '8px 14px', borderRadius: '8px', cursor: 'pointer' }}>← 対局に戻る</button>
        <h2 style={{ margin: 0 }}>📜 実戦振り返り: {id}</h2>
        <div className="summary-badges" style={{ display: 'flex', gap: '12px' }}>
          <span style={{ background: 'rgba(78, 204, 163, 0.2)', color: '#4ecca3', padding: '6px 12px', borderRadius: '8px', fontWeight: 600 }}>一致率: {review.summary.match_rate}%</span>
          <span style={{ background: 'rgba(230, 126, 34, 0.2)', color: '#e67e22', padding: '6px 12px', borderRadius: '8px', fontWeight: 600 }}>重要手: {review.summary.critical_turns.length}箇所</span>
        </div>
      </header>

      <main style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '20px' }}>
        {/* Sidebar Timeline */}
        <div className="timeline-panel" style={{ background: '#161625', padding: '16px', borderRadius: '12px', height: 'calc(100vh - 160px)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ marginBottom: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <button onClick={prevTurn} disabled={currentTurn === 0} style={{ background: '#2a2a40', border: 'none', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer' }}>◀</button>
              <span style={{ color: '#4ecca3', fontWeight: 600 }}>{currentTurn + 1} / {review.timeline.length}</span>
              <button onClick={nextTurn} disabled={currentTurn === review.timeline.length - 1} style={{ background: '#2a2a40', border: 'none', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer' }}>▶</button>
            </div>
            <button 
                onClick={() => nextCritical !== undefined && setCurrentTurn(nextCritical)}
                disabled={nextCritical === undefined}
                style={{ width: '100%', padding: '8px', border: '1px solid #e67e22', borderRadius: '8px', background: 'rgba(230, 126, 34, 0.1)', color: '#e67e22', cursor: 'pointer' }}
            >
              ⚠️ 次の重要手へ
            </button>
          </div>
          <div ref={timelineListRef} style={{ flex: 1, overflowY: 'auto', paddingRight: '4px' }}>
            {review.timeline.map((t, i) => (
              <div 
                key={i} 
                className={`timeline-item ${i === currentTurn ? 'active' : ''}`}
                onClick={() => setCurrentTurn(i)}
                style={{
                  padding: '10px', margin: '4px 0', borderRadius: '8px', cursor: 'pointer',
                  background: i === currentTurn ? '#2a2a40' : '#1a1a2e',
                  border: i === currentTurn ? '1px solid #4ecca3' : '1px solid transparent',
                  display: 'flex', justifyContent: 'space-between'
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, color: '#888', fontSize: '0.75rem' }}>巡目 {t.turn}</div>
                  <div style={{ fontSize: '0.85rem', fontFamily: 'monospace' }}>{t.user_move} → {t.ai_move}</div>
                </div>
                {review.summary.critical_turns.includes(t.turn) ? '⚠️' : t.is_match ? '✅' : '❓'}
              </div>
            ))}
          </div>
        </div>

        {/* Content Area */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <ReviewBoard 
            state={currentTurnData?.state_snapshot} 
            aiSuggestion={currentTurnData?.ai_move} 
          />
          
          <ExplanationPanel 
            explanation={currentTurnData?.explanation} 
            userMove={currentTurnData?.user_move}
            isReviewMode={true}
          />

          {currentTurnData && !currentTurnData.is_match && (
            <div style={{ padding: '16px', background: 'rgba(230, 126, 34, 0.1)', borderLeft: '4px solid #e67e22', borderRadius: '8px' }}>
               <h4 style={{ margin: '0 0 8px 0', color: '#e67e22' }}>📚 分析ノート</h4>
               <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: '1.6' }}>{currentTurnData.user_move_analysis}</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
