# Majan MVP

最小実行可能な麻雀ゲームエンジンとTenhouログ解析ツール群です。

## 概要
- `game.py`: WebSocketによるリアルタイム通信を含むPython/FastAPI製の麻雀ゲームバックエンド・簡単な自律打牌付き。
- `parser.py`: Tenhou形式の牌譜（XML）をロード・パースするためのパーサー。ドラ、赤ドラ情報も正しく解析します。
- `rule_generator.py`: 解析結果からAI向けのルールを生成するスクリプト。実測値のみを返し、虚偽のデータを生成しません。
- `static/`: HTML/CSS/JSによるProfessional UIを配置するディレクトリ。

## 🚀 使用方法

### 依存関係のインストール
```bash
pip install fastapi uvicorn pyyaml
```

### ゲーム（最小プロトタイプ）の起動
```bash
python game.py
```
ブラウザで `http://localhost:8000` にアクセスしてください。

### 統計分析の実行例
```bash
python rule_generator.py --input ./haihu --pattern kagi_cut --output ./rules
```

### テストの実行
```bash
python -m unittest discover tests/
```
