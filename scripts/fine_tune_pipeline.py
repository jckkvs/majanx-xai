# scripts/fine_tune_pipeline.py
import json
import os
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
import onnx
try:
    from onnxsim import simplify
except ImportError:
    simplify = None
from huggingface_hub import HfApi, login
import argparse

class MahjongDataset(Dataset):
    def __init__(self, kifu_dir: str):
        self.samples = []
        suit_map = {'m': 0, 'p': 9, 's': 18, 'z': 27}
        
        for p in Path(kifu_dir).glob("*.json"):
            try:
                game = json.loads(p.read_text(encoding="utf-8"))
                for move in game["moves"]:
                    # 簡易特徴量: 手牌(34種カウントベクトル)
                    # 実際は move["ai_suggestion"] 等から特徴量を抽出
                    vec = [0.0] * 34
                    # ... ダミー実装 ...
                    self.samples.append((np.array(vec, dtype=np.float32), 0)) # y=0 (ダミーラベル)
            except Exception as e:
                print(f"Error loading {p}: {e}")
        
    def __len__(self): return len(self.samples)
    def __getitem__(self, idx): return self.samples[idx]

class MahjongPolicyNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(34, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 34), # 34種牌の確率分布
            nn.Softmax(dim=-1)
        )
    def forward(self, x): return self.net(x)

def train_and_export(kifu_dir: str, output_path: str, epochs: int = 5):
    dataset = MahjongDataset(kifu_dir)
    if len(dataset) == 0:
        print("⚠️ 学習データがありません。kifu_data/ に牌譜を配置してください。")
        return None

    loader = DataLoader(dataset, batch_size=32, shuffle=True)
    model = MahjongPolicyNet()
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    print(f"📊 学習開始: {len(dataset)} samples, {epochs} epochs")
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for x, y in loader:
            optimizer.zero_grad()
            outputs = model(x)
            loss = criterion(outputs, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        print(f"Epoch {epoch+1}/{epochs} | Loss: {total_loss/len(loader):.4f}")

    # ONNX エクスポート
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    dummy_input = torch.randn(1, 34)
    torch.onnx.export(model, dummy_input, output_path, 
                      input_names=["state"], output_names=["probs"],
                      dynamic_axes={"state": {0: "batch"}, "probs": {0: "batch"}})
    
    # ONNX Simplify
    if simplify:
        try:
            model_onnx = onnx.load(output_path)
            model_simp, check = simplify(model_onnx)
            onnx.save(model_simp, output_path)
            print("✅ ONNX 最適化完了")
        except Exception as e:
            print(f"⚠️ ONNX Simplify 失敗 (スキップ): {e}")

    return output_path

def push_to_hf(model_path: str, repo_id: str, token: str):
    login(token)
    api = HfApi()
    api.upload_file(
        path_or_fileobj=model_path,
        path_in_repo="model.onnx",
        repo_id=repo_id,
        repo_type="model"
    )
    print(f"🚀 HF Hub 公開完了: https://huggingface.co/{repo_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kifu_dir", default="./kifu_data")
    parser.add_argument("--output", default="./models_cache/custom_policy.onnx")
    parser.add_argument("--hf_repo", default=None)
    parser.add_argument("--hf_token", default=None)
    args = parser.parse_args()

    onnx_path = train_and_export(args.kifu_dir, args.output)
    if onnx_path and args.hf_repo and args.hf_token:
        push_to_hf(onnx_path, args.hf_repo, args.hf_token)
