// src/render/TableRenderer.tsx
import React, { useRef, useEffect, useState } from 'react';
import { useGameStore } from '../state/gameStore';
import { SoundManager } from '../audio/SoundManager';
import { GameOrchestrator } from '../core/GameOrchestrator';
import { TileIntelligence } from '../ui/TileIntelligence';

// 画像パス生成関数
const getTileImageSrc = (
    tileId: string, 
    isTsumo?: boolean, 
    isSelfDiscard?: boolean, 
    isOpponentDiscard?: boolean, 
    isRightPlayerDiscard?: boolean, 
    isLeftPlayerDiscard?: boolean,
    isHidden?: boolean // 対面の裏向き牌用
): string => {
    if (isHidden) {
        return `/design/majang-hai/p_bk_0.gif`;
    }

    let typeCode = '';
    let numCode = '';
    let suffix = '_0'; 
    
    if (isOpponentDiscard) suffix = '_1';
    else if (isSelfDiscard) suffix = '_2';
    else if (isRightPlayerDiscard) suffix = '_4'; 
    else if (isLeftPlayerDiscard) suffix = '_3'; 

    if (['E', 'S', 'W', 'N', 'P', 'F', 'C'].includes(tileId)) {
        const jiMap: Record<string, string> = {
            'E': 'e', 'S': 's', 'W': 'w', 'N': 'n',
            'P': 'no', 'F': 'h', 'C': 'c'
        };
        typeCode = 'ji';
        numCode = jiMap[tileId] || tileId.toLowerCase();

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
        return `/design/majang-hai/p_no_0.gif`;
    }

    return `/design/majang-hai/p_${typeCode}${numCode}${suffix}.gif`;
};

// リーチ棒のパス取得
const getRiichiStickSrc = (isVertical: boolean): string => {
    return isVertical 
        ? `/design/others/b_1_1.gif` // 縦（左右のプレイヤー用）
        : `/design/others/b_1_2.gif`; // 横（自分と対面用）
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
        const imageCache: Record<string, HTMLImageElement> = {};

        const getImage = (src: string): HTMLImageElement | null => {
            if (imageCache[src]) return imageCache[src];
            const img = new Image();
            img.src = src;
            imageCache[src] = img;
            return img;
        };

        const render = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // 背景描画
            ctx.fillStyle = '#1a3a19';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // 卓の枠線
            ctx.strokeStyle = 'rgba(255,255,255,0.1)';
            ctx.lineWidth = 2;
            ctx.strokeRect(320, 160, 640, 400);

            // 各プレイヤーの捨て牌・リーチ棒・手牌描画
            players.forEach((player, pIdx) => {
                const isVertical = pIdx % 2 === 1; // 1(右), 3(左) は縦配置
                let offsetX = 0, offsetY = 0;
                let stickOffsetX = 0, stickOffsetY = 0;
                let isStickVertical = false;

                // 座標設定
                if (pIdx === 0) { // 自分 (下)
                    offsetX = 460; offsetY = 380;
                    stickOffsetX = 460; stickOffsetY = 340;
                    isStickVertical = false;
                } else if (pIdx === 1) { // 右 (右側)
                    offsetX = 840; offsetY = 240;
                    stickOffsetX = 800; stickOffsetY = 240;
                    isStickVertical = true;
                } else if (pIdx === 2) { // 対面 (上)
                    offsetX = 460; offsetY = 160;
                    stickOffsetX = 460; stickOffsetY = 120;
                    isStickVertical = false;
                } else if (pIdx === 3) { // 左 (左側)
                    offsetX = 380; offsetY = 240;
                    stickOffsetX = 340; stickOffsetY = 240;
                    isStickVertical = true;
                }

                // 1. リーチ棒描画
                if (player.hasRiichi) {
                    const stickSrc = getRiichiStickSrc(isStickVertical);
                    const stickImg = getImage(stickSrc);
                    if (stickImg && stickImg.complete) {
                        const stickW = isStickVertical ? 10 : 60;
                        const stickH = isStickVertical ? 60 : 10;
                        ctx.drawImage(stickImg, stickOffsetX, stickOffsetY, stickW, stickH);
                    }
                }

                // 2. 捨て牌描画
                const pRiver = river[pIdx] || [];
                pRiver.forEach((entry, tIdx) => {
                    const row = Math.floor(tIdx / 6);
                    const col = tIdx % 6;

                    let x = offsetX + (isVertical ? 0 : col * 32);
                    let y = offsetY + (isVertical ? col * 32 : row * 44);

                    let suffixType: 'self' | 'opponent' | 'right' | 'left' | undefined;
                    if (pIdx === 0) suffixType = 'self';
                    else if (pIdx === 2) suffixType = 'opponent';
                    else if (pIdx === 3) suffixType = 'left';
                    else if (pIdx === 1) suffixType = 'right';

                    const imgSrc = getTileImageSrc(
                        entry.tile.id, 
                        false, 
                        suffixType === 'self', 
                        suffixType === 'opponent', 
                        suffixType === 'right', 
                        suffixType === 'left'
                    );
                    const img = getImage(imgSrc);

                    if (img && img.complete) {
                        ctx.drawImage(img, x, y, 30, 40);
                    } else {
                        // フォールバック：白抜き矩形
                        ctx.fillStyle = '#f0f0f0';
                        ctx.fillRect(x, y, 30, 40);
                        ctx.strokeStyle = '#333';
                        ctx.strokeRect(x, y, 30, 40);
                    }
                });

                // 3. 対面の手牌（裏向き）描画
                // ※ Canvas 上で簡易的に描画（実際の手牌詳細は UI コンポーネント側で扱う場合もあるが、ここでは視認性のため描画）
                if (pIdx === 2 && player.handLength) {
                    const hiddenSrc = getTileImageSrc('', false, false, false, false, false, true);
                    const hiddenImg = getImage(hiddenSrc);
                    if (hiddenImg && hiddenImg.complete) {
                        // 対面の手牌エリアに裏向き牌を並べる
                        const handStartX = 460 - (player.handLength * 15); // 中央寄せ
                        const handY = 100; 
                        for (let i = 0; i < player.handLength; i++) {
                            ctx.drawImage(hiddenImg, handStartX + i * 30, handY, 30, 40);
                        }
                    }
                }
            });

            animationFrameId = requestAnimationFrame(render);
        };

        render();

        return () => {
            cancelAnimationFrame(animationFrameId);
        };
    }, [river, players]);

    // 自家の手牌操作イベント設定
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
                                boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
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
