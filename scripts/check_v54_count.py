#!/usr/bin/env python3
"""v5.4データセットの件数確認スクリプト"""
import json

# v5.4データセットを読み込み
with open('inputs/sft_processed/v5.4/train.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 総件数
total_count = len(data)
print(f"総件数: {total_count}件")

# フォーマット別の件数を集計
format_counts = {}
for item in data:
    # metadataフィールドを確認（formatキーを使用）
    if 'metadata' in item and 'format' in item['metadata']:
        fmt = item['metadata']['format'].upper()
    elif 'metadata' in item and 'output_format' in item['metadata']:
        fmt = item['metadata']['output_format'].upper()
    elif 'output_format' in item:
        fmt = item['output_format'].upper()
    else:
        fmt = 'UNKNOWN'

    format_counts[fmt] = format_counts.get(fmt, 0) + 1

print()
print("フォーマット別内訳:")

# 指定された順序で表示
for fmt in ['JSON', 'YAML', 'CSV', 'XML', 'TOML']:
    count = format_counts.get(fmt, 0)
    print(f"- {fmt}: {count}件")

# その他のフォーマットがあれば表示
for fmt, count in sorted(format_counts.items()):
    if fmt not in ['JSON', 'YAML', 'CSV', 'XML', 'TOML']:
        print(f"- {fmt}: {count}件")
