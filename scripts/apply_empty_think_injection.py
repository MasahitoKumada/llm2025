#!/usr/bin/env python3
"""
Apply Empty Think Injection to cleaned dataset.

Person R の Empty Think Injection を適用:
- <think>\n</think>\n\n を assistant 出力の先頭に付与
- system role を追加

Input: inputs/cleaned/merged_dataset_final_clean.jsonl
Output: inputs/sft_processed/v9/train.json
"""

import json
from pathlib import Path
from collections import Counter

def apply_empty_think_injection(content: str) -> str:
    """Empty Think Injection を適用"""
    return f"<think>\n</think>\n\n{content}"

def get_system_prompt(fmt: str) -> str:
    """フォーマット別のシステムプロンプトを生成"""
    fmt_upper = fmt.upper()
    return f"You are a structured data expert. Output only valid {fmt_upper} without any explanation."

def process_record(record: dict) -> dict:
    """レコードを処理"""
    messages = record.get('messages', [])
    fmt = record.get('format', 'json')

    # 新しいメッセージリストを構築
    new_messages = []

    # 1. system role を追加
    new_messages.append({
        'role': 'system',
        'content': get_system_prompt(fmt)
    })

    # 2. user と assistant を処理
    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '')

        if role == 'user':
            new_messages.append({
                'role': 'user',
                'content': content
            })
        elif role == 'assistant':
            # Empty Think Injection を適用
            new_content = apply_empty_think_injection(content)
            new_messages.append({
                'role': 'assistant',
                'content': new_content
            })

    return {
        'messages': new_messages,
        'metadata': {
            'format': fmt,
            'source_format': record.get('source_format', 'unknown'),
            'complexity': record.get('complexity', ''),
            'schema': record.get('schema', ''),
            'type': record.get('type', ''),
            'source': record.get('source', ''),
            'series': record.get('series', ''),
        }
    }

def main():
    input_path = Path('inputs/cleaned/merged_dataset_final_clean.jsonl')
    output_path = Path('inputs/sft_processed/v9/train.json')

    # 出力ディレクトリを作成
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading: {input_path}")

    records = []
    format_counts = Counter()

    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            record = json.loads(line)
            processed = process_record(record)
            records.append(processed)

            fmt = processed['metadata']['format']
            format_counts[fmt] += 1

    print(f"Processed: {len(records)} records")

    print("\nFormat distribution:")
    for fmt, count in sorted(format_counts.items()):
        print(f"  {fmt}: {count}")

    # JSON形式で出力（HuggingFaceデータセット互換）
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to: {output_path}")

    # サンプル表示
    print("\n" + "="*60)
    print("Sample output (first record):")
    print("="*60)

    sample = records[0]
    for msg in sample['messages']:
        role = msg['role']
        content = msg['content']
        if len(content) > 200:
            content = content[:200] + '...'
        print(f"\n[{role}]")
        print(content)

if __name__ == '__main__':
    main()
