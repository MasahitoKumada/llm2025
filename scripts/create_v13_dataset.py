#!/usr/bin/env python3
"""
v13データセット作成スクリプト

Person T (96.7%達成者) の戦略に基づき、v5データセットからTOML出力サンプルを除去
「TOMLはTOMLデータでは学習していない」という発見に基づく実験
"""

import json
import os
from datetime import datetime

def create_v13_dataset():
    """v5データからTOML出力サンプルを除去したv13データセットを作成"""

    # v5データセットを読み込み
    with open('inputs/sft_processed/v5/train.json', 'r', encoding='utf-8') as f:
        v5_data = json.load(f)

    print("=" * 70)
    print("v13データセット作成: TOML出力除去版")
    print("=" * 70)
    print()
    print(f"v5データセット件数: {len(v5_data)}件")

    # フォーマット別に集計
    format_counts = {"json": 0, "yaml": 0, "csv": 0, "xml": 0, "toml": 0, "unknown": 0}

    # TOML以外のサンプルを抽出
    v13_data = []
    toml_removed = 0

    for item in v5_data:
        metadata = item.get("metadata", {})
        fmt = metadata.get("format", "unknown").lower()

        format_counts[fmt] = format_counts.get(fmt, 0) + 1

        if fmt == "toml":
            toml_removed += 1
        else:
            v13_data.append(item)

    print()
    print("📊 v5データセット フォーマット別内訳:")
    for fmt, count in sorted(format_counts.items()):
        print(f"  {fmt.upper()}: {count}件")

    print()
    print(f"❌ 除去されたTOMLサンプル: {toml_removed}件")
    print(f"✅ v13データセット件数: {len(v13_data)}件")

    # v13データセットを保存
    output_dir = 'inputs/sft_processed/v13'
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'train.json')

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(v13_data, f, ensure_ascii=False, indent=2)

    print()
    print(f"📁 保存先: {output_path}")

    # v13データセットのフォーマット別内訳を再確認
    v13_format_counts = {}
    for item in v13_data:
        metadata = item.get("metadata", {})
        fmt = metadata.get("format", "unknown").upper()
        v13_format_counts[fmt] = v13_format_counts.get(fmt, 0) + 1

    print()
    print("📊 v13データセット フォーマット別内訳:")
    for fmt in ["JSON", "YAML", "CSV", "XML"]:
        count = v13_format_counts.get(fmt, 0)
        print(f"  {fmt}: {count}件")

    print()
    print("=" * 70)
    print("✅ v13データセット作成完了")
    print("=" * 70)

    return len(v13_data), toml_removed

if __name__ == "__main__":
    create_v13_dataset()
