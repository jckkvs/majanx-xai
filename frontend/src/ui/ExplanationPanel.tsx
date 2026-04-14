// src/ui/ExplanationPanel.tsx
import React, { useState } from 'react';
import { useGameAudio } from '../hooks/useAudio';

interface TechnicalFactor {
  code: string;
  label: string;
  value?: number;
  detail?: string;
}

interface StrategicFactor {
  code: string;
  label: string;
  context: string;
  priority: number;
}

interface CompleteExplanation {
  recommended_move: string;
  technical_factors: TechnicalFactor[];
  strategic_factors: StrategicFactor[];
  summary: {
    one_liner: string;
    full_paragraph: string;
  };
  confidence_score: number;
  alternative_moves: any[];
}

export const ExplanationPanel: React.FC<{ 
  explanation: CompleteExplanation | null;
  userMove?: string;
  userAnalysis?: string;
  isReviewMode?: boolean;
}> = ({ explanation, userMove, userAnalysis, isReviewMode }) => {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    tech: true,
    strat: false,
    full: false
  });
  const { isSpeaking, speakExplanation, stopSpeaking } = useGameAudio();
  const appMode = useGameStore(state => state.appMode);
  const [isMinimized, setIsMinimized] = useState(appMode === 'PLAY');

  if (!explanation) return null;

  const toggleVoice = () => isSpeaking ? stopSpeaking() : speakExplanation(explanation.summary.full_paragraph);

  const toggle = (key: string) => setExpanded(prev => ({ ...prev, [key]: !prev[key] }));

  if (isMinimized && appMode === 'PLAY') {
    return (
      <button 
        onClick={() => setIsMinimized(false)}
        style={{
          background: '#1a1a2e',
          border: '2px solid #4ecca3',
          borderRadius: '50%',
          width: '56px',
          height: '56px',
          fontSize: '1.5rem',
          cursor: 'pointer',
          boxShadow: '0 4px 15px rgba(78, 204, 163, 0.4)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#4ecca3',
          animation: 'pulse 2s infinite'
        }}
      >
        💡
        <style>{`@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(78, 204, 163, 0.4); } 70% { box-shadow: 0 0 0 15px rgba(78, 204, 163, 0); } 100% { box-shadow: 0 0 0 0 rgba(78, 204, 163, 0); } }`}</style>
      </button>
    );
  }

  return (
    <div className="explanation-panel" style={{
      background: '#1a1a2e',
      borderLeft: '4px solid #4ecca3',
      padding: '12px',
      fontSize: '0.9rem',
      color: '#e0e0e0',
      width: '320px',
      maxHeight: '80vh',
      overflowY: 'auto',
      position: 'relative',
      boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
      borderRadius: '8px'
    }}>
      {/* 最小化ボタン */}
      {appMode === 'PLAY' && (
        <button 
          onClick={() => setIsMinimized(true)}
          style={{ position: 'absolute', top: '8px', right: '8px', background: 'transparent', border: 'none', color: '#666', cursor: 'pointer' }}
        >
          ✕
        </button>
      )}
      
      {/* 最上部: 要約 */}
      <div className="summary-section" style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h4 style={{ color: '#4ecca3', margin: '0 0 4px 0' }}>🎯 推奨: {explanation.recommended_move}</h4>
          {isReviewMode && userMove && (
            <div style={{ 
              fontSize: '0.8rem', 
              background: userMove === explanation.recommended_move ? 'rgba(78, 204, 163, 0.2)' : 'rgba(230, 126, 34, 0.2)',
              padding: '2px 8px',
              borderRadius: '4px',
              color: userMove === explanation.recommended_move ? '#4ecca3' : '#e67e22'
            }}>
              あなたの打牌: {userMove} {userMove === explanation.recommended_move ? '✅' : '⚠️'}
            </div>
          )}
          {isReviewMode && userAnalysis && (
            <div style={{ 
              fontSize: '0.8rem', 
              background: 'rgba(78, 204, 163, 0.1)', 
              padding: '8px', 
              borderRadius: '6px', 
              color: '#aaa',
              borderLeft: '3px solid #4ecca3',
              marginTop: '8px'
            }}>
              {userAnalysis}
            </div>
          )}
          <button 
            onClick={toggleVoice} 
            style={{ 
              background: isSpeaking ? '#4ecca3' : '#2a2a40', 
              border: 'none', 
              color: isSpeaking ? '#0d0d1a' : '#888', 
              padding: '4px 10px', 
              borderRadius: '6px', 
              cursor: 'pointer', 
              fontSize: '0.8rem',
              transition: 'all 0.2s'
            }}
          >
            {isSpeaking ? '🔊 停止' : '🔇 読み上げ'}
          </button>
        </div>
        <p style={{ fontSize: '1.1rem', fontWeight: 500, margin: 0 }}>{explanation.summary.one_liner}</p>
      </div>

      {/* 層1: 技術的要因 */}
      <div className="section" style={{ borderTop: '1px solid #333', paddingTop: '8px' }}>
        <div 
          onClick={() => toggle('tech')}
          style={{ cursor: 'pointer', color: '#4ecca3', fontWeight: 600, display: 'flex', justifyContent: 'space-between' }}
        >
          <span>📊 技術的要因</span>
          <span>{expanded.tech ? '▼' : '▶'}</span>
        </div>
        {expanded.tech && (
          <ul style={{ listStyle: 'none', padding: '8px 0 0 0', margin: 0 }}>
            {explanation.technical_factors.map(f => (
              <li key={f.code} style={{ display: 'flex', gap: '8px', marginBottom: '4px', fontSize: '0.85rem' }}>
                <span style={{ color: '#94a3b8' }}>•</span>
                <span>{f.label}</span>
                {f.value !== undefined && <span style={{ color: '#4ecca3', fontWeight: 'bold' }}>{f.value % 1 === 0 ? f.value : f.value.toFixed(1)}</span>}
                {f.detail && <span style={{ color: '#64748b' }}>— {f.detail}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 層2: 戦略的要因 */}
      <div className="section" style={{ borderTop: '1px solid #333', paddingTop: '8px', marginTop: '8px' }}>
        <div 
          onClick={() => toggle('strat')}
          style={{ cursor: 'pointer', color: '#4ecca3', fontWeight: 600, display: 'flex', justifyContent: 'space-between' }}
        >
          <span>🧠 戦略的判断</span>
          <span>{expanded.strat ? '▼' : '▶'}</span>
        </div>
        {expanded.strat && (
          <ul style={{ listStyle: 'none', padding: '8px 0 0 0', margin: 0 }}>
            {explanation.strategic_factors.map(f => (
              <li key={f.code} style={{ 
                marginBottom: '8px', 
                opacity: 0.4 + f.priority * 0.6,
                fontSize: '0.85rem'
              }}>
                <div style={{ fontWeight: 500 }}>{f.label}</div>
                <div style={{ color: '#888', fontSize: '0.8rem' }}>【{f.context}】</div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 層3: 詳細説明 */}
      <div className="section" style={{ borderTop: '1px solid #333', paddingTop: '8px', marginTop: '8px' }}>
        <div 
          onClick={() => toggle('full')}
          style={{ cursor: 'pointer', color: '#4ecca3', fontWeight: 600, display: 'flex', justifyContent: 'space-between' }}
        >
          <span>📝 詳細解説</span>
          <span>{expanded.full ? '▼' : '▶'}</span>
        </div>
        {expanded.full && (
          <p style={{ margin: '8px 0 0 0', fontSize: '0.85rem', lineHeight: '1.5', color: '#cbd5e1' }}>
            {explanation.summary.full_paragraph}
          </p>
        )}
      </div>

      {/* 付加情報 */}
      <div style={{ marginTop: '16px', fontSize: '0.75rem', color: '#64748b', borderTop: '1px dotted #333', paddingTop: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>確信度: {(explanation.confidence_score * 100).toFixed(0)}%</span>
          {explanation.alternative_moves.length > 0 && (
            <span>次点: {explanation.alternative_moves[0].tile}</span>
          )}
        </div>
      </div>
    </div>
  );
};
