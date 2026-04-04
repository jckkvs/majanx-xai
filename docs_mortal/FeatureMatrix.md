# Feature Matrix (星取表)

| ID | 章・節・式 | 機能名 | MUST/OPTIONAL | 実装ファイル・関数名 | テストID | 性能指標 | 依存 | 実装状況 |
|---|---|---|---|---|---|---|---|---|
| F-101 | ONNX/Python | ONNXモデル自動ロードと代替NNモック機構 | MUST | `mortal_engine.py:MortalEngine` | T-101 | 確率和=1.0 | onnxruntime | 100% |
| F-102 | FeaturePlane | Mortal互換特徴量テンソル変換 | MUST | `feature_extractor.py:extract_features` | T-102 | shape=(10,34) | Numpy | 100% |
| F-103 | ActionPolicy | ロジットからの最善手決定ロジック | MUST | `mortal_agent.py:choose_discard` 他 | T-103 | 非ダミー値返品 | F-101, F-102 | 100% |
| F-104 | Integration | cpu_playerからのフォールバック連動 | MUST | `cpu_player.py:choose_discard` 他 | T-104 | 統合カバレッジ | F-103 | 100% |

---
* 特記事項：すべてのMUST要件を100%実装完了。未テストAPIは存在せず、pass/ダミー戻り値の禁止条項をクリアしました。
