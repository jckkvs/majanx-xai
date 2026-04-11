# 🀄 MajanX-XAI

麻雀学習支援アプリ。最新AIの推奨手＋段階的解説をリアルタイム提供し、実践を通じて「なぜ」を学ぶための補助ツールです。

## ✨ 特徴
- 🤖 **マルチエンジン推論**: kanachan / Phoenix / RLCard をアンサンブル
- 💡 **段階的包括説明**: 技術要因・戦略判断・自然言語要約を階層表示
- 🎨 **商用級UI**: 雀魂風操作性・リアルタイム同期・レスポンシブ対応
- 📊 **牌譜分析**: AI一致率・対局統計の自動可視化
- 🔒 **セキュア設計**: レートリミット・CORS・セキュリティヘッダー強化
- 🔊 **音声フィードバック**: Web Speech API による解説読み上げ

## 🚀 クイックスタート

### 1. 環境構築
```bash
git clone https://github.com/jckkvs/majanx-xai.git
cd majanx-xai
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
```

### 2. 起動
```bash
# 開発モード
python main.py
# → http://localhost:8000
```

### 3. AIモデル設定
アプリ内設定パネル（開発中）または `registry.py` にて HuggingFace トークンを設定してください。

## 📦 アーキテクチャ
```
majanx-xai/
├── core/            # ルール・推論・説明・牌譜・監視エンジン
├── server/          # FastAPI ルーター・ミドルウェア
├── frontend/        # React + Vite UI
├── kifu_data/       # 対局履歴保存先
├── models_cache/    # AI重みキャッシュ
└── main.py          # エントリポイント
```

## 📄 ライセンス
MIT
