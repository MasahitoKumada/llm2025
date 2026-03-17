# 📊 LLM Structured Output Generation - Competition Toolkit

LLMの構造化出力生成能力を評価するコンペティション（Struct Eval）向けのツールキットです。
SFT（Supervised Fine-Tuning）およびDPO（Direct Preference Optimization）によるモデルファインチューニングのためのデータ準備、分析、評価ツールを提供します。

## 🎯 プロジェクト概要

このプロジェクトは、LLMが正確な構造化データ（JSON, YAML, XML, TOML, CSV）を生成できるかを評価・改善するためのツールセットです。

### 主な機能

- **データセット分析・可視化**: SFT/DPOデータセットの品質分析
- **推論結果の比較**: 複数モデルの出力を比較・評価
- **データ前処理スクリプト**: トレーニングデータの生成・加工

## 🛠️ 開発ツール

このプロジェクトでは、以下の2つのGradioベースのビューアーアプリを開発しました。

### 🔍 [Inference Comparator](inference-comparator/)

推論結果（inference_v*.json）を比較・分析するためのツールです。

**主な機能:**
- 推論結果の一覧表示とフォーマット検証（JSON, YAML, TOML, XML, CSV対応）
- フォーマット不正のハイライト表示
- 2つの推論結果の並列比較とDiff表示
- task_name、output_typeによるフィルタリング

```bash
# 起動方法
cd inference-comparator
pip install gradio pyyaml toml pandas
python app.py
# http://127.0.0.1:7860 でアクセス
```

### 📊 [Dataset Explorer](dataset-explorer/)

SFT/DPOデータセットを確認・分析するためのツールです。

**主な機能:**
- SFTデータセット分析: フォーマット分布、複雑度分布、品質指標
- DPOデータセット分析: Chosen/Rejected比較、品質指標
- 評価データ分析: タスク種別・出力フォーマット分布
- データセット間の比較分析

```bash
# 起動方法
cd dataset-explorer
pip install -r requirements.txt  # または: pip install gradio plotly pandas numpy pyyaml toml
python app.py
# http://localhost:7860 でアクセス
```

## 📁 ディレクトリ構成

```
llm2025/
├── inference-comparator/    # 推論結果比較ツール
│   ├── app.py               # メインアプリケーション
│   ├── public_150.json      # テストデータ（150タスク）
│   ├── scripts.js           # カスタムJavaScript
│   ├── styles.css           # カスタムCSS
│   └── README.md            # ドキュメント
│
├── dataset-explorer/        # データセット分析ツール
│   ├── app.py               # メインアプリケーション
│   ├── static/              # 静的ファイル（JS/CSS）
│   ├── utils/               # ユーティリティモジュール
│   ├── SPECIFICATION.md     # 設計仕様書
│   └── README.md            # ドキュメント
│
├── docs/                    # ドキュメント
│   ├── sft_datasets_overview.md    # SFTデータセット概要
│   ├── data_directory_structure.md # データ構造説明
│   ├── coding_standards.md         # コーディング規約
│   └── ...
│
├── scripts/                 # データ処理スクリプト
│   ├── create_sft_v*.py     # SFTデータセット生成
│   ├── analyze_v*.py        # 分析スクリプト
│   └── ...
│
├── notebooks/               # Jupyter Notebooks
│   ├── SFT/                 # SFTトレーニング用ノートブック
│   └── DPO/                 # DPOトレーニング用ノートブック
│
├── plans/                   # 戦略・計画ドキュメント
│
├── inputs/                  # 入力データ（※Gitで管理しない）
│   ├── sft/                 # SFTオリジナルデータ
│   ├── dpo/                 # DPOデータ
│   └── sft_processed/       # 加工済みSFTデータ
│
├── outputs/                 # 推論結果（※Gitで管理しない）
│
└── output_analysis/         # 出力分析結果
```

## 📊 対応データセット

### SFTデータセット

| グループ | フォルダ | 説明 |
|---------|---------|------|
| グループ1 | `1-1_512_v2` 〜 `1-6_base` | 短〜中長（平均300〜400トークン） |
| グループ2 | `2-1_3k_mix` 〜 `2-3_hard_4k` | 長文系（平均~1000トークン） |

### 対応出力フォーマット

- **JSON**: JavaScript Object Notation
- **YAML**: YAML Ain't Markup Language
- **XML**: eXtensible Markup Language
- **TOML**: Tom's Obvious, Minimal Language
- **CSV**: Comma-Separated Values

## 🚀 クイックスタート

### 1. リポジトリのクローン

```bash
git clone https://github.com/YOUR_USERNAME/llm2025.git
cd llm2025
```

### 2. 依存パッケージのインストール

```bash
# 各ツールで必要なパッケージ
pip install gradio plotly pandas numpy pyyaml toml
```

### 3. ツールの起動

```bash
# Inference Comparator
cd inference-comparator && python app.py

# または Dataset Explorer
cd dataset-explorer && python app.py
```

## 📝 技術スタック

- **UIフレームワーク**: Gradio 5.x / 6.x
- **グラフ描画**: Plotly
- **データ処理**: Pandas, NumPy
- **フォーマット検証**: PyYAML, toml

## 📜 ライセンス

MIT License

## 👥 Author

- Masahito Kumada
- Powered by Claude (claude-opus-4.5)
