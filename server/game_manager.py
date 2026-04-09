"""
対局マネージャー: ゲームループとプレイヤー管理
Implements: F-004 | 対局進行管理

人間プレイヤー1人 + CPU3人の対局を管理。
WebSocketを通じてフロントエンドと通信。
"""
from __future__ import annotations

import asyncio
from typing import Optional, Callable, Awaitable

from .models import (
    Tile, ActionType, GameAction, GamePhase, tile_from_str,
)
from .engine import GameEngine
class SimpleCPU:
    def __init__(self, seat: int, engine: GameEngine):
        self.seat = seat
        self.engine = engine

    def _get_probabilities(self):
        return None

    def decide_tsumo_action(self, options: list[GameAction]) -> Optional[GameAction]:
        for opt in options:
            if opt.action_type == ActionType.HORA:
                return opt
        return None

    def choose_discard(self) -> Tile:
        player = self.engine.state.players[self.seat]
        if player.hand:
            return player.hand[-1]
        raise ValueError("Empty hand")

    def decide_call(self, options: list[GameAction]) -> GameAction:
        for opt in options:
            if opt.action_type == ActionType.HORA:
                return opt
        return GameAction(action_type=ActionType.SKIP, player=self.seat)
from .commentator import CommentatorAI


class GameManager:
    """
    対局のゲームループを管理。
    - 人間プレイヤー(seat=0) の入力待ち
    - CPU (seat=1,2,3) の自動応答
    """

    def __init__(self, human_seat: int = 0, seed: Optional[int] = None):
        self.human_seat = human_seat
        self.engine = GameEngine(use_red_dora=True, seed=seed)
        self.explainer = CommentatorAI(self.engine)
        self.cpus: dict[int, SimpleCPU] = {}
        self._send_to_client: Optional[Callable[[dict], Awaitable[None]]] = None
        self._waiting_for_human = False
        self._human_response: Optional[dict] = None
        self._human_event = asyncio.Event()

    def set_client_handler(self, handler: Callable[[dict], Awaitable[None]]):
        """クライアントへのメッセージ送信ハンドラを設定"""
        self._send_to_client = handler

    async def _send(self, msg: dict):
        """クライアントにメッセージ送信"""
        if self._send_to_client:
            await self._send_to_client(msg)

    async def start_game(self):
        """対局開始"""
        # CPUプレイヤー作成
        for seat in range(4):
            if seat != self.human_seat:
                self.cpus[seat] = SimpleCPU(seat, self.engine)

        # イベントハンドラ設定
        def _engine_handler(e):
            if e["type"] in ["ryukyoku", "agari"]:
                
                # 名前の付与
                players = []
                for i in range(4):
                    if i == self.human_seat: players.append({"name": "Player"})
                    elif i == (self.human_seat + 1) % 4: players.append({"name": "下家"})
                    elif i == (self.human_seat + 2) % 4: players.append({"name": "対面"})
                    else: players.append({"name": "上家"})
                
                if e["type"] == "ryukyoku":
                    if "tenpai_info" in e:
                        for info in e["tenpai_info"]:
                            info["name"] = players[info["seat"]]["name"]

                e["players"] = players
                
                asyncio.create_task(self._send(e))

        self.engine.set_event_handler(_engine_handler)
        # ゲーム開始
        self.engine.start_game()

        # 初期状態をクライアントに送信
        await self._send({
            "type": "game_state",
            "state": self.engine.to_state_dict(for_player=self.human_seat),
        })

        # ゲームループ開始
        await self._game_loop()

    async def _game_loop(self):
        """メインゲームループ"""
        while self.engine.state.phase not in (GamePhase.GAME_END, GamePhase.ROUND_END):
            st = self.engine.state
            current = st.current_player

            if st.phase == GamePhase.PLAYER_TURN:
                # ツモ
                tile = self.engine.do_tsumo()
                if tile is None:
                    # 流局
                    await self._send({
                        "type": "game_state",
                        "state": self.engine.to_state_dict(for_player=self.human_seat),
                    })
                    break

                await self._send({
                    "type": "tsumo",
                    "actor": current,
                    "pai": tile.id if current == self.human_seat else "?",
                    "state": self.engine.to_state_dict(for_player=self.human_seat),
                })

                # ツモ後アクション判定
                tsumo_actions = self.engine.get_tsumo_actions(current)

                if current == self.human_seat:
                    # 人間の打牌待ち
                    await self._handle_human_turn(tsumo_actions)
                else:
                    # CPUの打牌
                    await self._handle_cpu_turn(current, tsumo_actions)

            elif st.phase == GamePhase.CALLING:
                # 鳴き判定
                await self._handle_calling_phase()

            elif st.phase == GamePhase.ROUND_END:
                break

            # 少し待つ（UI更新のため）
            await asyncio.sleep(0.1)

        # 局終了後
        if self.engine.state.phase == GamePhase.ROUND_END:
            await self._send({
                "type": "round_end",
                "state": self.engine.to_state_dict(for_player=None),  # 全手牌公開
            })
            # 次局の自動開始を通知
            await self._send({"type": "waiting_next_round"})

        elif self.engine.state.phase == GamePhase.GAME_END:
            await self._send({
                "type": "game_end",
                "state": self.engine.to_state_dict(for_player=None),
            })

    async def _handle_human_turn(self, tsumo_actions: list[GameAction]):
        """人間プレイヤーのターン処理"""
        # 選択肢をクライアントに送信
        actions_data = []
        for a in tsumo_actions:
            actions_data.append({
                "type": a.action_type.value,
                "tile": a.tile.id if a.tile else None,
            })

        try:
            from server.app import AI_AVAILABLE, feature_extractor_global, ai_engine_global, orchestrator_global
            if AI_AVAILABLE and self.engine.state:
                feat = feature_extractor_global.extract(self.engine.state, self.human_seat)
                recs = ai_engine_global.predict(feat, top_k=3)
                
                # コンテキスト抽出（実計算ロジック使用）
                from server.utils.mahjong_logic import build_full_context
                ctx = build_full_context(self.engine.state, self.human_seat)
                
                if recs:
                    tile = recs[0].tile
                    prob = recs[0].probability
                    # アクション空間マッピングのインデックスはMortal推論内で消失しているため仮引数を渡す
                    # (本質的にはXAIAnalyzerでしか使わずモック実装なので問題ない)
                    idx = 0 
                else:
                    tile = "default"
                    prob = 0.0
                    idx = 0

                triple_rec = await orchestrator_global.run(
                    features=feat, 
                    ai_idx=idx, 
                    ai_prob=prob, 
                    ai_tile=tile, 
                    ctx=ctx, 
                    model=getattr(ai_engine_global, 'model', None)
                )
                
                # 指定された WebSocket 送信ペイロード構造
                await self._send({
                    "type": "triple_recommendation",
                    "data": {
                        "xai": triple_rec.xai,
                        "strategy": triple_rec.strategy,
                        "interpretation": triple_rec.interpret,
                        "reading": triple_rec.reading,
                        "four_layer": triple_rec.four_layer,
                        "meta": triple_rec.meta,
                        # 元々のMortal推論結果（alternativesなど）もUIで表示するため追加
                        "ai": {
                            "primary": {"tile": recs[0].tile, "prob": recs[0].probability, "q_val": recs[0].q_value} if recs else {},
                            "alternatives": [{"tile": alt.tile, "prob": alt.probability, "q_val": alt.q_value} for alt in (recs[1:] if recs else [])]
                        }
                    }
                })
            
            ai_data = None
        except Exception as e:
            import traceback
            import logging
            logging.error(f"AI inference failed: {e}")
            traceback.print_exc()
            ai_data = None

        await self._send({
            "type": "your_turn",
            "actions": actions_data,
            "state": self.engine.to_state_dict(for_player=self.human_seat),
            "ai_analysis": ai_data,  # 互換性のため残すが中身はNone
        })

        # 人間の入力待ち
        response = await self._wait_for_human_input()
        await self._process_human_action(response)

    async def _handle_cpu_turn(self, seat: int, tsumo_actions: list[GameAction]):
        """CPUプレイヤーのターン処理"""
        cpu = self.cpus[seat]
        await asyncio.sleep(2.0)  # CPU思考時間（オート進行見やすくするため2秒）

        # === AI解説を生成してUIへ配信（オートプレイ時の見栄え用） ===
        try:
            mortal_probs = None
            analysis = self.explainer.analyze(seat, mortal_probs)
            ai_data = analysis
            await self._send({
                "type": "ai_analysis",
                "ai_analysis": ai_data,
            })
        except Exception as e:
            import traceback
            print(f"AI解説エラー: {e}")
            traceback.print_exc()

        # ツモ後アクション
        action = cpu.decide_tsumo_action(tsumo_actions)
        if action:
            if action.action_type == ActionType.HORA:
                # ツモ和了
                result = self.engine.handle_hora(seat, seat, is_tsumo=True)
                await self._send({
                    "type": "hora",
                    "data": result,
                    "state": self.engine.to_state_dict(for_player=None),
                })
                return
            elif action.action_type == ActionType.RIICHI:
                self.engine.do_riichi(seat, action.tile)
                await self._send({
                    "type": "game_state",
                    "state": self.engine.to_state_dict(for_player=self.human_seat),
                })
                return
            elif action.action_type == ActionType.ANKAN:
                self.engine.do_ankan(seat, action.tile)
                await self._send({
                    "type": "game_state",
                    "state": self.engine.to_state_dict(for_player=self.human_seat),
                })
                return

        # 通常打牌
        discard = cpu.choose_discard()
        is_tsumogiri = (discard == self.engine.state.players[seat].hand[-1])
        self.engine.do_dahai(seat, discard, is_tsumogiri)

        await self._send({
            "type": "dahai",
            "actor": seat,
            "pai": discard.id,
            "state": self.engine.to_state_dict(for_player=self.human_seat),
        })

    async def _handle_calling_phase(self):
        """鳴き判定フェーズ"""
        st = self.engine.state
        discard_player = st.last_discard_player

        # 全プレイヤーの鳴き選択肢を確認（ロン→ポン/カン→チーの優先順）
        all_options: dict[int, list[GameAction]] = {}
        for seat in range(4):
            if seat == discard_player:
                continue
            options = self.engine.get_call_options(seat)
            if options:
                all_options[seat] = options

        # 人間の鳴き選択肢があるか
        human_has_options = self.human_seat in all_options and self.human_seat != discard_player

        if human_has_options:
            # 人間に鳴きの選択肢を提示
            actions_data = []
            for a in all_options[self.human_seat]:
                actions_data.append({
                    "type": a.action_type.value,
                    "tile": a.tile.id if a.tile else None,
                    "consumed": [t.id for t in a.consumed] if a.consumed else None,
                })
            actions_data.append({"type": "skip"})

            await self._send({
                "type": "call_option",
                "actions": actions_data,
                "state": self.engine.to_state_dict(for_player=self.human_seat),
            })

            response = await self._wait_for_human_input()

            if response.get("action") == "skip":
                # 人間がスキップ → CPUの鳴きを処理
                pass
            else:
                # 人間の鳴き実行
                await self._process_human_action(response)
                return

        # CPUの鳴き判定
        for seat in all_options:
            if seat == self.human_seat:
                continue
            cpu = self.cpus.get(seat)
            if cpu:
                decision = cpu.decide_call(all_options[seat])
                if decision.action_type == ActionType.HORA:
                    # ロン
                    result = self.engine.handle_hora(
                        seat, discard_player, is_tsumo=False
                    )
                    await self._send({
                        "type": "hora",
                        "data": result,
                        "state": self.engine.to_state_dict(for_player=None),
                    })
                    return
                elif decision.action_type == ActionType.PON:
                    self.engine.do_pon(seat, decision.consumed)
                    await asyncio.sleep(0.3)
                    # ポン後の打牌
                    discard = cpu.choose_discard()
                    self.engine.do_dahai(seat, discard)
                    await self._send({
                        "type": "game_state",
                        "state": self.engine.to_state_dict(for_player=self.human_seat),
                    })
                    return

        # 誰も鳴かない → 次のターン
        self.engine.advance_turn()

    async def _wait_for_human_input(self) -> dict:
        """人間プレイヤーの入力を待つ"""
        self._human_event.clear()
        self._waiting_for_human = True
        await self._human_event.wait()
        self._waiting_for_human = False
        return self._human_response or {}

    def receive_human_input(self, data: dict):
        """WebSocketからの人間入力を受け取る"""
        self._human_response = data
        self._human_event.set()

    async def _process_human_action(self, data: dict):
        """人間プレイヤーのアクションを処理"""
        action = data.get("action", "")
        st = self.engine.state

        if action == "dahai":
            tile_str = data.get("tile", "")
            tile = tile_from_str(tile_str)
            is_tsumogiri = data.get("tsumogiri", False)
            self.engine.do_dahai(self.human_seat, tile, is_tsumogiri)
            await self._send({
                "type": "game_state",
                "state": self.engine.to_state_dict(for_player=self.human_seat),
            })

        elif action == "riichi":
            tile_str = data.get("tile", "")
            tile = tile_from_str(tile_str)
            self.engine.do_riichi(self.human_seat, tile)
            await self._send({
                "type": "game_state",
                "state": self.engine.to_state_dict(for_player=self.human_seat),
            })

        elif action == "hora":
            is_tsumo = data.get("is_tsumo", True)
            from_seat = self.human_seat if is_tsumo else st.last_discard_player
            result = self.engine.handle_hora(
                self.human_seat, from_seat, is_tsumo=is_tsumo
            )
            await self._send({
                "type": "hora",
                "data": result,
                "state": self.engine.to_state_dict(for_player=None),
            })

        elif action == "chi":
            tile_str = data.get("tile", "")
            consumed_strs = data.get("consumed", [])
            consumed = [tile_from_str(s) for s in consumed_strs]
            self.engine.do_chi(self.human_seat, consumed)
            # チー後の打牌待ち
            await self._send({
                "type": "your_turn",
                "actions": [],
                "state": self.engine.to_state_dict(for_player=self.human_seat),
            })
            response = await self._wait_for_human_input()
            await self._process_human_action(response)

        elif action == "pon":
            consumed_strs = data.get("consumed", [])
            consumed = [tile_from_str(s) for s in consumed_strs]
            self.engine.do_pon(self.human_seat, consumed)
            # ポン後の打牌待ち
            await self._send({
                "type": "your_turn",
                "actions": [],
                "state": self.engine.to_state_dict(for_player=self.human_seat),
            })
            response = await self._wait_for_human_input()
            await self._process_human_action(response)

        elif action == "ankan":
            tile_str = data.get("tile", "")
            tile = tile_from_str(tile_str)
            self.engine.do_ankan(self.human_seat, tile)
            await self._send({
                "type": "game_state",
                "state": self.engine.to_state_dict(for_player=self.human_seat),
            })

        elif action == "skip":
            pass  # 何もしない

    async def next_round(self):
        """次局を開始"""
        if self.engine.state.phase == GamePhase.ROUND_END:
            self.engine.start_round()
            await self._send({
                "type": "game_state",
                "state": self.engine.to_state_dict(for_player=self.human_seat),
            })
            await self._game_loop()
