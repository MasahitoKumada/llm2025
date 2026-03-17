#!/usr/bin/env python3
"""
SFTデータセット結合スクリプト

v3戦略: 1-1_512_v2 + 1-2_512_v4 を結合
"""

import json
from pathlib import Path

import pandas as pd


def main():
    base_dir = Path(__file__).parent.parent

    # 入力データセット
    dataset1_path = base_dir / "inputs/sft/1-1_512_v2/train.json"
    dataset2_path = base_dir / "inputs/sft/1-2_512_v4/train.json"

    # 出力ディレクトリ
    output_dir = base_dir / "inputs/sft/v3_merged"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SFTデータセット結合: v3用")
    print("=" * 60)

    # データセット読み込み
    print(f"\n📂 読み込み中: {dataset1_path.name}")
    with open(dataset1_path, "r", encoding="utf-8") as f:
        data1 = json.load(f)
    print(f"   → {len(data1):,} 件")

    print(f"\n📂 読み込み中: {dataset2_path.name}")
    with open(dataset2_path, "r", encoding="utf-8") as f:
        data2 = json.load(f)
    print(f"   → {len(data2):,} 件")

    # 結合
    merged_data = data1 + data2
    print(f"\n✅ 結合完了: {len(merged_data):,} 件")

    # メタデータ分析
    print("\n📊 結合データの内訳:")
    format_counts = {}
    complexity_counts = {}
    schema_counts = {}

    for item in merged_data:
        meta = item.get("metadata", {})

        fmt = meta.get("format", "unknown")
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

        comp = meta.get("complexity", "unknown")
        complexity_counts[comp] = complexity_counts.get(comp, 0) + 1

        schema = meta.get("schema", "unknown")
        schema_counts[schema] = schema_counts.get(schema, 0) + 1

    print("\n   フォーマット別:")
    for fmt, count in sorted(format_counts.items(), key=lambda x: -x[1]):
        pct = count / len(merged_data) * 100
        print(f"     {fmt}: {count:,} 件 ({pct:.1f}%)")

    print("\n   複雑度別:")
    for comp, count in sorted(complexity_counts.items(), key=lambda x: -x[1]):
        pct = count / len(merged_data) * 100
        print(f"     {comp}: {count:,} 件 ({pct:.1f}%)")

    print("\n   スキーマ別 (上位10):")
    sorted_schemas = sorted(schema_counts.items(), key=lambda x: -x[1])[:10]
    for schema, count in sorted_schemas:
        print(f"     {schema}: {count:,} 件")

    # JSONファイル出力
    output_json = output_dir / "train.json"
    print(f"\n💾 保存中: {output_json}")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)

    # Parquetファイル出力
    output_parquet = output_dir / "train.parquet"
    print(f"💾 保存中: {output_parquet}")

    # Parquet用にデータを整形
    parquet_records = []
    for item in merged_data:
        messages = item.get("messages", [])
        metadata = item.get("metadata", {})
        parquet_records.append({
            "messages": json.dumps(messages, ensure_ascii=False),
            "metadata": json.dumps(metadata, ensure_ascii=False)
        })

    df = pd.DataFrame(parquet_records)
    df.to_parquet(output_parquet, index=False)

    print("\n" + "=" * 60)
    print("✅ 完了!")
    print(f"   出力先: {output_dir}")
    print(f"   合計: {len(merged_data):,} 件")
    print("=" * 60)

    # v3用の設定情報を出力
    print("\n📋 v3 ノートブック設定:")
    print("   DATASET_ID = 'v3_merged'")
    print("   MAX_SEQ_LEN = 1024  # v2と同じ")
    print("   LR = 5e-6           # v2と同じ")
    print("   または")
    print("   LR = 8e-6           # 学習強化版")


if __name__ == "__main__":
    main()
