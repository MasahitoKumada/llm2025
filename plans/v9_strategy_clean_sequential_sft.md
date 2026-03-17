# v9 Strategy: Clean Sequential SFT

## 概要

v8実験の失敗分析とPerson Q〜Yの知見を踏まえた新戦略。
**目標: LBスコア 0.8以上**

## v8失敗の根本原因

### 問題1: 学習データに「Approach:」「Output:」プレフィックスが含まれていた
```
assistant content: "Approach:\n1. Task: Create news article in CSV\n...\n\nOutput:\narticle_id,author,..."
```

モデルはこれを「正しい出力形式」として学習し、推論時にも出力してしまった。
採点では**純粋な構造化データのみ**が期待されるため、形式不正として判定された。

### 問題2: 段階的学習でのCatastrophic Forgetting
- Stage 1 → Stage 2 → Stage 3 → Stage 4 と進むにつれて、前のStageの能力が失われた
- Stage 1: 0.40 → Stage 2: 0.03 → Stage 3: 0.07 → Stage 4: 0.03

### 問題3: 空の出力・文字化けの発生
- Stage 2以降で空の出力（`""`）や文字化け（`"蓢\n\n"`）が多発

---

## 重要な知見（Person Q〜Y）

### Person R: Empty Think Injection（LB 0.7228達成）
```
<think>
</think>

{生の構造化データ}
```
- Qwen3の`<think>...</think>`機能を利用
- CoT（Approach: ... Output: ...）を**物理削除**
- 空の`<think>`ブロックで思考フェーズを即座に終了させる

### Person T: TOMLの学習源
- **衝撃の発見**: TOMLの出力データを削除してもTOML文法正解率は84%維持
- TOMLの文法は**他のフォーマット（JSON, YAML）から転移学習**している

### Person U: 段階的SFT（LB 0.84達成）- 最重要
- ベースモデルに一度SFTを実行して、特定フォーマットの学習
- そのモデルをベースにして、別のフォーマットの学習
- **なるべくベースモデルに近い方が文章読解力が高くて安定**
- 「Here!」「Sure!」が出たら → もうちょっと学習できそう
- 同じこと繰り返し → やりすぎ

### Person W: 高品質データの重要性（LB 0.8以上達成）
- **1000件以下のデータ**で0.8以上達成
- データの**質**が重要（量より質）
- epoch 2でT4使用で40分程度

### Person Y: データクリーニング
- CoT除去（Approach: ... Output:）の実装
- 構文検証・重複除去・外れ値チェック

---

## v9戦略

### Phase 1: データセット作成（Clean Format）

#### データ形式
```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a structured data expert. Output only valid {format} without any explanation."
    },
    {
      "role": "user",
      "content": "Generate lab result data in JSON format."
    },
    {
      "role": "assistant",
      "content": "<think>\n</think>\n\n{\n  \"result_id\": \"LAB-3793814\",\n  ...pure structured data...\n}"
    }
  ]
}
```

#### 重要ポイント
1. **CoT完全削除**: 「Approach:」「Output:」を物理削除
2. **Empty Think Injection**: `<think>\n</think>\n\n` を先頭に付与
3. **純粋な構造化データのみ**: コードフェンス、説明文、後書きなし
4. **構文検証済みデータのみ使用**: Person Yのパイプライン活用

### Phase 2: 段階的SFT

#### Stage構成（Person U方式を改良）

```
Base: Qwen/Qwen3-4B-Instruct-2507
     │
     ▼
Stage 1: JSON集中学習（最重要フォーマット）
     │   - JSON生成・変換データ約500件
     │   - epoch 2, lr 5e-5
     │   - LoRA merge → HFアップロード
     │
     ▼
Stage 2: CSV追加学習
     │   - CSV生成・変換データ約300件
     │   - Stage 1 merged モデルをベースに
     │   - epoch 2, lr 3e-5（やや低く）
     │   - LoRA merge → HFアップロード
     │
     ▼
Stage 3: YAML追加学習
     │   - YAML生成・変換データ約300件
     │   - Stage 2 merged モデルをベースに
     │   - epoch 2, lr 3e-5
     │   - LoRA merge → HFアップロード
     │
     ▼
Stage 4: XML追加学習
     │   - XML生成・変換データ約200件
     │   - Stage 3 merged モデルをベースに
     │   - epoch 2, lr 2e-5（さらに低く）
     │   - LoRA merge → HFアップロード
     │
     ▼
Stage 5: Mixed微調整（TOML含む）
         - 全フォーマットの小規模混合データ約200件
         - Stage 4 merged モデルをベースに
         - epoch 1, lr 1e-5（非常に低く）
         - 最終モデル
```

#### 学習率の設計理念
- 後のStageほど**学習率を下げる**
- 前のStageの能力を維持しつつ、新しいフォーマットを追加
- Person U: 「なるべくベースモデルに近い方が安定」

### Phase 3: 推論時の後処理

```python
def clean_output(text):
    # 1. <think>...</think> を削除
    text = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL)

    # 2. 残存する説明文を削除
    patterns = [
        r'^Here is.*?:\s*',
        r'^Sure.*?:\s*',
        r'^Output:\s*',
        r'^Result:\s*',
        r'```\w*\n?',  # コードフェンス開始
        r'\n?```$',     # コードフェンス終了
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    return text.strip()
```

---

## 代替戦略: Single Shot Clean SFT

段階的SFTが複雑すぎる場合の代替案：

### データセット
- Person Yのクリーニングパイプラインで全9データセットを処理
- CoT除去 + Empty Think Injection
- 約3000〜5000件の高品質データ

### 学習設定
```python
# Person R参考
lora_r = 64
lora_alpha = 64
lr = 5e-5
epochs = 2
batch_size = 16
max_seq_len = 1024
```

---

## 期待される結果

| フォーマット | 目標正解率 |
|-------------|-----------|
| JSON | 100% (50/50) |
| CSV | 100% (20/20) |
| YAML | 97%+ (34/35) |
| XML | 90%+ (18/20) |
| TOML | 80%+ (20/25) |
| **Total** | **95%+ (142/150)** → **LB 0.8+** |

---

## 実装順序

1. `scripts/create_v9_clean_dataset.py` - データセット作成（CoT除去 + Empty Think Injection）
2. `notebooks/SFT/v9_single_shot.ipynb` - 単発SFT版（代替戦略）
3. `notebooks/SFT/v9_stage1_json.ipynb` - Stage 1
4. `notebooks/SFT/v9_stage2_csv.ipynb` - Stage 2
5. `notebooks/SFT/v9_stage3_yaml.ipynb` - Stage 3
6. `notebooks/SFT/v9_stage4_xml.ipynb` - Stage 4
7. `notebooks/SFT/v9_stage5_mixed.ipynb` - Stage 5

---

## リスク軽減策

1. **各Stageで推論テスト**: 次に進む前に必ずパース成功率を確認
2. **ロールバック準備**: 各Stage mergedモデルをHFに保存
3. **Single Shot版を先に実行**: 安定したベースラインを確保

---

## 参考リンク

- Person R: https://huggingface.co/beachcities/qwen3-4b-sft-v5g-hybrid-merged
- Person Y: notebooks/data_cleaning.ipynb
