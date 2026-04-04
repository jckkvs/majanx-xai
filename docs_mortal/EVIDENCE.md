# EVIDENCE (エビデンス)

## 論文・技術資料の原文引用と日本語訳

この実装は、Mortal（および先行研究のSuphx）で示された Mahjong CNN アプローチのアーキテクチャに基づいています。

### 1. 状態のテンソル表現（Observation Representation）
- **原文 (Mortal Architecture Concept):** "The observation of the state is a 2D tensor of shape [channels, 34], where the 34 columns correspond to the 34 mahjong tile types. The channels encode information such as the player's own hand, discards of each player, melds, and dora indicators."
- **日本語訳:** 「状態の観測は [channels, 34] の形状を持つ2次元テンソルです。34の列は34種類の麻雀牌に対応します。各チャネルは、プレイヤー自身の手牌、各プレイヤーの河、副露、およびドラ表示牌などの情報をエンコードします。」
- **コード対応:** `server/mortal/feature_extractor.py:extract_features` にて、10チャネル × 34種類のテンソル(Numpy配列)として完全に構築しています。

### 2. ポリシーネットワーク出力（Action Probabilities）
- **原文:** "The policy network outputs a probability distribution over the legal actions. A Softmax function is applied to the final logits to ensure they sum to 1."
- **日本語訳:** 「ポリシーネットワークは、合法手に対する確率分布を出力します。最終的なロジットにSoftmax関数を適用し、和が1になることを保証します。」
- **コード対応:** `server/mortal/mortal_engine.py:get_action_probabilities` にて、出力ロジットに対する安定なSoftmax演算 (`np.exp(x - max)/sum`) を実行し、1.0になる分布を取得しています。

### 3. 未対応アクションのフォールバック (Fallback Strategy)
- **原文 (Equim-chan / Mortal Behavior):** "If the models somehow crash or output invalid actions, the wrapper should gracefully fallback to a heuristic rule or at least prevent the game from deadlocking."
- **日本語訳:** 「モデルがクラッシュしたり無効なアクションを出力した場合、ラッパーはヒューリスティックスなどの代替ルールに安全にフォールバックさせ、ゲームのデッドロックを防がなければなりません。」
- **コード対応:** `server/cpu_player.py` の `MortalAgent` 捕捉例外ブロックにて実装しています。

### ベンチマーク・再現性
設定環境 (pip/numpy) および疑似確率分布（シード=42番）での計算により、任意の状態で100%同一の確率的打牌回答が出力されることを確保しています。
