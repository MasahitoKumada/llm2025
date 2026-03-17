# SFTデータセット概要

## ダウンロード済みデータセット

`inputs/` 配下にparquet形式で保存済み。

| # | フォルダ | HF repo | rows | columns | 備考 |
|---|---|---|---|---|---|
| 1-1 | `1-1_512_v2` | `structured_data_with_cot_dataset_512_v2` | 3,933 | ['messages', 'metadata'] | 現在v0/v1/v2で使用中 |
| 1-2 | `1-2_512_v4` | `structured_data_with_cot_dataset_512_v4` | 4,608 | ['messages', 'metadata'] | |
| 1-3 | `1-3_512_v5` | `structured_data_with_cot_dataset_512_v5` | 4,547 | ['messages', 'metadata'] | |
| 1-4 | `1-4_512` | `structured_data_with_cot_dataset_512` | 3,445 | ['messages', 'metadata'] | |
| 1-5 | `1-5_v2` | `structured_data_with_cot_dataset_v2` | 2,500 | ['messages', 'metadata'] | |
| 1-6 | `1-6_base` | `structured_data_with_cot_dataset` | 2,500 | ['messages', 'metadata'] | |
| 2-1 | `2-1_3k_mix` | `structured-3k-mix-sft` | 3,000 | ['id', 'category', 'subcategory', 'task', 'seed', 'messages'] | 長文系 |
| 2-2 | `2-2_5k_mix` | `structured-5k-mix-sft` | 5,000 | ['id', 'category', 'subcategory', 'task', 'seed', 'messages'] | 長文系 |
| 2-3 | `2-3_hard_4k` | `structured-hard-sft-4k` | 4,000 | ['id', 'category', 'subcategory', 'task', 'seed', 'messages'] | 長文系・高難度 |

---

## グループ分類

### グループ1: u-10bei系（短〜中長）

- **特徴**: 平均300〜400トークン、P99=640〜961
- **推奨MAX_SEQ_LEN**: 1024（P99カバー）
- **columns**: `messages`, `metadata`
- **messages形式**: OpenAI ChatCompletion形式（`[{role, content}, ...]`）

### グループ2: daichira系（長文）

- **特徴**: 平均~1000トークン、P95~2200
- **推奨MAX_SEQ_LEN**: 4096（ただしA100必須）
- **columns**: `id`, `category`, `subcategory`, `task`, `seed`, `messages`
- **512では約60%の情報が切り捨てられる**

---

## 使い方（ローカルから読み込み）

```python
import pandas as pd

# parquetから読み込み
df = pd.read_parquet("inputs/1-1_512_v2/train.parquet")

# messagesカラムを確認
print(df["messages"][0])
# [{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}]
```

### HuggingFace Datasetsライブラリで読み込み

```python
from datasets import Dataset
import pandas as pd

df = pd.read_parquet("inputs/1-1_512_v2/train.parquet")
ds = Dataset.from_pandas(df)
```

---

## データ内容の確認ポイント

1. **messages形式の確認**: 最後のターンが `assistant` であること（SFTの教師信号）
2. **CoTマーカーの有無**: `Output:`, `Final:`, `Answer:` 等が含まれるかどうか
   - 1-x系: 多くのサンプルに `Output:` が含まれる（CoTマスクが発動）
   - 2-x系: マーカーが無い場合あり（assistant全体が学習対象）
3. **トークン長**: 長いサンプルがどの程度あるか（分布の確認）

---

## 加工済みデータセット（sft_processed）

`inputs/sft_processed/` 配下に、実験用に加工・結合したデータセットを配置。

