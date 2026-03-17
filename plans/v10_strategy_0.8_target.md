# v10戦略: スコア0.8超えを目指す

## 1. 現状分析

### これまでの実験結果

| Version | パース成功率 | LBスコア | 備考 |
|---------|------------|---------|------|
| v5.2 | 89.3% | 0.75程度 | 最良結果 |
| v9 (Empty Think なし) | 壊滅的 | 0.06098 | tool_call漏洩 |

### v9失敗の原因
- **Empty Think Injectionを省略**したことでQwen3のデフォルト動作（`<tool_call>`、thinking）が活性化
- Person Yのクリーンデータは有効だが、**Empty Think Injectionは必須**

---

## 2. Person Q以降の重要知見

### Person Q: スコアの仕組み
- **×判定は「内容が違う」ではなく「形式が壊れた」が多い**
- スコアは単純な正解率ではない（構造の一致度で評価）
- **形式の安定が内容より重要**

### Person R: Empty Think Injection (LB 0.7228達成)
```
<think>
</think>

{生の構造化データ}
```
- LoRA r=64, alpha=64, lr=5e-5, 2 epochs, batch=16
- CoT除去 + コードフェンス除去 + Empty Think付与

### Person T: TOMLの意外な発見
- **TOMLデータを削除しても、TOML 84.0%達成**
- TOMLの学習は必ずしもTOMLのデータから来ていない

### Person U: スコア0.84への道（最重要！）
達成した結果:
```
CSV:  20/20 = 100.0%
JSON: 50/50 = 100.0%
TOML: 23/25 = 92.0%
XML:  19/20 = 95.0%
YAML: 35/35 = 100.0%
```

**重要な洞察:**
1. **「なるべくベースモデルに近い方が文章読解力が高くて安定した合格スコアになる」**
2. TOMLの学習は他のデータで覚えている
3. 各フォーマットで最適なデータセットが違う
4. **段階的学習（Sequential Learning）**:
   - ベースモデルに一度SFTを実行して、特定フォーマットの学習
   - そのモデルをベースにして、別のフォーマットの学習
5. パラメータを詰めることで、ベースモデルの100%正答率フォーマットは崩れない

### Person W: 少量高品質データ
- **最終的には1000件以下のデータで学習**
- 質（今回のコンペに対して適切か）が重要
- 基準となるLLMの性能が良い場合は、学習量を増やすよりも細かい調整

### Person X: NEFTune
- **NEFTuneを導入**が効いた

---

## 3. 戦略オプション

### 戦略A: Person R方式の忠実な再現（推奨：最初に試す）
Person Rの手法をクリーンデータに適用:

1. **データ準備**:
   - Person Yのクリーンデータ（merged_dataset_final_clean.jsonl）
   - Empty Think Injection適用: `<think>\n</think>\n\n{データ}`

2. **ハイパーパラメータ**:
   - LoRA r=64, alpha=64
   - lr=5e-5
   - 2 epochs
   - batch=16

3. **期待効果**: LB 0.72〜0.75

### 戦略B: Person U方式の段階的学習（0.84達成者の方法）

1. **Stage 1**: JSON/CSVに特化したSFT
   - ベースモデル: Qwen3-4B-Instruct
   - データ: JSON/CSVのみのサブセット
   - Empty Think Injection適用

2. **Stage 2**: Stage 1モデルでYAML学習
   - ベースモデル: Stage 1のmergedモデル
   - データ: YAMLのサブセット

3. **Stage 3**: Stage 2モデルでXML/TOML学習
   - ベースモデル: Stage 2のmergedモデル
   - データ: XML/TOMLのサブセット

4. **期待効果**: LB 0.80〜0.84

### 戦略C: 少量高品質データ + NEFTune

1. **データ準備**:
   - クリーンデータから厳選した1000件以下
   - フォーマット別にバランス調整

2. **学習設定**:
   - NEFTune有効化
   - 低学習率で慎重に学習

3. **期待効果**: LB 0.78〜0.82

---

## 4. 推奨実行順序

### Phase 1: 基盤構築（v10）
**戦略A: Person R方式**
- 目的: Empty Think Injectionの効果確認
- 期待: LB 0.72〜0.75

### Phase 2: 段階的学習（v11）
**戦略B: Person U方式**
- 目的: 0.8超えを狙う
- 前提: Phase 1で基本動作を確認済み

### Phase 3: 最適化（v12）
**戦略C: 少量データ + NEFTune**
- 目的: さらなる改善
- 戦略A/Bの良いところを組み合わせ

---

## 5. 具体的な実装計画

### v10: Empty Think Injection + クリーンデータ

#### 必要なファイル
1. `scripts/create_sft_v10_dataset.py` - Empty Think適用スクリプト
2. `notebooks/SFT/v10_empty_think.ipynb` - 学習ノートブック

#### データ処理フロー
```
merged_dataset_final_clean.jsonl
    │
    ▼
scripts/create_sft_v10_dataset.py
    │  - CoT除去確認
    │  - Empty Think Injection: <think>\n</think>\n\n{データ}
    │  - コードフェンス除去
    │
    ▼
inputs/sft_processed/v10/train.json
```

#### ハイパーパラメータ（Person R準拠）
```python
# LoRA設定
r = 64
lora_alpha = 64
lora_dropout = 0.1

# 学習設定
learning_rate = 5e-5
num_train_epochs = 2
per_device_train_batch_size = 16
max_seq_length = 1024  # L4推奨
```

### v11: 段階的学習

#### Stage構成
| Stage | フォーマット | データ件数(目安) | ベースモデル |
|-------|------------|----------------|------------|
| 1 | JSON, CSV | 2000件 | Qwen3-4B-Instruct |
| 2 | YAML | 1000件 | Stage1のmerged |
| 3 | XML, TOML | 1500件 | Stage2のmerged |

#### 各Stage後の検証
- 毎Stage後にローカル評価実行
- 特定フォーマットの崩壊がないか確認

---

## 6. 成功の指標

### パース成功率の目標
| フォーマット | 現状(v5.2) | 目標(v10) | 目標(v11) |
|------------|-----------|-----------|-----------|
| JSON | 98.0% | 100% | 100% |
| YAML | 88.6% | 95%+ | 100% |
| TOML | 72.0% | 80%+ | 92%+ |
| XML | 85.0% | 90%+ | 95%+ |
| CSV | 95.0% | 100% | 100% |
| **全体** | **89.3%** | **93%+** | **97%+** |

### LBスコア目標
- v10: 0.75〜0.78
- v11: **0.80+**
- v12: 0.82+

---

## 7. 注意事項

### Empty Think Injectionの重要性
v9の失敗から明確になった教訓:
- **Qwen3-InstructはEmpty Think Injectionなしではtool_callモードが活性化**
- データがどれだけクリーンでも、この前処理は必須

### ベースモデルの能力を活かす
Person Uの洞察:
> 「なるべくベースモデルに近い方が文章読解力が高くて安定した合格スコアになる」

- 過学習を避ける
- 適切なパラメータで「崩さない」学習

### 段階的学習のコツ
- 各Stageで前Stageの能力が崩れていないか確認
- フォーマット間の干渉を最小化

---

## 8. 次のアクション

1. **即座に実行**: v10データセット作成スクリプトの実装
2. **v10ノートブック作成**: Person R設定を適用
3. **v10実験実行**: Empty Think Injectionの効果確認
4. **v11計画**: 結果を見て段階的学習の詳細を決定
