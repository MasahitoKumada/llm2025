# v15戦略: スコア0.8超え達成計画 (Person U/Z/AA知見ベース)

## 📊 状況分析

### 現在の最高スコア
- **v5.4.1: LB 0.77794** (v5データ 3,869件, LR=5e-6, r=64, α=128, dropout=0)

### 目標
- **LB 0.8 超え** (約+0.02のギャップを埋める)

---

## 🏆 トップスコア達成者の知見

### Person U (LB 0.84) ⭐最重要
```
パース成功率:
- CSV: 100.0%
- JSON: 100.0%
- TOML: 92.0% (fail 2)
- XML: 95.0% (fail 1)
- YAML: 100.0%
```

**核心メッセージ:**
> 「なるべくベースモデルに近い方が文章読解力が高くて安定した合格スコアになるようです」

**Sequential SFT戦略:**
1. ベースモデルに一度SFTを実行して、特定フォーマットの学習をする
2. そのモデルをベースにして、別のフォーマットの学習をする
3. 各データセットのベストスコアをマージする

**発見:**
- TOMLの学習はTOMLのデータが持つとは限らない
- フォーマットAのスコアが良くなっても、フォーマットBのスコアはいまいちになることがある

### Person Z (LB 0.82超え)
**3段階のアプローチ:**

1. **基礎フェーズ**: 構造化データ出力の「安定化」
   - コンテキスト長の拡張（512→1024）
   - 中道の学習率

2. **向上フェーズ**: 学習の「質」への転換
   - バッチ処理による勾配の純化（勾配累積）
   - 「量」より「時間」の管理

3. **究極フェーズ**: 過学習（Overfitting）の抑制 ← **最も重要**
   - ドロップアウトやウェイトディケイを適切に設定
   - 学習率の極微細なチューニング

### Person AA (LB 0.8超え)
**重要ポイント:**
- 過学習防止が最重要（val loss低下よりも重要）
- **低めのlearning rate**が有効（Geminiの推奨は高すぎる）
- **過学習防止パラメータは大きめ**が効果的
- **rsLoRA推奨** (`use_rslora = True`)
- rsLoRAはrが大きくても効果的に学習が進む

### Person W (LB 0.8超え)
- 微調整で変化度合いを確かめながら進める
- **学習データは1000件以下でも0.8超え可能**
- 質（今回のコンペに対して適切か）が重要

### Person T (96.7% parse rate)
- TOMLデータを除去しても、TOML出力は学習できる
- TOML: 84.0%, XML: 95.0%, CSV/JSON/YAML: 100%

---

## 📈 比較分析: v5.4.1 vs Person U (0.84)

| フォーマット | v5.4.1 | Person U | 差分 |
|-------------|--------|----------|------|
| CSV | 100.0% | 100.0% | 0 |
| JSON | 98.0% | 100.0% | +2% |
| TOML | 72.0% | 92.0% | **+20%** |
| XML | 75.0%? | 95.0% | **+20%** |
| YAML | 88.6% | 100.0% | +11.4% |

**最大の改善余地: TOML (+20%) と XML (+20%)**

---

## 🎯 実験計画

### Phase 1: パラメータ微調整（最優先）

#### v15.0: 低LR実験
```python
# v5データ維持、LRのみ調整
Data: v5 (3,869件)
LR: 4e-6  # 5e-6 → 80%に下げる
r: 64
α: 128
dropout: 0
weight_decay: 0.05
rsLoRA: False
epochs: 3

# 期待: LBスコア +0.01〜0.02
```

#### v15.1: rsLoRA + 過学習防止
```python
# Person AA推奨のrsLoRA追加
Data: v5 (3,869件)
LR: 4e-6
r: 64
α: 128
dropout: 0.03  # 微量追加
weight_decay: 0.1  # 増加
rsLoRA: True  # ⭐追加
epochs: 3

# 期待: 過学習防止で汎化性能向上
```

#### v15.2: 大きめr + rsLoRA
```python
# Person AAの「rsLoRAはrが大きくても効果的」を検証
Data: v5 (3,869件)
LR: 3e-6  # さらに低く
r: 128   # 倍増
α: 128
dropout: 0.05
weight_decay: 0.1
rsLoRA: True
epochs: 3
```

### Phase 2: Sequential SFT（Person U戦略）

#### 手順
1. **Step 1**: JSON/YAMLのみでSFT → model_a
2. **Step 2**: model_aをベースに TOML/XMLでSFT → model_b
3. **Step 3**: model_bをベースに CSVでSFT → model_final

#### データ分割
```python
# v5データをフォーマット別に分割
json_yaml_data = filter(v5, format in ['json', 'yaml'])
toml_xml_data = filter(v5, format in ['toml', 'xml'])
csv_data = filter(v5, format == 'csv')
```

### Phase 3: 高品質少量データ（Person W戦略）

#### v15.5: 厳選データセット
```python
# daichira hard-4kのみ使用（複雑なタスク）
Data: daichira/structured-hard-sft-4k (4,000件)
# または
Data: u-10bei/512_v4 の高品質サブセット (1,000件程度)

LR: 3e-6
r: 64
α: 128
dropout: 0.03
weight_decay: 0.1
rsLoRA: True
epochs: 2  # 少量データなので短め
```

---

## 🔬 実験優先順位

| 優先度 | 実験 | 変更点 | 根拠 |
|--------|------|--------|------|
| 1 | v15.0 | LR: 5e-6→4e-6 | Person U/Z/AA全員が低LR推奨 |
| 2 | v15.1 | +rsLoRA +dropout | Person AA推奨 |
| 3 | v15.2 | r=128 + rsLoRA | Person AAの「rが大きくても効果的」 |
| 4 | v15.3 | Sequential SFT | Person Uの成功戦略 |
| 5 | v15.5 | 少量高品質データ | Person Wの知見 |

---

## 📝 v15.0 ノートブック設計

v7.1ベースで以下を変更:
```python
# 設定値の変更
os.environ["SFT_LR"] = "4e-6"         # 5e-6 → 4e-6
os.environ["SFT_LORA_R"] = "64"       # 維持
os.environ["SFT_LORA_ALPHA"] = "128"  # 維持
os.environ["SFT_LORA_DROPOUT"] = "0"  # 維持
os.environ["SFT_WEIGHT_DECAY"] = "0.05"  # 維持

# データセット: v5維持
os.environ["SFT_DATASET_ID"] = "kmd2525/structeval-sft-v5"
```

---

## ⚠️ 注意点

1. **LR変更は慎重に**: v5.6 (LR=6e-6) でLB 0.68263まで暴落した経験あり
2. **変更は1つずつ**: 結果の解釈を容易にするため
3. **rsLoRA単独では効果なし**: v5.5B (rsLoRA=True) でLB 0.76631に悪化
4. **rsLoRA + 過学習防止の組み合わせ**: v13.2でLB 0.76127（TOMLデータ除去の影響もあり）

---

## 🎯 成功の鍵（Person U/Z/AAの共通点）

1. **ベースモデルに近い状態を維持** → 低LR
2. **過学習防止を徹底** → dropout + weight_decay
3. **rsLoRAの活用**（ただし他のパラメータとの組み合わせが重要）
4. **細かいパラメータ調整** → 凸探索で最適点を見つける

---

## 🚀 次のステップ

1. v15.0ノートブック作成（LR=4e-6のみ変更）
2. Colabで実行
3. 結果に応じてv15.1以降を実行
4. 0.8超えが達成できたら、Sequential SFTを試行