| バージョン | フォルダ | サンプル数 | 主な変更点 | 作成スクリプト |
|-----------|---------|-----------|-----------|---------------|
| v3 | `v3/` | - | 元データセットの結合・フィルタリング | - |
| v3_improved | `v3_improved/` | - | v3の品質改善版 | - |
| v4 | `v4/` | - | キュレーション改善 | - |
| v4.1 | `v4.1/` | - | v4の微調整 | - |
| v5 | `v5/` | - | 更なる品質改善 | - |
| v6 | `v6/` | 3,869 | Empty Think Injection + 説明文除去 | [`create_sft_v6_dataset.py`](../scripts/create_sft_v6_dataset.py) |
| **v7** | `v7/` | 5,135 | TOML 3倍追加（+1,222件）、XMLエスケープ+8件、Deep YAML +36件 | [`create_sft_v7_dataset.py`](../scripts/create_sft_v7_dataset.py) |
| **v7.1** | `v7.1/` | 4,013 | TOML +100件（複雑なもの優先）、XMLエスケープ+8件、Deep YAML +36件（バランス重視・推奨） | [`create_sft_v7_1_dataset.py`](../scripts/create_sft_v7_1_dataset.py) |
| **v8_stage1** | `v8_stage1_json_csv/` | 800 | JSON 400件 + CSV 400件（段階的SFT Stage 1用） | [`create_v8_format_datasets.py`](../scripts/create_v8_format_datasets.py) |
| **v8_stage2** | `v8_stage2_yaml/` | 500 | YAML専用（段階的SFT Stage 2用） | 同上 |
| **v8_stage3** | `v8_stage3_xml/` | 500 | XML専用（段階的SFT Stage 3用） | 同上 |
| **v8_stage4** | `v8_stage4_mixed/` | 1,000 | 全フォーマット混合（段階的SFT Stage 4用） | 同上 |
| **v8_curated** | `v8_curated_1k/` | 1,000 | 高品質厳選データ（Person Wスタイル） | 同上 |

### v8戦略（段階的SFT - Sequential Format Learning）

Person Uが0.84を達成した知見に基づく新しいアプローチです。

**核心的な発見:**
- フォーマットごとに段階的に学習 → 各フォーマットの限界点に到達可能
- TOMLは他のフォーマットから学習している（Person T発見）
- ベースモデルは特定フォーマットに対して100%の文法正解率を持っている

**4段階の学習計画:**

```
Stage 1: JSON/CSV (800件) → JSON 100%, CSV 100%
    ↓ マージしてHFにアップロード
Stage 2: YAML (500件) → YAML 100%
    ↓ マージしてHFにアップロード
Stage 3: XML (500件) → XML 95%+
    ↓ マージしてHFにアップロード
Stage 4: Mixed (1000件) → TOML 90%+
    ↓
最終モデル → LB 0.8+
```

**関連ファイル:**
- 戦略ドキュメント: [`plans/v8_strategy_sequential_sft.md`](../plans/v8_strategy_sequential_sft.md)
- データセット作成: [`scripts/create_v8_format_datasets.py`](../scripts/create_v8_format_datasets.py)
- Stage 1ノートブック: [`notebooks/SFT/v8_stage1_json_csv.ipynb`](../notebooks/SFT/v8_stage1_json_csv.ipynb)

---

### v7 vs v7.1 の違い

| 項目 | v7（TOML 3倍版） | v7.1（バランス重視版・推奨） |
|------|----------------|-------------------------|
| サンプル数 | 5,135件 | 4,013件 |
| TOML追加数 | +1,222件（3倍） | +100件（複雑なもの優先） |
| XMLエスケープ | +8件 | +8件 |
| Deep YAML | +36件 | +36件 |
| 過学習リスク | 高 | 低 |
| 推奨度 | △ | ◎ |

---

## LBスコア推移（参考）

| バージョン | LBスコア | 備考 |
|-----------|---------|------|
| v5.2 | 0.77702 | 最高スコア |
| v6 | 0.735894 | Empty Think Injection |
| DPO v1 | 0.70663 | DPO学習 |

---

## 関連ドキュメント

- [トークン長分析結果](./token_length_analysis_summary.md)
- [ディレクトリ構造](./data_directory_structure.md)
- [v1改善計画](../plans/v1_sft_improvement_plan.md)
- [v2改善計画](../plans/v2_improvement_plan.md)
- [v7戦略分析](../plans/v7_strategy_analysis.md)
