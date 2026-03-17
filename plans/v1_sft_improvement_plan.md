# SFT v1 ハイパーパラメータ改善計画

## 現状（標準コード1のデフォルト設定）

| カテゴリ | パラメータ | 現在の値 |
|---|---|---|
| モデル | SFT_BASE_MODEL | `Qwen/Qwen3-4B-Instruct-2507` |
| データ | SFT_DATASET_ID | `u-10bei/structured_data_with_cot_dataset_512_v2` |
| シーケンス長 | SFT_MAX_SEQ_LEN | **512** |
| LoRA | SFT_LORA_R | 64 |
| LoRA | SFT_LORA_ALPHA | 128 |
| LoRA | SFT_LORA_DROPOUT | 0 |
| LoRA | SFT_LORA_TARGET_MODULES | q/k/v/o/gate/up/down_proj |
| 学習 | SFT_EPOCHS | 1 |
| 学習 | SFT_PER_DEVICE_TRAIN_BS | 2 |
| 学習 | SFT_GRAD_ACCUM | 8 |
| 学習 | SFT_LR | 1e-6 |
| 学習 | SFT_WARMUP_RATIO | 0.1 |
| 学習 | SFT_WEIGHT_DECAY | 0.05 |
| 特殊 | SFT_MASK_COT | 1（有効） |
| 特殊 | SFT_OUTPUT_LEARN_MODE | after_marker |
| 特殊 | SFT_USE_UPSAMPLING | 0（無効） |

## 問題点の分析

### 1. MAX_SEQ_LEN = 512 はデータを大幅に切り詰めている

各データセットの最大文字数（HuggingFace SQL調査結果）：

| データセット | 最大文字数 | 推定最大トークン数 | 512で足りる？ |
|---|---|---|---|
| `_512_v2`（現在使用中） | 3,919 | ~1,000 | ❌ |
| `_512_v4` | 3,597 | ~900 | ❌ |
| `_512_v5` | 4,769 | ~1,200 | ❌ |
| `_512` | 3,439 | ~860 | ❌ |
| `_v2` | 2,537 | ~630 | ❌ |
| `_dataset` | 2,109 | ~530 | ❓ |
| `structured-3k-mix-sft` | 6,683 | ~1,670 | ❌ |
| `structured-5k-mix-sft` | 6,673 | ~1,670 | ❌ |
| `structured-hard-sft-4k` | 6,867 | ~1,720 | ❌ |

※ 推定トークン数は英語/コード中心として文字数÷4で概算。正確な値はトークナイザーで要計測。

### 2. 環境の優位性（Colab Pro: L4/A100/H100）

T4（16GB VRAM）前提の標準コードに対し、Proプランでは：
- **L4**: 24GB VRAM
- **A100**: 40GB/80GB VRAM
- **H100**: 80GB VRAM

→ MAX_SEQ_LEN、バッチサイズ、データ量すべて大幅に拡張可能

## v1 改善計画

### フェーズ1: MAX_SEQ_LEN の最適化（最優先） ✅ 分析完了

**作業内容:**
1. ~~トークナイザーで各データセットの正確なトークン数分布を計測する~~ → ✅ `token_length_analysis.ipynb` で完了
2. ~~使用データセットの95パーセンタイル〜最大トークン数をカバーできるMAX_SEQ_LENを決定~~ → ✅ 決定済み
3. 推論時のmax_model_lenとも整合性を取る

**分析結果に基づく決定値:**
- `_512_v2`のみ使用の場合（v1）: **1024** で十分（P99: 640〜961）
- daichiraデータセットも混ぜる場合（v2以降）: **4096** が必要（P95: ~2200、2048では不足）

> 📊 詳細: [トークン長分析結果](../docs/token_length_analysis_summary.md)

### フェーズ2: その他ハイパーパラメータの調整

| パラメータ | 現在 | v1候補 | 理由 |
|---|---|---|---|
| SFT_MAX_SEQ_LEN | 512 | **1024〜2048** | データ切り詰め防止（最優先） |
| SFT_EPOCHS | 1 | **2〜3** | 小規模データ（~3.6k行）なのでもう少し回せる |
| SFT_LR | 1e-6 | **2e-5〜5e-5** | LoRA学習では一般的に高めのLRが有効 |
| SFT_PER_DEVICE_TRAIN_BS | 2 | **4〜8** | A100/H100なら余裕あり |
| SFT_GRAD_ACCUM | 8 | **4** | BS増なら減らして実効BS維持 |
| SFT_WARMUP_RATIO | 0.1 | 0.1 | 据え置き |
| SFT_LORA_R | 64 | 64〜128 | 余力があれば128を試す |

### フェーズ3: データセット戦略

**候補アプローチ:**
- A) `_512_v2` 単体で MAX_SEQ_LEN を上げる（最もシンプル）
- B) 複数SFTデータセットを結合して学習（データ量UP）
- C) `structured-hard-sft-4k` 等の「ハード」データを混ぜて汎化性能UP
- D) アップサンプリングを有効にして弱いカテゴリを補強

**v1では A) を採用し、まずMAX_SEQ_LENの効果を単独で検証する。**

### フェーズ4: DPO（後続で検討）

SFTのベースライン確立後、DPO（標準コード3）を適用してさらにスコア向上を狙う。

## v1 ノートブックの作成方針

- ファイル名: `メインコンペ_標準コード1(SFT)_v1.ipynb`
- 標準コード1のコピーをベースに、環境変数セルのみ変更
- 変更点を明確にコメントで記載
- 実行環境: Colab Pro（L4 or A100推奨）

## 事前準備: トークン数調査 ✅ 完了

> `token_length_analysis.ipynb` にて全10データセットの計測を完了。
> 結果の詳細は [トークン長分析結果](../docs/token_length_analysis_summary.md) を参照。

### 主要な発見

| グループ | データセット例 | 平均トークン | P99 | MAX_SEQ_LEN推奨 |
|---|---|---|---|---|
| 1-x（u-10bei系） | `_512_v2` | 300-400 | 640-961 | **1024** |
| 2-x（daichira系） | `structured-3k-mix-sft` | ~1000 | >2200 | **4096** |
| DPO | `dpo-dataset-qwen-cot` | - | ~1024 | **1024** |

### v1への適用

- **v1は `MAX_SEQ_LEN=1024` + 1-x系データで進行** → 情報損失 <1%
- 2-x系データの導入はv2以降で `MAX_SEQ_LEN=4096` + A100環境にて検討

これをCPU環境で各データセットに対して実行し、適切なMAX_SEQ_LENを決定する。
