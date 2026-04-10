import numpy as np

def select_cpu_action(ai_probabilities, valid_moves, strength=0.75):
    """
    CPUの打牌選択（強さ調整付き）
    strength: 0.0(弱) ～ 1.0(強)
    """
    if not valid_moves:
        return None
        
    try:
        if not ai_probabilities:
            raise ValueError("No AI probabilities")
            
        # ai_probabilities が valid_moves と同じ長さを持ち対応していると想定
        move_indices = [valid_moves.index(m) for m in valid_moves]
        probs = np.array(ai_probabilities)[move_indices]
        
        # 温度スケーリングによる強弱調整
        # strengthが高い -> 温度が低い -> 確率分布が鋭くなる(強い)
        temperature = 1.0 + (1.0 - strength) * 3.0
        scaled_probs = probs ** (1.0 / temperature)
        scaled_probs /= scaled_probs.sum()  # 正規化
        
        # 確率分布からサンプリング
        chosen_idx = np.random.choice(len(valid_moves), p=scaled_probs)
        return valid_moves[chosen_idx]
    except Exception:
        # 何らかの理由で確率処理に失敗した場合や未指定の場合はランダム選択
        chosen_idx = np.random.choice(len(valid_moves))
        return valid_moves[chosen_idx]
