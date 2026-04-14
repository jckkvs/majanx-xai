// src/render/TableRenderer.tsx
import React, { useRef, useEffect, useState } from 'react';
import { useGameStore } from '../state/gameStore';
import { SoundManager } from '../audio/SoundManager';
import { GameOrchestrator } from '../core/GameOrchestrator';
import { TileIntelligence } from '../ui/TileIntelligence';

// 牌の画像パスを生成するヘルパー関数
const getTileImageSrc = (tileId: string, isTsumo?: boolean, isSelfDiscard?: boolean, isOpponentDiscard?: boolean, isRightPlayerDiscard?: boolean, isLeftPlayerDiscard?: boolean): string => {
    // tileId の形式: "1m", "E", "P" など
    let typeCode = '';
    let numCode = '';
    let suffix = '_0'; // デフォルトは通常表示（手牌など）

    if (isOpponentDiscard) suffix = '_1';
    else if (isSelfDiscard) suffix = '_2';
    else if (isRightPlayerDiscard) suffix = '_3'; // 自分の右（画面左側の人）の捨て牌
    else if (isLeftPlayerDiscard) suffix = '_4';  // 自分の左（画面右側の人）の捨て牌

    if (['E', 'S', 'W', 'N', 'P', 'F', 'C'].includes(tileId)) {
        // 字牌
        const jiMap: Record<string, string> = {
            'E': 'e', 'S': 's', 'W': 'w', 'N': 'n',
            'P': 'no', 'F': 'h', 'C': 'c'
        };
        typeCode = 'ji';
        numCode = jiMap[tileId] || tileId.toLowerCase();

        // 白 (P) の場合は p_no_x.gif (jiプレフィックスなし)
        if (tileId === 'P') {
            return `/design/majang-hai/p_no${suffix}.gif`;
        }
    } else if (tileId.endsWith('m')) {
        typeCode = 'ms';
        numCode = tileId.replace('m', '');
    } else if (tileId.endsWith('p')) {
        typeCode = 'ps';
        numCode = tileId.replace('p', '');
    } else if (tileId.endsWith('s')) {
        typeCode = 'ss';
        numCode = tileId.replace('s', '');
    } else {
        // フォールバック
        return `/design/majang-hai/p_no_0.gif`;
    }

    // 数値が1桁の場合、プレフィックスなしで OK (例：1 -> 1)
    // 画像ファイル名規則: p_{type}{num}_{suffix}.gif
    // 例：1萬 -> p_ms1_0.gif, 東 (自家捨て) -> p_ji_e_2.gif
    return `/design/majang-hai/p_${typeCode}${numCode}${suffix}.gif`;
};

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

        // 画像キャッシュ
        const imageCache: Record<string, HTMLImageElement> = {};

        const getImage = (src: string): HTMLImageElement | null => {
            if (imageCache[src]) return imageCache[src];

            const img = new Image();
            img.src = src;
            imageCache[src] = img;
            return img;
        };

        const render = () => {
            // Clear
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Draw Table Background (Green felt)
            ctx.fillStyle = '#1a3a19';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            // Draw Table Markings
            ctx.strokeStyle = 'rgba(255,255,255,0.06)';
            ctx.lineWidth = 2;
            ctx.strokeRect(320, 160, 640, 400);

            // Draw Rivers (4-way cross layout)
            river.forEach((pRiver, pIdx) => {
                const isVertical = pIdx % 2 === 1;
                let offsetX = 0, offsetY = 0;

                if (pIdx === 0) { // 自分 (下)
                    offsetX = 460;
                    offsetY = 380;
                } else if (pIdx === 1) { // 右 (画面右側)
                    offsetX = 840;
                    offsetY = 240;
                } else if (pIdx === 2) { // 対面 (上)
                    offsetX = 460;
                    offsetY = 160;
                } else if (pIdx === 3) { // 左 (画面左側)
                    offsetX = 380;
                    offsetY = 240;
                }

                pRiver.forEach((entry, tIdx) => {
                    const row = Math.floor(tIdx / 6);
                    const col = tIdx % 6;

                    let x = offsetX + (isVertical ? 0 : col * 32);
                    let y = offsetY + (isVertical ? col * 32 : row * 44);

                    let suffixType: 'self' | 'opponent' | 'right' | 'left' | undefined;
                    if (pIdx === 0) suffixType = 'self';
                    else if (pIdx === 2) suffixType = 'opponent';
                    else if (pIdx === 3) suffixType = 'right';
                    else if (pIdx === 1) suffixType = 'left';

                    const imgSrc = getTileImageSrc(entry.tile.id, false, suffixType === 'self', suffixType === 'opponent', suffixType === 'right', suffixType === 'left');
                    const img = getImage(imgSrc);

                    if (img && img.complete) {
                        ctx.drawImage(img, x, y, 30, 40);
                    } else {
                        ctx.fillStyle = '#f8f8f8';
                        ctx.fillRect(x, y, 30, 40);
                    }
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

        Array.from(handContainerRef.current.children).forEach((el: any) => {
            const tileId = el.dataset.tile;

            el.onpointerup = (e: PointerEvent) => {
                const dy = e.clientY - (el as any)._startY;
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
                {hand.map((tile, idx) => {
                    const isTsumo = idx === hand.length - 1 && hand.length % 3 === 2;
                    const imgSrc = getTileImageSrc(tile.id, isTsumo);

                    return (
                        <div
                            key={`${tile.id}-${idx}`}
                            data-tile={tile.id}
                            className="tile-hand"
                            style={{
                                width: '44px',
                                height: '62px',
                                backgroundImage: `url(${imgSrc})`,
                                backgroundSize: 'contain',
                                backgroundRepeat: 'no-repeat',
                                backgroundPosition: 'center',
                                borderRadius: '4px',
                                border: '1px solid #ccc',
                                cursor: 'pointer',
                                boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                                userSelect: 'none',
                                touchAction: 'none'
                            }}
                        />
                    );
                })}
            </div>
        </div>
    );
};
