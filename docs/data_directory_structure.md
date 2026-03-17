# データディレクトリ構造

本プロジェクトのデータディレクトリ構造を説明します。

## ディレクトリ構成

```
inputs/
├── dpo/                    # DPO用データセット
│   ├── train.json
│   └── train.parquet
├── sft/                    # 元のSFTデータセット（ダウンロードしたもの）
│   ├── 1-1_512_v2/
│   ├── 1-2_512_v4/
│   ├── 1-3_512_v5/
│   ├── 1-4_512/
│   ├── 1-5_v2/
│   ├── 1-6_base/
│   ├── 2-1_3k_mix/
│   ├── 2-2_5k_mix/
│   └── 2-3_hard_4k/
├── sft_processed/          # 加工済みSFTデータセット
│   ├── v3/                 # v3用に結合・加工したデータ
│   │   ├── train.json
│   │   └── train.parquet
│   ├── v3_improved/        # v3の品質改善版
│   │   └── train.json
│   ├── v4/                 # キュレーション改善版
│   │   └── train.json
│   ├── v4.1/               # v4の微調整
│   │   └── train.json
│   ├── v5/                 # 品質改善版
│   │   └── train.json
│   ├── v6/                 # Empty Think Injection + 説明文除去
│   │   └── train.json
│   ├── v7/                 # TOML 3倍版（5,135件）
│   │   └── train.json
│   └── v7.1/               # バランス重視版（4,013件）推奨
│       └── train.json
└── dpo_processed/          # 加工済みDPOデータセット
    └── v1/
        └── train.json
```

## 各ディレクトリの役割

### `inputs/sft/`
- **目的**: 元のデータセットを保存（変更しない）
- **内容**: HuggingFaceやKaggleからダウンロードした生データ
- **命名規則**: ダウンロード元の名前をそのまま使用

### `inputs/sft_processed/`
- **目的**: 加工・結合したデータセットを保存
- **内容**:
  - 複数データセットの結合
  - フィルタリング済みデータ
  - 品質改善済みデータ
- **命名規則**: バージョン番号（v1, v2, v3...）で管理

### `inputs/dpo/`
- **目的**: DPO（Direct Preference Optimization）用データ
- **内容**: 選好学習用のデータセット

## バージョン管理ポリシー

1. **元データは不変**: `inputs/sft/` 配下のデータは変更しない
2. **加工データは別管理**: 結合・フィルタリング等を行ったデータは `inputs/sft_processed/` に配置
3. **バージョン番号**: 実験バージョンに合わせて v1, v2, v3... と命名

## 各バージョンのデータセット

### v3〜v5: 品質改善版
元の`inputs/sft/`配下の複数データセットを結合し、以下の処理を適用:
- 重複除去
- 品質フィルタリング
- フォーマット統一

### v6: Empty Think Injection版
配置場所: `inputs/sft_processed/v6/`
- 空の`<think></think>`タグを注入
- 説明文・コードフェンスの除去
- サンプル数: 3,869件

### v7: TOML 3倍版
配置場所: `inputs/sft_processed/v7/`
- v6ベースにTOML +1,222件（3倍）追加
- XMLエスケープサンプル +8件
- Deep YAML（ネスト5レベル以上）+36件
- サンプル数: 5,135件
- **注意**: 過学習リスクあり

### v7.1: バランス重視版（推奨）
配置場所: `inputs/sft_processed/v7.1/`
- v6ベースにTOML +100件（複雑なもの優先）追加
- XMLエスケープサンプル +8件
- Deep YAML（ネスト5レベル以上）+36件
- サンプル数: 4,013件
- **推奨**: 過学習リスクを抑えたバランス版

### 使用方法（notebook内）
```python
# v7.1用データセットの読み込み
dataset = load_dataset("json", data_files="inputs/sft_processed/v7.1/train.json")
```
