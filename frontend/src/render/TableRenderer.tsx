// src/render/TableRenderer.tsx
import React, { useRef, useEffect } from 'react';
import { useGameStore } from '../state/gameStore';
import { SoundManager } from '../audio/SoundManager';
import { GameOrchestrator } from '../core/GameOrchestrator';
import { TileIntelligence } from '../ui/TileIntelligence';

export const TableRenderer: React.FC = () => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const handContainerRef = useRef<HTMLDivElement>(null);
    const orchestratorRef = useRef<GameOrchestrator | null>(null);
    const store = useGameStore();
    const { hand, river, players, discardOptions } = store;

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        
        if (handContainerRef.current && !orchestratorRef.current) {
            orchestratorRef.current = new GameOrchestrator(handContainerRef.current);
        }
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let animationFrameId: number;

        const render = () => {
            // Clear
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Draw Table Background (Green felt)
            ctx.fillStyle = '#1a3a19'; // Slightly darker professional green
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // Draw Table Markings
            ctx.strokeStyle = 'rgba(255,255,255,0.06)';
            ctx.lineWidth = 2;
            ctx.strokeRect(320, 160, 640, 400);

            // Draw Rivers (4-way cross layout)
            river.forEach((pRiver, pIdx) => {
                const isVertical = pIdx % 2 === 1;
                const offsetX = pIdx === 0 ? 460 : pIdx === 2 ? 460 : pIdx === 1 ? 840 : 380;
                const offsetY = pIdx === 0 ? 380 : pIdx === 2 ? 220 : pIdx === 1 ? 240 : 240;

                pRiver.forEach((entry, tIdx) => {
                    const row = Math.floor(tIdx / 6);
                    const col = tIdx % 6;
                    const x = offsetX + (isVertical ? 0 : col * 32);
                    const y = offsetY + (isVertical ? col * 32 : row * 44);

                    // Risk Glow
                    if (entry.danger === 0) {
                        ctx.shadowBlur = 10;
                        ctx.shadowColor = 'rgba(34,197,94,0.6)'; // Green Genbutsu
                    } else if (entry.danger > 0.6) {
                        ctx.shadowBlur = 12;
                        ctx.shadowColor = 'rgba(239,68,68,0.5)'; // High Danger
                    } else {
                        ctx.shadowBlur = 0;
                    }

                    // Tile Body
                    ctx.fillStyle = '#f8f8f8';
                    ctx.fillRect(x, y, 30, 40);
                    ctx.shadowBlur = 0;

                    // Tile text (ID)
                    ctx.fillStyle = '#333';
                    ctx.font = 'bold 12px sans-serif';
                    ctx.fillText(entry.tile.id, x + 5, y + 25);
                });
            });

            animationFrameId = requestAnimationFrame(render);
        };

        render();

        return () => {
            cancelAnimationFrame(animationFrameId);
        };
    }, [river, players]);

    useEffect(() => {
        if (!handContainerRef.current) return;
        
        const sm = SoundManager.getInstance();
        
        Array.from(handContainerRef.current.children).forEach((el: any) => {
            const tileId = el.dataset.tile;
            
            el.onpointerup = (e: PointerEvent) => {
                const dy = e.clientY - (el as any)._startY; // 簡易的な開始位置保持が必要
                if (dy < -60) {
                    orchestratorRef.current?.handleDiscard(
                        hand.find(t => t.id === tileId)!,
                        el,
                        (tile) => {
                            console.log(`[Engine] Discard finalized: ${tile.id}`);
                        }
                    );
                }
                orchestratorRef.current?.triggerFeedback('snaps');
            };

            el.onpointerdown = (e: PointerEvent) => {
                (el as any)._startY = e.clientY;
                if (orchestratorRef.current) {
                    const ukeire = discardOptions?.[tileId]?.waits.map(w => ({
                        tile: w,
                        remaining: TileIntelligence.getRemainingCount(w, store)
                    })) || [];
                    
                    orchestratorRef.current.handleDragStart(el, e, ukeire);
                }
            };
        });

        return () => {
            orchestratorRef.current?.cleanup();
        };
    }, [hand.length, discardOptions]); 

    return (
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
            <canvas 
                ref={canvasRef} 
                width={1280} 
                height={720} 
                style={{ width: '100%', height: '100%', display: 'block', transform: 'translateZ(0)' }} 
            />
            {/* プレイヤー手牌レイヤー (DOM) */}
            <div 
                ref={handContainerRef}
                className="hand-container" 
                style={{
                position: 'absolute',
                bottom: '40px',
                left: '50%',
                transform: 'translateX(-50%)',
                display: 'flex',
                gap: '4px',
                padding: '10px'
            }}>
                {hand.map((tile, idx) => (
                    <div 
                        key={`${tile.id}-${idx}`}
                        data-tile={tile.id}
                        className="tile-hand"
                        style={{
                            width: '44px',
                            height: '62px',
                            backgroundColor: '#f8f8f8',
                            borderRadius: '4px',
                            border: '1px solid #ccc',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            cursor: 'pointer',
                            fontSize: '20px',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                            userSelect: 'none',
                            touchAction: 'none'
                        }}
                    >
                        {tile.id}
                    </div>
                ))}
            </div>
        </div>
    );
};
