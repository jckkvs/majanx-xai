import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

interface Stats {
  games_played: number;
  total_moves: number;
  ai_match_rate: number;
  avg_moves_per_game: number;
}

interface KifuEntry {
  id: string;
  date: string;
  size_kb: number;
}

export const StatsDashboard: React.FC = () => {
  const [stats, setStats] = useState<Stats>({
    games_played: 0,
    total_moves: 0,
    ai_match_rate: 0,
    avg_moves_per_game: 0
  });
  const [kifuList, setKifuList] = useState<KifuEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [sRes, kRes] = await Promise.all([
          fetch('/api/v1/stats/summary'),
          fetch('/api/v1/review/list')
        ]);
        if (sRes.ok) setStats(await sRes.json());
        if (kRes.ok) setKifuList(await kRes.json());
      } catch (e) {
        console.warn('Data fetch failed:', e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="stats-panel" style={{
      background: '#161625',
      border: '1px solid #2a2a40',
      borderRadius: '16px',
      padding: '20px',
      color: '#e0e0e0',
      width: '100%',
      maxWidth: '400px'
    }}>
      <h3 style={{ margin: '0 0 16px 0', fontSize: '1.2rem' }}>📊 対局統計</h3>
      <div className="stats-grid" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '12px',
        margin: '16px 0'
      }}>
        <div className="stat-card" style={{
          textAlign: 'center',
          background: '#1a1a2e',
          padding: '12px',
          borderRadius: '12px'
        }}>
          <span style={{ display: 'block', fontSize: '1.5rem', fontWeight: 700, color: '#4ecca3' }}>
            {stats.games_played}
          </span>
          <span style={{ fontSize: '0.75rem', color: '#888' }}>対局数</span>
        </div>
        <div className="stat-card" style={{
          textAlign: 'center',
          background: '#1a1a2e',
          padding: '12px',
          borderRadius: '12px'
        }}>
          <span style={{ display: 'block', fontSize: '1.5rem', fontWeight: 700, color: '#4ecca3' }}>
            {stats.total_moves}
          </span>
          <span style={{ fontSize: '0.75rem', color: '#888' }}>総打牌数</span>
        </div>
        <div className="stat-card" style={{
          textAlign: 'center',
          background: '#1a1a2e',
          padding: '12px',
          borderRadius: '12px'
        }}>
          <span style={{ 
            display: 'block', 
            fontSize: '1.5rem', 
            fontWeight: 700, 
            color: stats.ai_match_rate > 60 ? '#2ecc71' : stats.ai_match_rate > 40 ? '#e67e22' : '#4ecca3' 
          }}>
            {stats.ai_match_rate}%
          </span>
          <span style={{ fontSize: '0.75rem', color: '#888' }}>AI一致率</span>
          <div style={{ height: '4px', background: '#333', borderRadius: '2px', marginTop: '6px', overflow: 'hidden' }}>
            <div style={{ 
              height: '100%', 
              background: '#4ecca3', 
              width: `${stats.ai_match_rate}%`, 
              transition: 'width 0.5s ease' 
            }} />
          </div>
        </div>
      </div>
      <div style={{ marginTop: '20px' }}>
        <h4 style={{ margin: '0 0 10px 0', borderBottom: '1px solid #333', paddingBottom: '4px' }}>📁 最近の対局</h4>
        <div style={{ maxHeight: '200px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {kifuList.length === 0 ? (
                <div style={{ color: '#666', fontSize: '0.8rem' }}>対局データがありません</div>
            ) : (
                kifuList.map(k => (
                    <Link 
                        key={k.id}
                        to={`/review/${k.id}`}
                        style={{
                            background: '#1a1a2e', padding: '10px', borderRadius: '8px',
                            textDecoration: 'none', color: '#e0e0e0', fontSize: '0.85rem',
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            border: '1px solid #2a2a40'
                        }}
                    >
                        <span>{k.id.split('_')[0]} <span style={{ color: '#666', fontSize: '0.75rem' }}>({k.date})</span></span>
                        <span style={{ color: '#4ecca3' }}>振り返る →</span>
                    </Link>
                ))
            )}
        </div>
      </div>

      <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <Link 
          to="/review/room1_latest" 
          style={{ 
            display: 'block', 
            textAlign: 'center', 
            background: '#2a2a40', 
            color: '#4ecca3', 
            textDecoration: 'none', 
            padding: '8px', 
            borderRadius: '8px', 
            fontSize: '0.85rem',
            fontWeight: 600,
            border: '1px solid #4ecca3'
          }}
        >
          🔍 直近の対局を振り返る
        </Link>
        <p style={{ fontSize: '0.75rem', color: '#666', textAlign: 'center', lineHeight: '1.4', margin: 0 }}>
          一致率はあなたの打牌がAI推奨と一致した割合です。<br/>60%以上で上級者レベル。
        </p>
      </div>
    </div>
  );
};
